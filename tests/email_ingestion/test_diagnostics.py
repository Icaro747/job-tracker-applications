import requests
import pytest
import logging
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from io import StringIO

from email_ingestion.diagnostics import DiagnosticResult
from email_ingestion.models import EmailAccount
from tests.factories import EmailAccountFactory, EmailSenderRuleFactory

pytestmark = pytest.mark.django_db


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}')

    def json(self):
        return self.payload


def test_ollama_offline_returns_error(settings, monkeypatch):
    from email_ingestion.diagnostics import diagnose_ollama

    settings.OLLAMA_HOST = 'http://localhost:11434'
    settings.OLLAMA_MODEL = 'llama3.2'

    def fake_get(*args, **kwargs):
        raise requests.ConnectionError('offline')

    monkeypatch.setattr('requests.get', fake_get)

    result = diagnose_ollama()

    assert result.status == 'error'
    assert 'Ollama indisponivel' in result.message


def test_ollama_online_without_configured_model_returns_warning(settings, monkeypatch):
    from email_ingestion.diagnostics import diagnose_ollama

    settings.OLLAMA_HOST = 'http://localhost:11434'
    settings.OLLAMA_MODEL = 'llama3.2'

    monkeypatch.setattr(
        'requests.get',
        lambda *args, **kwargs: FakeResponse(
            {'models': [{'name': 'mistral:latest'}]}
        ),
    )

    result = diagnose_ollama()

    assert result.status == 'warning'
    assert 'llama3.2' in result.message


def test_ollama_online_with_configured_model_returns_ok(settings, monkeypatch):
    from email_ingestion.diagnostics import diagnose_ollama

    settings.OLLAMA_HOST = 'http://localhost:11434'
    settings.OLLAMA_MODEL = 'llama3.2'

    monkeypatch.setattr(
        'requests.get',
        lambda *args, **kwargs: FakeResponse(
            {'models': [{'name': 'llama3.2:latest'}]}
        ),
    )

    result = diagnose_ollama()

    assert result.status == 'ok'
    assert 'llama3.2' in result.message


def test_gmail_without_oauth_configuration_returns_error(settings, user):
    from email_ingestion.diagnostics import diagnose_gmail

    settings.GOOGLE_OAUTH_CLIENT_ID = ''
    settings.GOOGLE_OAUTH_CLIENT_SECRET = ''

    result = diagnose_gmail(user=user)

    assert result.status == 'error'
    assert 'GOOGLE_OAUTH_CLIENT_ID' in result.details[0]


def test_gmail_with_active_account_token_and_rule_returns_ok(settings, user):
    from email_ingestion.diagnostics import diagnose_gmail

    settings.GOOGLE_OAUTH_CLIENT_ID = 'client-id'
    settings.GOOGLE_OAUTH_CLIENT_SECRET = 'client-secret'
    account = EmailAccountFactory(
        user=user,
        provider=EmailAccount.Provider.GMAIL,
        access_token='token',
        refresh_token='refresh',
        is_active=True,
        last_scan_at=timezone.now(),
    )
    EmailSenderRuleFactory(email_account=account)

    result = diagnose_gmail(user=user)

    assert result.status == 'ok'
    assert 'Gmail configurado' in result.message


def test_check_integrations_command_outputs_statuses(monkeypatch):
    monkeypatch.setattr(
        'email_ingestion.management.commands.check_integrations.run_diagnostics',
        lambda: [
            DiagnosticResult('gmail', 'ok', 'Gmail configurado.'),
            DiagnosticResult('ollama', 'warning', 'Modelo ausente.'),
        ],
    )
    out = StringIO()

    call_command('check_integrations', stdout=out)

    output = out.getvalue()
    assert '[ok] gmail: Gmail configurado.' in output
    assert '[warning] ollama: Modelo ausente.' in output


def test_diagnostics_view_is_scoped_to_authenticated_user(
    auth_client, settings, user, monkeypatch
):
    settings.GOOGLE_OAUTH_CLIENT_ID = 'client-id'
    settings.GOOGLE_OAUTH_CLIENT_SECRET = 'client-secret'
    mine = EmailAccountFactory(
        user=user,
        email_address='minha@gmail.com',
        access_token='token',
        refresh_token='refresh',
        is_active=True,
        last_scan_at=timezone.now(),
    )
    EmailSenderRuleFactory(email_account=mine)
    other = EmailAccountFactory(
        email_address='outra@gmail.com',
        access_token='token',
        refresh_token='refresh',
        is_active=True,
        last_scan_at=timezone.now(),
    )
    EmailSenderRuleFactory(email_account=other)
    monkeypatch.setattr(
        'requests.get',
        lambda *args, **kwargs: FakeResponse(
            {'models': [{'name': 'llama3.2:latest'}]}
        ),
    )

    response = auth_client.get(reverse('email_ingestion:diagnostics'))

    assert response.status_code == 200
    assert b'Diagnostico de integracoes' in response.content
    assert b'minha@gmail.com' in response.content
    assert b'outra@gmail.com' not in response.content


def test_startup_diagnostics_logs_warning_without_raising(monkeypatch, caplog):
    from email_ingestion.diagnostics import run_startup_diagnostics

    monkeypatch.setattr(
        'email_ingestion.diagnostics.run_diagnostics',
        lambda: [DiagnosticResult('ollama', 'error', 'Ollama indisponivel.')],
    )

    with caplog.at_level(logging.WARNING):
        run_startup_diagnostics()

    assert 'Diagnostico de startup: ollama error - Ollama indisponivel.' in caplog.text
