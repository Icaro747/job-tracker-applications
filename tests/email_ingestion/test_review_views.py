"""Testes da tela de revisao de classificacoes (Fila 2)."""
import pytest
from django.urls import reverse

from applications.models import ApplicationTimelineEntry, JobApplication
from email_ingestion.models import EmailClassification, InboundEmail
from tests.factories import (
    EmailAccountFactory,
    EmailClassificationFactory,
    InboundEmailFactory,
    JobApplicationFactory,
)

pytestmark = pytest.mark.django_db


def _processed_email(user, **kwargs):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
        **kwargs,
    )
    EmailClassificationFactory(email=email, suggested_status=JobApplication.Status.INTERVIEW)
    return email


def test_review_list_scoped_to_user(auth_client, user):
    mine = _processed_email(user, subject='Meu e-mail')
    _processed_email(EmailAccountFactory().user, subject='De outro')  # outro dono

    response = auth_client.get(reverse('email_ingestion:review_list'))

    assert response.status_code == 200
    assert b'Meu e-mail' in response.content
    assert b'De outro' not in response.content
    # pendentes nao aparecem na revisao
    assert mine.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW


def test_review_list_excludes_pending(auth_client, user):
    account = EmailAccountFactory(user=user)
    InboundEmailFactory(
        email_account=account,
        subject='Ainda pendente',
        processing_status=InboundEmail.ProcessingStatus.PENDING,
    )
    response = auth_client.get(reverse('email_ingestion:review_list'))
    assert b'Ainda pendente' not in response.content


def test_confirm_apply_changes_status_and_marks_classified(auth_client, user):
    app = JobApplicationFactory(user=user, status=JobApplication.Status.APPLIED)
    email = _processed_email(user)

    response = auth_client.post(
        reverse('email_ingestion:email_confirm', args=[email.pk]),
        {'application': app.pk, 'status': JobApplication.Status.INTERVIEW},
    )

    assert response.status_code == 200
    email.refresh_from_db()
    app.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert email.application_id == app.pk
    assert app.status == JobApplication.Status.INTERVIEW
    assert app.timeline.filter(
        entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE
    ).exists()
    email.classification.refresh_from_db()
    assert email.classification.reviewed_by == user


def test_confirm_with_edited_status(auth_client, user):
    app = JobApplicationFactory(user=user, status=JobApplication.Status.APPLIED)
    email = _processed_email(user)

    auth_client.post(
        reverse('email_ingestion:email_confirm', args=[email.pk]),
        {'application': app.pk, 'status': JobApplication.Status.REJECTED},
    )

    app.refresh_from_db()
    assert app.status == JobApplication.Status.REJECTED


def test_manual_link_sets_application(auth_client, user):
    app = JobApplicationFactory(user=user)
    email = _processed_email(user)

    auth_client.post(
        reverse('email_ingestion:email_link', args=[email.pk]),
        {'application': app.pk},
    )

    email.refresh_from_db()
    assert email.application_id == app.pk


def test_ignore_marks_email_ignored(auth_client, user):
    email = _processed_email(user)

    auth_client.post(reverse('email_ingestion:email_ignore', args=[email.pk]))

    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.IGNORED


def test_actions_reject_other_users_email(auth_client, user):
    email = _processed_email(EmailAccountFactory().user)  # de outro usuario
    response = auth_client.post(reverse('email_ingestion:email_ignore', args=[email.pk]))
    assert response.status_code == 404


def test_confirm_rejects_other_users_application(auth_client, user):
    email = _processed_email(user)
    other_app = JobApplicationFactory()  # candidatura de outro usuario

    response = auth_client.post(
        reverse('email_ingestion:email_confirm', args=[email.pk]),
        {'application': other_app.pk, 'status': JobApplication.Status.INTERVIEW},
    )

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Selo de intencao na fila (emenda 13, Fatia 3).                              #
# --------------------------------------------------------------------------- #
def _review_email_with_intent(user, **classification_kwargs):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    EmailClassificationFactory(email=email, **classification_kwargs)
    return email


def test_queue_shows_suggested_intent_badge(auth_client, user):
    # Intencao sugerida pelo LLM, ainda nao confirmada: selo marcado como palpite.
    _review_email_with_intent(
        user,
        suggested_intent=EmailClassification.Intent.LIST,
        reviewed_intent='',
    )
    response = auth_client.get(reverse('email_ingestion:review_list'))
    content = response.content.decode()
    # O passo 1 renderiza os rotulos como radios; o selo se distingue pelo
    # marcador "Sugerido" e pela classe ``badge-intent``.
    assert 'badge-intent' in content
    assert 'Sugerido' in content


def test_queue_shows_confirmed_intent_badge(auth_client, user):
    # Intencao confirmada pelo usuario: selo sem marca de "sugerido".
    _review_email_with_intent(
        user,
        suggested_intent=EmailClassification.Intent.LIST,
        reviewed_intent=EmailClassification.Intent.UPDATE,
    )
    response = auth_client.get(reverse('email_ingestion:review_list'))
    content = response.content.decode()
    assert 'Atualizacao de candidatura' in content
    # O badge confirmado nao usa o prefixo "Sugerido:".
    assert 'Sugerido: Atualizacao' not in content


def test_queue_without_intent_has_no_badge(auth_client, user):
    # E-mail legado sem intencao: nenhum selo de intencao, sem quebrar a fila.
    _review_email_with_intent(user, suggested_intent='', reviewed_intent='')
    response = auth_client.get(reverse('email_ingestion:review_list'))
    assert response.status_code == 200
    assert 'badge-intent' not in response.content.decode()
