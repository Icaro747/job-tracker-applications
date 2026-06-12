"""Emenda 13 (Fatia 1) — assistente de revisao em dois passos.

Passo 1 confirma a intencao do e-mail (``reviewed_intent``); o passo 2 mostrado
deriva da intencao gravada. Reabrir um e-mail meio-processado cai no passo 2.
"""
import pytest
from django.urls import reverse

from email_ingestion.models import (
    EmailClassification,
    EmailDetectedOpportunity,
    InboundEmail,
)
from tests.factories import (
    EmailAccountFactory,
    EmailClassificationFactory,
    EmailDetectedOpportunityFactory,
    InboundEmailFactory,
)

pytestmark = pytest.mark.django_db


def _review_email(user, **classification_kwargs):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
    )
    EmailClassificationFactory(email=email, **classification_kwargs)
    return email


# --------------------------------------------------------------------------- #
# Modelo.                                                                      #
# --------------------------------------------------------------------------- #
def test_detected_opportunity_defaults_to_pending():
    opp = EmailDetectedOpportunityFactory()
    assert opp.state == EmailDetectedOpportunity.State.PENDING
    assert opp.job is None
    assert opp.application is None


def test_reviewed_intent_blank_by_default():
    classification = EmailClassificationFactory()
    assert classification.reviewed_intent == ''


def test_suggested_intent_blank_by_default():
    # ``suggested_intent`` e persistido pelo servico (emenda 13, Fatia 2); a
    # factory nao o define, entao fica em branco.
    classification = EmailClassificationFactory()
    assert classification.suggested_intent == ''


def test_suggested_intent_stores_value():
    classification = EmailClassificationFactory(
        suggested_intent=EmailClassification.Intent.LIST
    )
    classification.refresh_from_db()
    assert classification.suggested_intent == EmailClassification.Intent.LIST


# --------------------------------------------------------------------------- #
# Passo 1 — confirmar/corrigir a intencao.                                     #
# --------------------------------------------------------------------------- #
def test_set_intent_saves_reviewed_intent(auth_client, user):
    email = _review_email(user)

    response = auth_client.post(
        reverse('email_ingestion:email_set_intent', args=[email.pk]),
        {'intent': 'atualizacao'},
    )

    assert response.status_code == 200
    email.classification.refresh_from_db()
    assert email.classification.reviewed_intent == 'atualizacao'


def test_unconfirmed_email_shows_step1(auth_client, user):
    _review_email(user)  # reviewed_intent em branco

    response = auth_client.get(reverse('email_ingestion:review_list'))

    assert 'Qual e a intencao' in response.content.decode()


def test_confirmed_email_shows_step2(auth_client, user):
    _review_email(user, reviewed_intent='atualizacao')

    body = auth_client.get(reverse('email_ingestion:review_list')).content.decode()

    assert 'Confirmar e aplicar' in body  # passo 2 de atualizacao
    assert 'Qual e a intencao' not in body  # nao reconfirma a intencao


def test_corrigir_intencao_returns_to_step1(auth_client, user):
    email = _review_email(user, reviewed_intent='nova_unica')

    response = auth_client.post(
        reverse('email_ingestion:email_set_intent', args=[email.pk]),
        {'intent': ''},
    )

    email.classification.refresh_from_db()
    assert email.classification.reviewed_intent == ''
    assert 'Qual e a intencao' in response.content.decode()


def test_set_intent_rejects_invalid_value(auth_client, user):
    email = _review_email(user, reviewed_intent='atualizacao')

    auth_client.post(
        reverse('email_ingestion:email_set_intent', args=[email.pk]),
        {'intent': 'valor-invalido'},
    )

    email.classification.refresh_from_db()
    assert email.classification.reviewed_intent == 'atualizacao'  # inalterado


def test_set_intent_rejects_other_users_email(auth_client):
    other = _review_email(EmailAccountFactory().user)

    response = auth_client.post(
        reverse('email_ingestion:email_set_intent', args=[other.pk]),
        {'intent': 'atualizacao'},
    )

    assert response.status_code == 404
