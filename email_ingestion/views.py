"""Views da Etapa 3 — contas de e-mail, conexao Gmail (OAuth) e regras.

Espelha os padroes da Etapa 2: CBVs genericas + mixin de escopo por dono.
A conexao Gmail usa um fluxo OAuth dedicado (`google_auth_oauthlib`), separado
do login social do allauth, para pedir o escopo `gmail.readonly`.
"""
from datetime import timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from applications.models import Company, CompanyAuditLog, Job, JobApplication
from applications.utils import find_duplicate_company, find_duplicate_job

from .adapters import get_adapter
from .diagnostics import run_diagnostics
from .forms import EmailAccountForm, EmailSenderRuleForm
from .models import (
    EmailAccount,
    EmailClassification,
    EmailDetectedOpportunity,
    EmailSenderRule,
    InboundEmail,
)


# --------------------------------------------------------------------------- #
# Contas de e-mail — privadas por usuario.                                     #
# --------------------------------------------------------------------------- #
class OwnedEmailAccountMixin(LoginRequiredMixin):
    """Restringe o queryset as contas de e-mail do usuario autenticado."""

    model = EmailAccount

    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)


class EmailAccountListView(OwnedEmailAccountMixin, ListView):
    context_object_name = 'accounts'
    template_name = 'email_ingestion/account_list.html'


class EmailAccountDetailView(OwnedEmailAccountMixin, DetailView):
    context_object_name = 'account'
    template_name = 'email_ingestion/account_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['rules'] = self.object.rules.select_related('company')
        context['recent_emails'] = self.object.emails.all()[:20]
        return context


class EmailAccountUpdateView(OwnedEmailAccountMixin, UpdateView):
    form_class = EmailAccountForm
    template_name = 'email_ingestion/account_form.html'


class EmailAccountDeleteView(OwnedEmailAccountMixin, DeleteView):
    template_name = 'email_ingestion/account_confirm_delete.html'
    context_object_name = 'account'
    success_url = reverse_lazy('email_ingestion:account_list')


class IntegrationDiagnosticsView(LoginRequiredMixin, ListView):
    """Mostra o diagnostico das integracoes para o usuario autenticado."""

    context_object_name = 'diagnostics'
    template_name = 'email_ingestion/diagnostics.html'

    def get_queryset(self):
        return run_diagnostics(user=self.request.user)


@login_required
@require_POST
def account_toggle_active(request, pk):
    account = get_object_or_404(EmailAccount, pk=pk, user=request.user)
    account.is_active = not account.is_active
    account.save(update_fields=['is_active'])
    return redirect('email_ingestion:account_detail', pk=account.pk)


@login_required
@require_POST
def account_disconnect(request, pk):
    """Revoga o acesso ao provedor e limpa as credenciais da conta."""
    account = get_object_or_404(EmailAccount, pk=pk, user=request.user)
    try:
        remote_ok = get_adapter(account).revoke()
    except NotImplementedError:
        account.clear_credentials()
        remote_ok = True
    if remote_ok:
        messages.success(request, f'Conta {account.email_address} desconectada.')
    else:
        messages.warning(
            request,
            f'Conta {account.email_address} desconectada localmente, mas a revogacao '
            'no Google falhou. Remova o acesso manualmente em '
            'https://myaccount.google.com/permissions.',
        )
    return redirect('email_ingestion:account_detail', pk=account.pk)


