"""Fatia 4 — aviso de duplicacao no fluxo de confirmar 'possivel vaga nova'.

Ao confirmar uma vaga nova cujo nome de empresa casa (normalizado) com uma ja
existente, o sistema avisa e oferece reusar a existente OU criar assim mesmo.
"""
import pytest
from django.urls import reverse

from applications.models import Company, Job, JobApplication
from email_ingestion.models import InboundEmail
from tests.factories import (
    CompanyFactory,
    EmailAccountFactory,
    EmailClassificationFactory,
    EmailDetectedOpportunityFactory,
    InboundEmailFactory,
)

pytestmark = pytest.mark.django_db


def _new_opportunity_email(user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    classification = EmailClassificationFactory(email=email, reviewed_intent='nova_unica')
    EmailDetectedOpportunityFactory(classification=classification)
    return email


def test_create_job_warns_on_duplicate_company(auth_client, user):
    CompanyFactory(name='Globex')
    email = _new_opportunity_email(user)

    response = auth_client.post(
        reverse('email_ingestion:email_create_job', args=[email.pk]),
        {'company_name': 'Globex Inc.', 'role_title': 'Designer', 'source_url': ''},
    )

    assert response.status_code == 200
    assert 'Globex' in response.content.decode()
    # Nada criado ainda: nem empresa nova, nem vaga, nem candidatura.
    assert not Company.objects.filter(name='Globex Inc.').exists()
    assert not Job.objects.exists()
    assert not JobApplication.objects.exists()


def test_create_job_reuse_company_links_existing(auth_client, user):
    existing = CompanyFactory(name='Globex')
    email = _new_opportunity_email(user)

    auth_client.post(
        reverse('email_ingestion:email_create_job', args=[email.pk]),
        {
            'company_name': 'Globex Inc.',
            'role_title': 'Designer',
            'source_url': '',
            'reuse_company_id': existing.pk,
        },
    )

    assert Company.objects.filter(name='Globex').count() == 1
    assert not Company.objects.filter(name='Globex Inc.').exists()
    job = Job.objects.get(role_title='Designer')
    assert job.company_id == existing.pk


def test_create_job_force_creates_despite_duplicate(auth_client, user):
    CompanyFactory(name='Globex')
    email = _new_opportunity_email(user)

    auth_client.post(
        reverse('email_ingestion:email_create_job', args=[email.pk]),
        {
            'company_name': 'Globex Inc.',
            'role_title': 'Designer',
            'source_url': '',
            'force': '1',
        },
    )

    assert Company.objects.filter(name='Globex Inc.').exists()
    job = Job.objects.get(role_title='Designer')
    assert job.company.name == 'Globex Inc.'
