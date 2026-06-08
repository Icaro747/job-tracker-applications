import base64

import pytest

from email_ingestion.adapters import get_adapter
from email_ingestion.adapters.gmail import GmailAdapter
from email_ingestion.models import EmailAccount
from tests.factories import EmailAccountFactory

pytestmark = pytest.mark.django_db


def test_get_adapter_returns_gmail_for_gmail_provider():
    account = EmailAccountFactory(provider=EmailAccount.Provider.GMAIL)
    assert isinstance(get_adapter(account), GmailAdapter)


@pytest.mark.parametrize('provider', ['outlook', 'imap'])
def test_get_adapter_raises_for_unsupported_provider(provider):
    account = EmailAccountFactory(provider=provider)
    with pytest.raises(NotImplementedError):
        get_adapter(account)


def test_gmail_parse_message_extracts_fields():
    body = base64.urlsafe_b64encode('Ola, tudo bem?'.encode()).decode()
    msg = {
        'id': 'abc123',
        'internalDate': '1700000000000',
        'payload': {
            'mimeType': 'multipart/alternative',
            'headers': [
                {'name': 'From', 'value': 'Recrutador <rh@empresa.com>'},
                {'name': 'Subject', 'value': 'Convite para entrevista'},
            ],
            'parts': [
                {'mimeType': 'text/plain', 'body': {'data': body}},
            ],
        },
    }

    fetched = GmailAdapter._parse_message(msg)

    assert fetched.message_id == 'abc123'
    assert fetched.sender == 'rh@empresa.com'
    assert fetched.subject == 'Convite para entrevista'
    assert fetched.body_text == 'Ola, tudo bem?'
