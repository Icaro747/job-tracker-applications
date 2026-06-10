"""Pipeline de e-mail — Fila 1 (varredura) e Fila 2 (classificacao LLM).

A **Fila 1** (``scan_account``) captura e-mails novos de cada conta ativa, aplica
as regras de filtragem e registra os que passam como ``InboundEmail`` pendentes.
A **Fila 2** (``classify_email``) envia cada e-mail ao LLM, registra a
classificacao e decide entre aplicar o status automaticamente (alta confianca) ou
encaminhar para revisao manual.

Ambas as filas sao sincronas e testaveis. O agendamento periodico (Django Q2)
chega na Etapa 5; as notificacoes (modelo ``Notification`` e painel) tambem — por
isso ``notify`` e um gancho no-op por enquanto.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

from applications.models import (
    Company,
    CompanyAuditLog,
    Job,
    JobApplication,
)

from .adapters import get_adapter
from .classifiers import ClassifierError, get_classifier
from .models import EmailAccount, EmailClassification, InboundEmail

logger = logging.getLogger(__name__)

# Status que indicam processo encerrado — candidaturas assim nao sao "abertas"
# e nao entram no contexto enviado ao LLM.
_CLOSED_STATUSES = {
    JobApplication.Status.REJECTED,
    JobApplication.Status.WITHDRAWN,
    JobApplication.Status.ARCHIVED,
}


def notify(user, notification_type, **context) -> None:
    """Gancho de notificacao — implementado na Etapa 5 (modelo + painel).

    Mantido como no-op para fixar os pontos onde notificacoes serao emitidas
    (``email_classified``, ``email_needs_review``, ``directed_job_detected``).
    """
    return None


# --------------------------------------------------------------------------- #
# Fila 2 — Classificacao por LLM.                                              #
# --------------------------------------------------------------------------- #
def _open_applications(user):
    """Candidaturas abertas do usuario (contexto para identificacao pelo LLM)."""
    return list(
        JobApplication.objects.filter(user=user)
        .exclude(status__in=_CLOSED_STATUSES)
        .select_related('job', 'job__company')
    )


def classify_email(email: InboundEmail, classifier=None) -> EmailClassification | None:
    """Classifica um e-mail pendente via LLM (Fila 2).

    Cria a ``EmailClassification`` e decide o fluxo pela confianca e clareza da
    candidatura identificada. Se o LLM falhar, o e-mail permanece ``pending`` e a
    funcao retorna ``None`` — o pipeline nao trava.
    """
    owner = email.email_account.user if email.email_account else None
    applications = _open_applications(owner) if owner else []

    classifier = classifier or get_classifier()
    try:
        result = classifier.classify(email, applications)
    except ClassifierError:
        logger.warning('Classificacao adiada (LLM indisponivel) para e-mail %s', email.pk)
        return None

    classification = EmailClassification.objects.create(
        email=email,
        confidence=result.confidence,
        summary=result.summary,
        suggested_status=result.suggested_status,
        rationale=result.rationale,
    )
    email.inferred_application_status = result.suggested_status

    if result.is_new_opportunity and owner is not None:
        _create_directed_job(email, owner, result)
    else:
        _apply_or_review(email, owner, applications, result)

    return classification


def _apply_or_review(email, owner, applications, result) -> None:
    """Vincula e aplica o status (alta confianca) ou marca para revisao."""
    threshold = settings.LLM_CONFIDENCE_THRESHOLD
    by_id = {app.pk: app for app in applications}
    application = by_id.get(result.application_id)
    status_valid = result.suggested_status in JobApplication.Status.values

    high_confidence = (
        result.confidence >= threshold and application is not None and status_valid
    )
    if high_confidence:
        email.application = application
        email.processing_status = InboundEmail.ProcessingStatus.CLASSIFIED
        application.register_email_update(
            email=email, new_status=result.suggested_status, summary=result.summary
        )
        notify(owner, 'email_classified', email=email, application=application)
    else:
        # Baixa confianca, candidatura ambigua ou status invalido: revisao manual.
        if application is not None:
            email.application = application
        email.processing_status = InboundEmail.ProcessingStatus.NEEDS_REVIEW
        notify(owner, 'email_needs_review', email=email)

    email.save(
        update_fields=['application', 'processing_status', 'inferred_application_status']
    )


def _create_directed_job(email, owner, result) -> None:
    """Cria vaga + candidatura rascunho a partir de uma oportunidade detectada."""
    opp = result.opportunity
    company_name = (opp.company_name if opp else '').strip() or 'Empresa nao identificada'
    company, created = Company.objects.get_or_create(
        name=company_name, defaults={'created_by': owner}
    )
    if created:
        CompanyAuditLog.record_create(company, owner)

    job = Job.objects.create(
        company=company,
        role_title=(opp.role_title if opp else '').strip() or 'Vaga sem titulo',
        source_url=(opp.source_url if opp else '') or '',
        directed_to=owner,
        created_by=owner,
    )
    application = JobApplication.objects.create(
        user=owner,
        job=job,
        status=JobApplication.Status.DRAFT,
        origin=JobApplication.Origin.EMAIL,
    )
    email.application = application
    email.processing_status = InboundEmail.ProcessingStatus.CLASSIFIED
    email.save(
        update_fields=['application', 'processing_status', 'inferred_application_status']
    )
    notify(owner, 'directed_job_detected', email=email, application=application)


def enqueue_classification(email: InboundEmail) -> None:
    """Enfileira a classificacao (Fila 2) — sincrona e resiliente.

    Chamada pela Fila 1 logo apos registrar cada e-mail. Uma falha na
    classificacao de um e-mail nao deve interromper a varredura dos demais.
    """
    try:
        classify_email(email)
    except Exception:  # noqa: BLE001 — isola a Fila 1 de qualquer erro da Fila 2
        logger.exception('Erro inesperado ao classificar e-mail %s', email.pk)


# --------------------------------------------------------------------------- #
# Fila 1 — Varredura.                                                          #
# --------------------------------------------------------------------------- #
def scan_account(account: EmailAccount, adapter=None) -> list[InboundEmail]:
    """Varre uma conta: autentica, busca novas mensagens, filtra e registra.

    Deduplicacao por ``message_id`` (unico no sistema). Apos varrer, carimba
    ``last_scan_at`` para que a proxima execucao busque so o que chegou depois.
    """
    adapter = adapter or get_adapter(account)
    adapter.authenticate()
    rules = list(account.rules.filter(is_active=True))

    created: list[InboundEmail] = []
    for message in adapter.fetch_messages(since=account.last_scan_at):
        if InboundEmail.objects.filter(message_id=message.message_id).exists():
            continue  # deduplicacao: nunca registra a mesma mensagem duas vezes
        matched_rule = next((rule for rule in rules if rule.matches(message)), None)
        if matched_rule is None:
            continue
        email = InboundEmail.objects.create(
            message_id=message.message_id,
            email_account=account,
            sender=message.sender,
            subject=message.subject,
            received_at=message.received_at,
            body_text=message.body_text,
            matched_rule=matched_rule,
            processing_status=InboundEmail.ProcessingStatus.PENDING,
        )
        created.append(email)
        enqueue_classification(email)

    account.last_scan_at = timezone.now()
    account.save(update_fields=['last_scan_at'])
    return created


def scan_all_active_accounts() -> dict[int, list[InboundEmail]]:
    """Varre todas as contas ativas. Retorna {account_id: e-mails criados}."""
    results: dict[int, list[InboundEmail]] = {}
    for account in EmailAccount.objects.filter(is_active=True):
        results[account.pk] = scan_account(account)
    return results
