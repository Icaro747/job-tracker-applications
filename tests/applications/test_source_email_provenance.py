"""Fatia 4 — rastreamento de origem (proveniencia).

Cada registro (empresa/vaga/candidatura) guarda um ponteiro opcional para o
``InboundEmail`` que o materializou (``source_email``). O bloco de origem nas
telas mostra a procedencia, mas o link "Ver origem" so aparece para o dono do
e-mail (recurso global, e-mail privado).
"""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from applications.models import JobApplication
from tests.factories import (
    CompanyFactory,
    EmailAccountFactory,
    EmailClassificationFactory,
    InboundEmailFactory,
    JobApplicationFactory,
    JobFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Campo source_email nos tres modelos.                                        #
# --------------------------------------------------------------------------- #
def test_source_email_pointer_on_company_job_application():
    email = InboundEmailFactory()
    company = CompanyFactory(source_email=email)
    job = JobFactory(company=company, source_email=email)
    application = JobApplicationFactory(job=job, source_email=email)

    assert company.source_email == email
    assert job.source_email == email
    assert application.source_email == email
    # related_names distintos e navegaveis a partir do e-mail.
    assert company in email.sourced_companies.all()
    assert job in email.sourced_jobs.all()
    assert application in email.sourced_applications.all()


def test_source_email_defaults_to_null():
    assert CompanyFactory().source_email is None
    assert JobFactory().source_email is None
    assert JobApplicationFactory().source_email is None


def test_deleting_source_email_sets_null_not_cascade():
    email = InboundEmailFactory()
    company = CompanyFactory(source_email=email)
    email.delete()
    company.refresh_from_db()
    assert company.source_email is None


# --------------------------------------------------------------------------- #
# Property origin_email da candidatura.                                        #
# --------------------------------------------------------------------------- #
def test_origin_email_returns_pointer_when_set():
    email = InboundEmailFactory()
    application = JobApplicationFactory(source_email=email)
    assert application.origin_email == email


def test_origin_email_falls_back_to_oldest_linked_email_for_legacy():
    """Legado auto-criado: origin=email, sem ponteiro, mas com e-mail vinculado."""
    application = JobApplicationFactory(origin=JobApplication.Origin.EMAIL)
    now = timezone.now()
    older = InboundEmailFactory(
        application=application, received_at=now - timedelta(days=2)
    )
    InboundEmailFactory(application=application, received_at=now)

    assert application.source_email is None
    assert application.origin_email == older


def test_origin_email_is_none_for_manual_without_pointer():
    application = JobApplicationFactory(origin=JobApplication.Origin.MANUAL)
    assert application.origin_email is None


# --------------------------------------------------------------------------- #
# Bloco de origem nas telas (link "Ver origem" so para o dono).               #
# --------------------------------------------------------------------------- #
def test_company_origin_block_shows_link_for_owner(auth_client, user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(email_account=account, subject='Vaga na Globex')
    company = CompanyFactory(source_email=email)

    response = auth_client.get(
        reverse('applications:company_detail', args=[company.pk])
    )

    content = response.content.decode()
    assert 'Vaga na Globex' in content
    assert reverse('email_ingestion:email_detail', args=[email.pk]) in content


def test_company_origin_block_hides_link_for_non_owner(auth_client):
    other = UserFactory()
    account = EmailAccountFactory(user=other)
    email = InboundEmailFactory(email_account=account, subject='E-mail privado')
    company = CompanyFactory(source_email=email)

    response = auth_client.get(
        reverse('applications:company_detail', args=[company.pk])
    )

    content = response.content.decode()
    assert 'E-mail privado' not in content
    assert reverse('email_ingestion:email_detail', args=[email.pk]) not in content


def test_company_origin_block_manual(auth_client):
    company = CompanyFactory()  # sem source_email

    response = auth_client.get(
        reverse('applications:company_detail', args=[company.pk])
    )

    assert 'manualmente' in response.content.decode().lower()


def test_job_origin_block_shows_link_for_owner(auth_client, user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(email_account=account, subject='Vaga de Designer')
    job = JobFactory(source_email=email)

    response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))

    content = response.content.decode()
    assert 'Vaga de Designer' in content
    assert reverse('email_ingestion:email_detail', args=[email.pk]) in content


def test_application_origin_block_lists_linked_emails(auth_client, user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account, subject='Vaga aberta na Acme'
    )
    application = JobApplicationFactory(user=user, source_email=email)
    email.application = application
    email.save(update_fields=['application'])
    InboundEmailFactory(
        email_account=account,
        application=application,
        subject='Agendamento de entrevista',
    )

    response = auth_client.get(
        reverse('applications:application_detail', args=[application.pk])
    )

    content = response.content.decode()
    assert 'Vaga aberta na Acme' in content
    assert 'Agendamento de entrevista' in content
    assert reverse('email_ingestion:email_detail', args=[email.pk]) in content
