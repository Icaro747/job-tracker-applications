import pytest
from django.core.management import call_command
from django.urls import reverse

from email_ingestion.models import EmailSenderRule
from tests.email_ingestion.fakes import FakeAdapter
from tests.factories import EmailAccountFactory, EmailSenderRuleFactory

pytestmark = pytest.mark.django_db


def test_account_list_shows_owned_accounts(auth_client, user):
    EmailAccountFactory(user=user, email_address='minha@gmail.com')
    response = auth_client.get(reverse('email_ingestion:account_list'))
    assert response.status_code == 200
    assert b'minha@gmail.com' in response.content


def test_account_detail_owner_ok_non_owner_404(auth_client, user):
    mine = EmailAccountFactory(user=user)
    other = EmailAccountFactory()  # outro usuario
    assert auth_client.get(reverse('email_ingestion:account_detail', args=[mine.pk])).status_code == 200
    assert auth_client.get(reverse('email_ingestion:account_detail', args=[other.pk])).status_code == 404


def test_rule_create(auth_client, user):
    account = EmailAccountFactory(user=user)
    response = auth_client.post(
        reverse('email_ingestion:rule_create', args=[account.pk]),
        {'name': 'Recrutamento', 'sender_domain': '@google.com', 'subject_keywords': 'vaga, entrevista', 'is_active': 'on'},
    )
    assert response.status_code == 302
    rule = EmailSenderRule.objects.get(email_account=account)
    assert rule.name == 'Recrutamento'
    assert rule.subject_keywords == ['vaga', 'entrevista']


def test_rule_create_requires_a_filter(auth_client, user):
    account = EmailAccountFactory(user=user)
    response = auth_client.post(
        reverse('email_ingestion:rule_create', args=[account.pk]),
        {'name': 'Sem filtro', 'is_active': 'on'},
    )
    assert response.status_code == 200  # re-renderiza com erro
    assert EmailSenderRule.objects.filter(email_account=account).count() == 0


def test_rule_update_non_owner_404(auth_client):
    rule = EmailSenderRuleFactory()  # conta de outro usuario
    assert auth_client.get(reverse('email_ingestion:rule_update', args=[rule.pk])).status_code == 404


def test_disconnect_calls_revoke(auth_client, user, monkeypatch):
    account = EmailAccountFactory(user=user, access_token='tok', refresh_token='ref')
    adapter = FakeAdapter(account)
    monkeypatch.setattr('email_ingestion.views.get_adapter', lambda acc: adapter)

    response = auth_client.post(reverse('email_ingestion:account_disconnect', args=[account.pk]))

    assert response.status_code == 302
    assert adapter.revoked is True
    account.refresh_from_db()
    assert account.access_token == ''
    assert account.is_active is False


def test_disconnect_warns_when_remote_revoke_fails(auth_client, user, monkeypatch):
    from django.contrib.messages import get_messages

    account = EmailAccountFactory(user=user, access_token='tok', refresh_token='ref')
    adapter = FakeAdapter(account, revoke_succeeds=False)
    monkeypatch.setattr('email_ingestion.views.get_adapter', lambda acc: adapter)

    response = auth_client.post(reverse('email_ingestion:account_disconnect', args=[account.pk]))

    levels = [m.level_tag for m in get_messages(response.wsgi_request)]
    assert 'warning' in levels
    # Credenciais locais sao limpas mesmo quando a revogacao remota falha.
    account.refresh_from_db()
    assert account.access_token == ''


def test_toggle_active(auth_client, user):
    account = EmailAccountFactory(user=user, is_active=True)
    auth_client.post(reverse('email_ingestion:account_toggle_active', args=[account.pk]))
    account.refresh_from_db()
    assert account.is_active is False


def test_gmail_connect_without_credentials_redirects(auth_client, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ''
    settings.GOOGLE_OAUTH_CLIENT_SECRET = ''
    response = auth_client.get(reverse('email_ingestion:gmail_connect'))
    assert response.status_code == 302
    assert response.url == reverse('email_ingestion:account_list')


def test_gmail_callback_without_state_redirects(auth_client):
    response = auth_client.get(reverse('email_ingestion:gmail_callback'))
    assert response.status_code == 302
    assert response.url == reverse('email_ingestion:account_list')


def test_scan_emails_command_smoke(db):
    # Sem contas ativas: o comando roda sem erro.
    call_command('scan_emails')
