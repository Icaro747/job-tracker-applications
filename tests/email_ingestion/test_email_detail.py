"""Fatia 4 — pagina interna de detalhe do e-mail (escopo restrito ao dono).

Funciona apos o expurgo do corpo, para qualquer provedor e sem sessao no
provedor — por isso e preferida a uma ida direta ao Gmail.
"""
import pytest
from django.urls import reverse

from tests.factories import (
    EmailAccountFactory,
    EmailClassificationFactory,
    InboundEmailFactory,
)

pytestmark = pytest.mark.django_db


def test_detail_rejects_other_users_email(auth_client):
    other_email = InboundEmailFactory(
        email_account=EmailAccountFactory()
    )
    response = auth_client.get(
        reverse('email_ingestion:email_detail', args=[other_email.pk])
    )
    assert response.status_code == 404


def test_detail_shows_body_and_classification(auth_client, user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        subject='Entrevista agendada',
        body_text='Corpo completo do e-mail.',
    )
    EmailClassificationFactory(
        email=email, summary='Resumo da analise', rationale='Justificativa'
    )

    response = auth_client.get(
        reverse('email_ingestion:email_detail', args=[email.pk])
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert 'Entrevista agendada' in content
    assert 'Corpo completo do e-mail.' in content
    assert 'Resumo da analise' in content
    assert 'Justificativa' in content


def test_detail_shows_purged_notice_when_body_empty(auth_client, user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(email_account=account, body_text='')

    response = auth_client.get(
        reverse('email_ingestion:email_detail', args=[email.pk])
    )

    assert 'expurgado' in response.content.decode().lower()


def test_detail_shows_provider_link_for_gmail(auth_client, user):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(email_account=account)

    response = auth_client.get(
        reverse('email_ingestion:email_detail', args=[email.pk])
    )

    assert email.provider_link in response.content.decode()
