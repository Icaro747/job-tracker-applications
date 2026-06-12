"""Emenda 13 (Fatia 2) — passo 2 da intencao 'lista': uma vaga por item.

Cada item cria SO a Vaga global (sem candidatura). O aviso de duplicacao roda
por item. O e-mail so sai de ``needs_review`` quando todas as linhas filhas
estao em estado terminal (``created``/``dismissed``) — conclusao derivada.
"""
import pytest
from django.urls import reverse

from applications.models import Company, Job, JobApplication
from email_ingestion.models import EmailClassification, EmailDetectedOpportunity, InboundEmail
from tests.factories import (
    CompanyFactory,
    EmailAccountFactory,
    EmailClassificationFactory,
    EmailDetectedOpportunityFactory,
    InboundEmailFactory,
)

pytestmark = pytest.mark.django_db


def _list_email(user, *, n=3):
    """E-mail em revisao com intencao 'lista' e ``n`` vagas pendentes."""
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    classification = EmailClassificationFactory(
        email=email,
        suggested_intent=EmailClassification.Intent.LIST,
        reviewed_intent=EmailClassification.Intent.LIST,
    )
    opps = [
        EmailDetectedOpportunityFactory(
            classification=classification,
            company_name=name,
            role_title=role,
            source_url='',
        )
        for name, role in [
            ('ACME', 'Dev Backend'),
            ('Globex', 'Designer'),
            ('Initech', 'QA'),
        ][:n]
    ]
    return email, opps


def _create_item_url(email):
    return reverse('email_ingestion:email_create_list_item', args=[email.pk])


# --------------------------------------------------------------------------- #
# Renderizacao do passo 2.                                                     #
# --------------------------------------------------------------------------- #
def test_list_step_renders_one_form_per_pending_opportunity(auth_client, user):
    email, _ = _list_email(user)

    resp = auth_client.post(
        reverse('email_ingestion:email_set_intent', args=[email.pk]),
        {'intent': EmailClassification.Intent.LIST},
    )

    assert resp.status_code == 200
    body = resp.content.decode()
    assert body.count('name="opp_id"') == 3
    assert 'ACME' in body and 'Globex' in body and 'Initech' in body
    assert _create_item_url(email) in body


# --------------------------------------------------------------------------- #
# Criar item — so a Vaga.                                                      #
# --------------------------------------------------------------------------- #
def test_create_list_item_materializes_only_job(auth_client, user):
    email, opps = _list_email(user)
    opp = opps[0]

    resp = auth_client.post(
        _create_item_url(email),
        {
            'opp_id': opp.pk,
            'company_name': 'ACME',
            'role_title': 'Dev Backend',
            'source_url': 'https://acme.com/vaga',
        },
    )

    assert resp.status_code == 200
    # So a Vaga e materializada (sem candidatura).
    job = Job.objects.get(role_title='Dev Backend')
    assert job.company.name == 'ACME'
    assert job.source_email_id == email.pk
    assert not JobApplication.objects.exists()
    # A linha vira 'created' ligada a Vaga, sem candidatura.
    opp.refresh_from_db()
    assert opp.state == EmailDetectedOpportunity.State.CREATED
    assert opp.job_id == job.pk
    assert opp.application_id is None
    # Sobraram 2 pendentes → e-mail continua na fila.
    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert email.classification.reviewed_at is None


def test_list_created_job_shows_origin_block(auth_client, user):
    # Emenda 13, Fatia 3: a Vaga criada por item de lista grava ``source_email``,
    # entao a pagina da vaga exibe o bloco de origem apontando para o e-mail.
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        subject='Vagas selecionadas para voce',
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    classification = EmailClassificationFactory(
        email=email, reviewed_intent=EmailClassification.Intent.LIST
    )
    opp = EmailDetectedOpportunityFactory(
        classification=classification, company_name='ACME', role_title='Dev Backend'
    )

    auth_client.post(
        _create_item_url(email),
        {'opp_id': opp.pk, 'company_name': 'ACME', 'role_title': 'Dev Backend'},
    )

    job = Job.objects.get(role_title='Dev Backend')
    assert job.source_email_id == email.pk

    resp = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
    body = resp.content.decode()
    assert 'Origem' in body
    assert 'Vagas selecionadas para voce' in body
    assert reverse('email_ingestion:email_detail', args=[email.pk]) in body


