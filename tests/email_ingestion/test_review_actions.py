"""Testes das acoes de revisao introduzidas na Fatia 1 da Etapa 4.

``email_create_job`` materializa Empresa/Vaga/Candidatura so apos a confirmacao
de uma "possivel vaga nova"; ``email_discard`` descarta um rascunho auto-criado
(legado) e limpa Vaga/Empresa que ficarem orfas.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from applications.models import Company, Job, JobApplication
from email_ingestion.models import InboundEmail
from tests.factories import (
    CompanyFactory,
    EmailAccountFactory,
    EmailClassificationFactory,
    EmailDetectedOpportunityFactory,
    InboundEmailFactory,
    JobApplicationFactory,
    JobFactory,
)

pytestmark = pytest.mark.django_db


def _new_opportunity_email(user):
    """E-mail em revisao com intencao 'nova unica' e uma vaga detectada."""
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    classification = EmailClassificationFactory(
        email=email,
        reviewed_intent='nova_unica',
    )
    EmailDetectedOpportunityFactory(
        classification=classification,
        company_name='Globex',
        role_title='Designer',
        source_url='https://globex.com/jobs/123',
    )
    return email


# --------------------------------------------------------------------------- #
# email_create_job — confirmar "possivel vaga nova".                          #
# --------------------------------------------------------------------------- #
def test_create_job_materializes_records_on_confirm(auth_client, user):
    email = _new_opportunity_email(user)

    response = auth_client.post(
        reverse('email_ingestion:email_create_job', args=[email.pk]),
        {
            'company_name': 'Globex',
            'role_title': 'Designer',
            'source_url': 'https://globex.com/jobs/123',
        },
    )

    assert response.status_code == 200
    company = Company.objects.get(name='Globex')
    job = Job.objects.get(company=company, role_title='Designer')
    assert job.directed_to == user
    assert job.created_by == user
    assert job.source_url == 'https://globex.com/jobs/123'
    application = JobApplication.objects.get(job=job, user=user)
    assert application.status == JobApplication.Status.DRAFT
    assert application.origin == JobApplication.Origin.EMAIL

    email.refresh_from_db()
    assert email.application_id == application.pk
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert email.classification.reviewed_by == user
    assert email.classification.reviewed_at is not None
    # A vaga detectada e marcada como criada, com job/candidatura rastreaveis.
    opp = email.classification.opportunities.get()
    assert opp.state == 'created'
    assert opp.job_id == job.pk
    assert opp.application_id == application.pk


def test_create_job_sets_source_email_provenance(auth_client, user):
    email = _new_opportunity_email(user)

    auth_client.post(
        reverse('email_ingestion:email_create_job', args=[email.pk]),
        {
            'company_name': 'Globex',
            'role_title': 'Designer',
            'source_url': 'https://globex.com/jobs/123',
        },
    )

    company = Company.objects.get(name='Globex')
    job = Job.objects.get(company=company, role_title='Designer')
    application = JobApplication.objects.get(job=job, user=user)
    # Empresa recem-criada, vaga e candidatura apontam para o e-mail de origem.
    assert company.source_email_id == email.pk
    assert job.source_email_id == email.pk
    assert application.source_email_id == email.pk


def test_create_job_reuse_company_leaves_company_source_email_null(auth_client, user):
    existing = CompanyFactory(name='Globex')  # sem source_email
    email = _new_opportunity_email(user)

    auth_client.post(
        reverse('email_ingestion:email_create_job', args=[email.pk]),
        {'company_name': 'Globex', 'role_title': 'Designer', 'source_url': ''},
    )

    existing.refresh_from_db()
    # Reuso de empresa existente nao sobrescreve a proveniencia dela.
    assert existing.source_email is None
    job = Job.objects.get(role_title='Designer')
    assert job.source_email_id == email.pk


def test_create_job_reuses_existing_company(auth_client, user):
    existing = CompanyFactory(name='Globex')
    email = _new_opportunity_email(user)

    auth_client.post(
        reverse('email_ingestion:email_create_job', args=[email.pk]),
        {'company_name': 'Globex', 'role_title': 'Designer', 'source_url': ''},
    )

    assert Company.objects.filter(name='Globex').count() == 1
    job = Job.objects.get(role_title='Designer')
    assert job.company_id == existing.pk


# --------------------------------------------------------------------------- #
# email_confirm_apply — erro inline (HTTP 200) quando falta candidatura.       #
# --------------------------------------------------------------------------- #
def test_confirm_without_candidatura_shows_inline_error(auth_client, user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    EmailClassificationFactory(email=email, reviewed_intent='atualizacao')

    response = auth_client.post(
        reverse('email_ingestion:email_confirm', args=[email.pk]),
        {'application': '', 'status': 'interview'},
    )

    # HTMX nao faz swap em erro: mantem 200 e mostra a faixa dentro do cartao.
    assert response.status_code == 200
    assert 'Selecione uma candidatura' in response.content.decode()
    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW


def test_create_job_rejects_other_users_email(auth_client):
    other_email = _new_opportunity_email(EmailAccountFactory().user)

    response = auth_client.post(
        reverse('email_ingestion:email_create_job', args=[other_email.pk]),
        {'company_name': 'X', 'role_title': 'Y', 'source_url': ''},
    )

    assert response.status_code == 404
    assert not Job.objects.exists()


# --------------------------------------------------------------------------- #
# email_discard — descartar rascunho auto-criado (legado).                    #
# --------------------------------------------------------------------------- #
def _auto_created_draft(user):
    """Reproduz o legado: empresa+vaga+rascunho criados pelo caminho automatico."""
    account = EmailAccountFactory(user=user)
    company = CompanyFactory(name='Globex')
    job = JobFactory(company=company, role_title='Designer', directed_to=user)
    application = JobApplicationFactory(
        user=user,
        job=job,
        status=JobApplication.Status.DRAFT,
        origin=JobApplication.Origin.EMAIL,
    )
    email = InboundEmailFactory(
        email_account=account,
        application=application,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    EmailClassificationFactory(email=email, reviewed_at=None)
    return email, application, job, company


def test_discard_removes_draft_and_orphans(auth_client, user):
    email, application, job, company = _auto_created_draft(user)

    response = auth_client.post(
        reverse('email_ingestion:email_discard', args=[email.pk])
    )

    assert response.status_code == 200
    assert not JobApplication.all_objects.filter(pk=application.pk).exists()
    assert not Job.objects.filter(pk=job.pk).exists()
    assert not Company.objects.filter(pk=company.pk).exists()
    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.IGNORED


def test_discard_keeps_company_with_other_jobs(auth_client, user):
    email, application, job, company = _auto_created_draft(user)
    # Outra vaga da mesma empresa, usada por alguem -> empresa nao fica orfa.
    other_job = JobFactory(company=company)
    JobApplicationFactory(job=other_job)

    auth_client.post(reverse('email_ingestion:email_discard', args=[email.pk]))

    assert not Job.objects.filter(pk=job.pk).exists()  # vaga orfa removida
    assert Company.objects.filter(pk=company.pk).exists()  # empresa preservada


def test_discard_rejects_other_users_email(auth_client):
    email, application, *_ = _auto_created_draft(EmailAccountFactory().user)

    response = auth_client.post(
        reverse('email_ingestion:email_discard', args=[email.pk])
    )

    assert response.status_code == 404
    assert JobApplication.all_objects.filter(pk=application.pk).exists()
