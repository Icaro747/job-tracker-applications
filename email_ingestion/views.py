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

from applications.models import JobApplication

from .adapters import get_adapter
from .forms import EmailAccountForm, EmailSenderRuleForm
from .models import EmailAccount, EmailSenderRule, InboundEmail


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


def _render_review_row(request, email):
    """Renderiza a linha de revisao de um e-mail (parcial HTMX)."""
    return render(
        request,
        'email_ingestion/_review_row.html',
        {
            'email': email,
            'applications': _user_applications(request.user),
            'status_choices': JobApplication.Status.choices,
        },
    )


class ClassificationReviewListView(LoginRequiredMixin, ListView):
    """Lista os e-mails ja processados pela Fila 2 para revisao do usuario."""

    context_object_name = 'emails'
    template_name = 'email_ingestion/review_list.html'

    def get_queryset(self):
        return (
            InboundEmail.objects.filter(email_account__user=self.request.user)
            .exclude(processing_status=InboundEmail.ProcessingStatus.PENDING)
            .select_related('classification', 'application__job__company')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['applications'] = _user_applications(self.request.user)
        context['status_choices'] = JobApplication.Status.choices
        return context


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

    new_status = request.POST.get('status', '')
    if application is not None:
        summary = getattr(getattr(email, 'classification', None), 'summary', '')
        application.register_email_update(
            email=email, new_status=new_status, summary=summary
        )
        if hasattr(email, 'classification'):
            email.classification.reviewed_by = request.user
            email.classification.reviewed_at = timezone.now()
            email.classification.save(update_fields=['reviewed_by', 'reviewed_at'])
        email.processing_status = InboundEmail.ProcessingStatus.CLASSIFIED
        email.save(update_fields=['application', 'processing_status'])
    else:
        messages.error(request, 'Selecione uma candidatura antes de confirmar.')

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
    """Marca o e-mail como irrelevante (ignorado pelo usuario)."""
    email = _owned_email(request, pk)
    email.processing_status = InboundEmail.ProcessingStatus.IGNORED
    email.save(update_fields=['processing_status'])
    return _render_review_row(request, email)