# --------------------------------------------------------------------------- #
# Conexao Gmail via OAuth dedicado.                                            #
# --------------------------------------------------------------------------- #
def _build_flow():
    from google_auth_oauthlib.flow import Flow

    client_config = {
        'web': {
            'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [settings.GMAIL_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=settings.GMAIL_OAUTH_SCOPES,
        redirect_uri=settings.GMAIL_REDIRECT_URI,
    )


@login_required
def gmail_connect(request):
    if not (settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET):
        messages.error(
            request,
            'Conexao Gmail indisponivel: defina GOOGLE_OAUTH_CLIENT_ID e '
            'GOOGLE_OAUTH_CLIENT_SECRET no ambiente.',
        )
        return redirect('email_ingestion:account_list')

    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    request.session['gmail_oauth_state'] = state
    return redirect(authorization_url)


@login_required
def gmail_callback(request):
    state = request.session.get('gmail_oauth_state')
    if not state or 'code' not in request.GET:
        messages.error(request, 'Fluxo de autorizacao invalido ou expirado.')
        return redirect('email_ingestion:account_list')

    flow = _build_flow()
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials
    email_address = _fetch_google_email(credentials)

    # credentials.expiry vem naive em UTC; torna-o aware antes de persistir.
    expiry = credentials.expiry
    if expiry is not None:
        expiry = expiry.replace(tzinfo=dt_timezone.utc)

    account, _ = EmailAccount.objects.update_or_create(
        user=request.user,
        email_address=email_address,
        defaults={
            'provider': EmailAccount.Provider.GMAIL,
            'access_token': credentials.token or '',
            'refresh_token': credentials.refresh_token or '',
            'token_expiry': expiry,
            'is_active': True,
        },
    )
    request.session.pop('gmail_oauth_state', None)
    messages.success(request, f'Conta {email_address} conectada com sucesso.')
    return redirect('email_ingestion:account_detail', pk=account.pk)


def _fetch_google_email(credentials) -> str:
    from googleapiclient.discovery import build

    service = build('oauth2', 'v2', credentials=credentials, cache_discovery=False)
    return service.userinfo().get().execute()['email']


# --------------------------------------------------------------------------- #
# Regras de varredura — aninhadas a uma conta do dono.                         #
# --------------------------------------------------------------------------- #
class OwnedRuleMixin(LoginRequiredMixin):
    model = EmailSenderRule

    def get_queryset(self):
        return EmailSenderRule.objects.filter(email_account__user=self.request.user)


class EmailSenderRuleCreateView(LoginRequiredMixin, CreateView):
    form_class = EmailSenderRuleForm
    template_name = 'email_ingestion/rule_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.account = get_object_or_404(
            EmailAccount, pk=kwargs['account_pk'], user=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.email_account = self.account
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = self.account
        return context

    def get_success_url(self):
        return reverse('email_ingestion:account_detail', args=[self.account.pk])


class EmailSenderRuleUpdateView(OwnedRuleMixin, UpdateView):
    form_class = EmailSenderRuleForm
    template_name = 'email_ingestion/rule_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = self.object.email_account
        return context

    def get_success_url(self):
        return reverse('email_ingestion:account_detail', args=[self.object.email_account_id])


class EmailSenderRuleDeleteView(OwnedRuleMixin, DeleteView):
    template_name = 'email_ingestion/rule_confirm_delete.html'
    context_object_name = 'rule'

    def get_success_url(self):
        return reverse('email_ingestion:account_detail', args=[self.object.email_account_id])


# --------------------------------------------------------------------------- #
# Tela de revisao de classificacoes (Fila 2).                                  #
# --------------------------------------------------------------------------- #
def _owned_email(request, pk):
    """E-mail recebido pertencente a uma conta do usuario autenticado."""
    return get_object_or_404(
        InboundEmail.objects.select_related('classification', 'application__job__company'),
        pk=pk,
        email_account__user=request.user,
    )


def _user_applications(user):
    """Candidaturas do usuario para o dropdown de vinculacao manual."""
    return JobApplication.objects.filter(user=user).select_related('job', 'job__company')


def _render_review_row(request, email, **extra):
    """Renderiza a linha de revisao de um e-mail (parcial HTMX).

    ``extra`` permite injetar o estado de aviso de duplicacao (Fatia 4).
    """
    context = {
        'email': email,
        'applications': _user_applications(request.user),
        'status_choices': JobApplication.Status.choices,
        'intent_choices': EmailClassification.Intent.choices,
    }
    context.update(extra)
    return render(request, 'email_ingestion/_review_row.html', context)


class ClassificationReviewListView(LoginRequiredMixin, ListView):
    """Lista os e-mails ja processados pela Fila 2 para revisao do usuario."""

    context_object_name = 'emails'
    template_name = 'email_ingestion/review_list.html'

    def get_queryset(self):
        # Ordena por confianca (maior primeiro): a faixa apenas prioriza a
        # revisao, nada e escondido (Etapa 4, Fatia 1).
        return (
            InboundEmail.objects.filter(email_account__user=self.request.user)
            .exclude(processing_status=InboundEmail.ProcessingStatus.PENDING)
            .select_related('classification', 'application__job__company')
            .order_by('-classification__confidence', '-received_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['applications'] = _user_applications(self.request.user)
        context['status_choices'] = JobApplication.Status.choices
        context['intent_choices'] = EmailClassification.Intent.choices
        return context


class InboundEmailDetailView(LoginRequiredMixin, DetailView):
    """Tela interna de detalhe do e-mail (Fatia 4), restrita ao dono.

    Mostra assunto/remetente/data, o corpo (ou aviso de expurgo) e a
    classificacao do LLM. Funciona apos o purge e para qualquer provedor.
    """

    context_object_name = 'email'
    template_name = 'email_ingestion/email_detail.html'

    def get_queryset(self):
        return InboundEmail.objects.filter(
            email_account__user=self.request.user
        ).select_related('classification')


@login_required
@require_POST
def email_set_intent(request, pk):
    """Passo 1 do assistente: grava a intencao confirmada pelo usuario (emenda 13).

    Intencao vazia volta ao passo 1 ("corrigir intencao"). A linha re-renderizada
    decide qual passo 2 mostrar a partir de ``reviewed_intent``.
    """
    email = _owned_email(request, pk)
    classification = getattr(email, 'classification', None)
    if classification is not None:
        intent = request.POST.get('intent', '')
        if intent == '' or intent in EmailClassification.Intent.values:
            classification.reviewed_intent = intent
            classification.save(update_fields=['reviewed_intent'])
    return _render_review_row(request, email)


@login_required
@require_POST
def email_confirm_apply(request, pk):
    """Confirma e aplica a classificacao: vincula candidatura e aplica o status."""
    email = _owned_email(request, pk)

    application = email.application
    app_id = request.POST.get('application')
    if app_id:
        application = get_object_or_404(
            JobApplication, pk=app_id, user=request.user
        )
        email.application = application

    if application is None:
        # Erro inline (HTTP 200): o HTMX nao faz swap em respostas de erro e o
        # ``messages`` global fica fora do cartao trocado — re-renderiza com a
        # faixa de erro dentro da linha (emenda 13).
        return _render_review_row(
            request, email, error='Selecione uma candidatura antes de confirmar.'
        )

    new_status = request.POST.get('status', '')
    summary = getattr(getattr(email, 'classification', None), 'summary', '')
    application.register_email_update(
        email=email, new_status=new_status, summary=summary
    )
    _mark_reviewed(email, request.user)
    email.processing_status = InboundEmail.ProcessingStatus.CLASSIFIED
    email.save(update_fields=['application', 'processing_status'])
    return _render_review_row(request, email)


def _mark_reviewed(email, user):
    """Carimba a classificacao como revisada manualmente pelo usuario."""
    if hasattr(email, 'classification'):
        classification = email.classification
        classification.reviewed_by = user
        classification.reviewed_at = timezone.now()
        classification.save(update_fields=['reviewed_by', 'reviewed_at'])


def _materialize_company_job(request, email, *, create_url, extra_fields=None):
    """Resolve Empresa+Vaga a partir dos campos da revisao, com aviso de duplicacao.

    Retorna ``(job, None)`` quando materializou, ou ``(None, response)`` quando
    precisa mostrar o aviso de duplicacao (linha ja re-renderizada). ``create_url``
    e o endpoint para onde o aviso re-posta; ``extra_fields`` sao campos ocultos
    extras (ex.: status sugerido) preservados no re-post. Reusa Empresa por reuso
    explicito ou nome exatamente igual; grava ``source_email`` nos criados (Fatia 4).
    """
    company_name = request.POST.get('company_name', '').strip() or 'Empresa nao identificada'
    role_title = request.POST.get('role_title', '').strip() or 'Vaga sem titulo'
    source_url = request.POST.get('source_url', '').strip()
    force = bool(request.POST.get('force'))
    reuse_company_id = request.POST.get('reuse_company_id')
    reuse_job_id = request.POST.get('reuse_job_id')

    # Reuso de vaga existente: vincula a ela, sem criar registros.
    if reuse_job_id:
        return get_object_or_404(Job, pk=reuse_job_id), None

    if reuse_company_id:
        company = get_object_or_404(Company, pk=reuse_company_id)
    else:
        company = Company.objects.filter(name=company_name).first()

    dup_ctx = {
        'create_url': create_url,
        'pending_company_name': company_name,
        'pending_role_title': role_title,
        'pending_source_url': source_url,
        'pending_extra': extra_fields or {},
    }

    # Aviso de duplicacao de empresa (normalizado, nao bloqueante) — Fatia 4.
    if company is None and not force:
        dup = find_duplicate_company(company_name)
        if dup is not None:
            return None, _render_review_row(
                request, email, dup_kind='company', dup_record=dup, **dup_ctx
            )

    if company is None:
        company = Company.objects.create(
            name=company_name, created_by=request.user, source_email=email
        )
        CompanyAuditLog.record_create(company, request.user)

    # Aviso de duplicacao de vaga na empresa resolvida (nao bloqueante).
    if not force:
        dup_job = find_duplicate_job(company, role_title)
        if dup_job is not None:
            return None, _render_review_row(
                request, email, dup_kind='job', dup_record=dup_job, **dup_ctx
            )

    job = Job.objects.create(
        company=company,
        role_title=role_title,
        source_url=source_url,
        directed_to=request.user,
        created_by=request.user,
        source_email=email,
    )
    return job, None


def _mark_opportunity_created(email, job, application):
    """Marca a oportunidade detectada como criada (emenda 13, intencao unica)."""
    classification = getattr(email, 'classification', None)
    if classification is None:
        return
    opp = (
        classification.opportunities.filter(
            state=EmailDetectedOpportunity.State.PENDING
        ).first()
        or classification.opportunities.first()
    )
    if opp is not None:
        opp.state = EmailDetectedOpportunity.State.CREATED
        opp.job = job
        opp.application = application
        opp.save(update_fields=['state', 'job', 'application'])


def _conclude_email(email, user):
    """Conclui o e-mail quando todas as linhas filhas estao em estado terminal.

    Conclusao *derivada* (emenda 13, Fatia 2): enquanto sobrar oportunidade
    ``pending`` o e-mail continua na fila. Sem pendentes, carimba a revisao e
    define o status — ``CLASSIFIED`` se ao menos uma vaga foi criada, senao
    ``IGNORED`` (lista toda descartada ou e-mail irrelevante).
    """
    classification = getattr(email, 'classification', None)
    if classification is None:
        return
    opportunities = classification.opportunities
    if opportunities.filter(state=EmailDetectedOpportunity.State.PENDING).exists():
        return
    created = opportunities.filter(
        state=EmailDetectedOpportunity.State.CREATED
    ).exists()
    email.processing_status = (
        InboundEmail.ProcessingStatus.CLASSIFIED
        if created
        else InboundEmail.ProcessingStatus.IGNORED
    )
    email.save(update_fields=['processing_status'])
    _mark_reviewed(email, user)


@login_required
@require_POST
def email_create_list_item(request, pk):
    """Materializa apenas a Vaga de um item da lista (emenda 13, Fatia 2).

    Numa lista/newsletter o usuario normalmente ainda nao se candidatou: cada
    item cria so a ``Job`` global (sem candidatura), com aviso de duplicacao por
    item. A linha vira ``created`` ligada a Vaga; o e-mail so sai da fila quando
    todas as linhas estao em estado terminal (``_conclude_email``).
    """
    email = _owned_email(request, pk)
    opp = get_object_or_404(
        EmailDetectedOpportunity,
        pk=request.POST.get('opp_id'),
        classification__email=email,
    )
    job, dup_response = _materialize_company_job(
        request, email,
        create_url=reverse('email_ingestion:email_create_list_item', args=[email.pk]),
        extra_fields={'opp_id': opp.pk},
    )
    if dup_response is not None:
        return dup_response

    opp.state = EmailDetectedOpportunity.State.CREATED
    opp.job = job
    opp.save(update_fields=['state', 'job'])
    _conclude_email(email, request.user)
    return _render_review_row(request, email)


@login_required
@require_POST
def email_create_job(request, pk):
    """Materializa Empresa/Vaga/Candidatura de uma 'possivel vaga nova'.

    So aqui — apos a confirmacao do usuario — os recursos globais sao criados a
    partir dos campos editaveis (Empresa reusada se ja existir). Vincula o e-mail
    a candidatura rascunho e marca a classificacao como revisada.
    """
    email = _owned_email(request, pk)
    job, dup_response = _materialize_company_job(
        request, email,
        create_url=reverse('email_ingestion:email_create_job', args=[email.pk]),
    )
    if dup_response is not None:
        return dup_response

    application = JobApplication.objects.create(
        user=request.user,
        job=job,
        status=JobApplication.Status.DRAFT,
        origin=JobApplication.Origin.EMAIL,
        source_email=email,
    )
    email.application = application
    email.processing_status = InboundEmail.ProcessingStatus.CLASSIFIED
    email.save(update_fields=['application', 'processing_status'])
    _mark_reviewed(email, request.user)
    _mark_opportunity_created(email, job, application)
    return _render_review_row(request, email)


@login_required
@require_POST
def email_create_application(request, pk):
    """Criacao retroativa (emenda 13): materializa Empresa/Vaga/Candidatura e
    aplica o status sugerido para um e-mail de atualizacao cuja candidatura nunca
    foi registrada (ex.: o usuario se candidatou pelo site da empresa). Origem
    ``EXTERNAL`` — e historia real, so nao estava no sistema. Resolve o beco UDS.
    """
    email = _owned_email(request, pk)
    new_status = request.POST.get('status', '')
    job, dup_response = _materialize_company_job(
        request, email,
        create_url=reverse('email_ingestion:email_create_application', args=[email.pk]),
        extra_fields={'status': new_status},
    )
    if dup_response is not None:
        return dup_response

    application = JobApplication.objects.create(
        user=request.user,
        job=job,
        status=JobApplication.Status.DRAFT,
        origin=JobApplication.Origin.EXTERNAL,
        source_email=email,
    )
    summary = getattr(getattr(email, 'classification', None), 'summary', '')
    application.register_email_update(
        email=email, new_status=new_status, summary=summary
    )
    email.application = application
    email.processing_status = InboundEmail.ProcessingStatus.CLASSIFIED
    email.save(update_fields=['application', 'processing_status'])
    _mark_reviewed(email, request.user)
    _mark_opportunity_created(email, job, application)
    return _render_review_row(request, email)


@login_required
@require_POST
def email_discard(request, pk):
    """Descarta um rascunho auto-criado (legado) e limpa orfaos.

    Remove a candidatura rascunho ligada ao e-mail; se a Vaga e a Empresa criadas
    junto ficarem sem nenhuma outra candidatura, sao removidas tambem. Trata-se de
    um palpite rejeitado — nao e historico real —, por isso a remocao e definitiva.
    O e-mail e marcado como ignorado.
    """
    email = _owned_email(request, pk)
    application = email.application
    if application is not None:
        job = application.job
        company = job.company
        application.delete()
        if not job.applications.exists():
            job.delete()
            if not company.jobs.exists():
                company.delete()
    email.application = None
    email.processing_status = InboundEmail.ProcessingStatus.IGNORED
    email.save(update_fields=['application', 'processing_status'])
    return _render_review_row(request, email)


@login_required
@require_POST
def email_link_application(request, pk):
    """Vincula manualmente o e-mail a uma candidatura do usuario."""
    email = _owned_email(request, pk)
    app_id = request.POST.get('application')
    if app_id:
        email.application = get_object_or_404(
            JobApplication, pk=app_id, user=request.user
        )
        email.save(update_fields=['application'])
    return _render_review_row(request, email)


@login_required
@require_POST
def email_ignore(request, pk):
    """Descarta as oportunidades pendentes e conclui o e-mail (emenda 13).

    Usado tanto por 'Ignorar tudo' (lista) quanto por 'Confirmar' (irrelevante):
    descarta os itens pendentes e deixa ``_conclude_email`` derivar o status —
    ``IGNORED`` quando nada foi criado, ``CLASSIFIED`` quando ja havia vagas
    criadas na lista. Sem classificacao (sem itens), conclui como ignorado.
    """
    email = _owned_email(request, pk)
    classification = getattr(email, 'classification', None)
    if classification is None:
        email.processing_status = InboundEmail.ProcessingStatus.IGNORED
        email.save(update_fields=['processing_status'])
        return _render_review_row(request, email)
    classification.opportunities.filter(
        state=EmailDetectedOpportunity.State.PENDING
    ).update(state=EmailDetectedOpportunity.State.DISMISSED)
    _conclude_email(email, request.user)
    return _render_review_row(request, email)