def test_create_list_item_warns_on_duplicate_company(auth_client, user):
    # Nome normalizado coincide ('ACME Ltda' ~ 'ACME') sem ser igual → aviso.
    CompanyFactory(name='ACME')
    email, opps = _list_email(user)

    resp = auth_client.post(
        _create_item_url(email),
        {'opp_id': opps[0].pk, 'company_name': 'ACME Ltda', 'role_title': 'Dev Backend'},
    )

    assert resp.status_code == 200
    assert 'Possivel duplicata' in resp.content.decode()
    # Nada criado ainda; a linha continua pendente.
    assert Company.objects.count() == 1
    assert not Job.objects.exists()
    opps[0].refresh_from_db()
    assert opps[0].state == EmailDetectedOpportunity.State.PENDING


def test_create_list_item_reuse_company_links_existing(auth_client, user):
    existing = CompanyFactory(name='ACME')
    email, opps = _list_email(user)

    resp = auth_client.post(
        _create_item_url(email),
        {
            'opp_id': opps[0].pk,
            'company_name': 'ACME',
            'role_title': 'Dev Backend',
            'reuse_company_id': existing.pk,
        },
    )

    assert resp.status_code == 200
    assert Company.objects.filter(name='ACME').count() == 1
    job = Job.objects.get(role_title='Dev Backend')
    assert job.company_id == existing.pk
    opps[0].refresh_from_db()
    assert opps[0].state == EmailDetectedOpportunity.State.CREATED


def test_create_list_item_force_creates_despite_duplicate(auth_client, user):
    CompanyFactory(name='ACME')
    email, opps = _list_email(user)

    resp = auth_client.post(
        _create_item_url(email),
        {
            'opp_id': opps[0].pk,
            'company_name': 'ACME Ltda',
            'role_title': 'Dev Backend',
            'force': '1',
        },
    )

    assert resp.status_code == 200
    # Forcou: cria a empresa nova apesar do aviso normalizado.
    assert Company.objects.count() == 2
    opps[0].refresh_from_db()
    assert opps[0].state == EmailDetectedOpportunity.State.CREATED


def test_create_list_item_rejects_other_users_email(auth_client, user):
    other_account = EmailAccountFactory()
    other_email = InboundEmailFactory(email_account=other_account)
    classification = EmailClassificationFactory(
        email=other_email, reviewed_intent=EmailClassification.Intent.LIST
    )
    opp = EmailDetectedOpportunityFactory(classification=classification)

    resp = auth_client.post(
        _create_item_url(other_email),
        {'opp_id': opp.pk, 'company_name': 'ACME', 'role_title': 'Dev'},
    )

    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Conclusao derivada do estado das linhas.                                     #
# --------------------------------------------------------------------------- #
def test_email_stays_in_queue_until_all_terminal(auth_client, user):
    email, opps = _list_email(user)

    # Cria 2 dos 3 itens.
    for opp in opps[:2]:
        auth_client.post(
            _create_item_url(email),
            {'opp_id': opp.pk, 'company_name': opp.company_name, 'role_title': opp.role_title},
        )

    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW

    # Ignora o restante (1 pendente) → todos terminais.
    auth_client.post(reverse('email_ingestion:email_ignore', args=[email.pk]))

    email.refresh_from_db()
    # Criou ao menos uma vaga → e-mail concluido como classificado.
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert email.classification.reviewed_at is not None
    opps[2].refresh_from_db()
    assert opps[2].state == EmailDetectedOpportunity.State.DISMISSED


def test_create_last_item_concludes_email(auth_client, user):
    email, opps = _list_email(user, n=1)

    auth_client.post(
        _create_item_url(email),
        {'opp_id': opps[0].pk, 'company_name': 'ACME', 'role_title': 'Dev Backend'},
    )

    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert email.classification.reviewed_at is not None


def test_ignore_all_with_nothing_created_marks_ignored(auth_client, user):
    email, opps = _list_email(user)

    auth_client.post(reverse('email_ingestion:email_ignore', args=[email.pk]))

    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.IGNORED
    assert email.classification.reviewed_at is not None
    for opp in opps:
        opp.refresh_from_db()
        assert opp.state == EmailDetectedOpportunity.State.DISMISSED
