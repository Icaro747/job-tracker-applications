"""Emenda 13 (Fatia 1) — criacao retroativa de candidatura na atualizacao.

Quando o e-mail atualiza uma candidatura real que nunca foi registrada (o usuario
se candidatou pelo site da empresa), ``email_create_application`` materializa
Empresa/Vaga/Candidatura com origem externa e aplica o status sugerido — resolve
o "clique sem efeito" do caso UDS.
"""
import pytest
from django.urls import reverse

from applications.models import (
    ApplicationTimelineEntry,
    Company,
    Job,
    JobApplication,
)
from email_ingestion.models import InboundEmail
from tests.factories import (
    CompanyFactory,
    EmailAccountFactory,
    EmailClassificationFactory,
    InboundEmailFactory,
)

pytestmark = pytest.mark.django_db


def _update_email_without_application(user, suggested_status='rejected'):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
        inferred_application_status=suggested_status,
    )
    EmailClassificationFactory(
        email=email,
        reviewed_intent='atualizacao',
        suggested_status=suggested_status,
        summary='Sua candidatura foi rejeitada',
    )
    return email


def test_create_application_materializes_and_applies_status(auth_client, user):
    email = _update_email_without_application(user)

    response = auth_client.post(
        reverse('email_ingestion:email_create_application', args=[email.pk]),
        {
            'company_name': 'UDS',
            'role_title': 'Dev .NET',
            'source_url': '',
            'status': 'rejected',
        },
    )

    assert response.status_code == 200
    company = Company.objects.get(name='UDS')
    job = Job.objects.get(company=company, role_title='Dev .NET')
    application = JobApplication.objects.get(job=job, user=user)
    # Candidatura criada ja com o status sugerido, origem externa.
    assert application.status == JobApplication.Status.REJECTED
    assert application.origin == JobApplication.Origin.EXTERNAL
    # Proveniencia nos tres recursos recem-criados.
    assert company.source_email_id == email.pk
    assert job.source_email_id == email.pk
    assert application.source_email_id == email.pk
    # A atualizacao por e-mail entra na timeline.
    assert application.timeline.filter(
        entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE
    ).exists()

    email.refresh_from_db()
    assert email.application_id == application.pk
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert email.classification.reviewed_at is not None


def test_create_application_reuses_existing_company(auth_client, user):
    existing = CompanyFactory(name='UDS')
    email = _update_email_without_application(user)

    auth_client.post(
        reverse('email_ingestion:email_create_application', args=[email.pk]),
        {'company_name': 'UDS', 'role_title': 'Dev', 'source_url': '', 'status': 'rejected'},
    )

    assert Company.objects.filter(name='UDS').count() == 1
    job = Job.objects.get(role_title='Dev')
    assert job.company_id == existing.pk


def test_create_application_warns_on_duplicate_company(auth_client, user):
    CompanyFactory(name='UDS')
    email = _update_email_without_application(user)

    response = auth_client.post(
        reverse('email_ingestion:email_create_application', args=[email.pk]),
        {
            'company_name': 'UDS Inc.',
            'role_title': 'Dev',
            'source_url': '',
            'status': 'rejected',
        },
    )

    assert response.status_code == 200
    assert 'UDS' in response.content.decode()
    # Nada criado ainda: aguarda o usuario reusar ou forcar.
    assert not Job.objects.exists()
    assert not JobApplication.objects.exists()


def test_create_application_rejects_other_users_email(auth_client):
    other = _update_email_without_application(EmailAccountFactory().user)

    response = auth_client.post(
        reverse('email_ingestion:email_create_application', args=[other.pk]),
        {'company_name': 'X', 'role_title': 'Y', 'source_url': '', 'status': 'rejected'},
    )

    assert response.status_code == 404
    assert not Job.objects.exists()
