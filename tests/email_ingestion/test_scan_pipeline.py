import pytest

from email_ingestion.models import InboundEmail
from email_ingestion.services import scan_account, scan_all_active_accounts
from tests.email_ingestion.fakes import FakeAdapter, make_message
from tests.factories import EmailAccountFactory, EmailSenderRuleFactory, InboundEmailFactory

pytestmark = pytest.mark.django_db


def test_scan_captures_only_matching_emails():
    account = EmailAccountFactory()
    EmailSenderRuleFactory(email_account=account, sender_domain='@empresa.com')
    adapter = FakeAdapter(
        account,
        messages=[
            make_message('m1', sender='rh@empresa.com', subject='Vaga'),
            make_message('m2', sender='spam@outro.com', subject='Promo'),
        ],
    )

    created = scan_account(account, adapter=adapter)

    assert adapter.authenticated is True
    assert len(created) == 1
    email = created[0]
    assert email.message_id == 'm1'
    assert email.email_account == account
    assert email.processing_status == InboundEmail.ProcessingStatus.PENDING
    assert email.matched_rule is not None
    assert InboundEmail.objects.count() == 1


def test_scan_dedups_by_message_id():
    account = EmailAccountFactory()
    EmailSenderRuleFactory(email_account=account, sender_domain='@empresa.com')
    InboundEmailFactory(message_id='dup', email_account=account, sender='rh@empresa.com')
    adapter = FakeAdapter(account, messages=[make_message('dup', sender='rh@empresa.com')])

    created = scan_account(account, adapter=adapter)

    assert created == []
    assert InboundEmail.objects.filter(message_id='dup').count() == 1


def test_scan_updates_last_scan_at():
    account = EmailAccountFactory()
    assert account.last_scan_at is None
    scan_account(account, adapter=FakeAdapter(account, messages=[]))
    account.refresh_from_db()
    assert account.last_scan_at is not None


def test_scan_ignores_inactive_rules():
    account = EmailAccountFactory()
    EmailSenderRuleFactory(
        email_account=account, sender_domain='@empresa.com', is_active=False
    )
    adapter = FakeAdapter(account, messages=[make_message('m1', sender='rh@empresa.com')])

    created = scan_account(account, adapter=adapter)

    assert created == []


def test_scan_all_skips_inactive_accounts(monkeypatch):
    active = EmailAccountFactory(is_active=True)
    EmailSenderRuleFactory(email_account=active, sender_domain='@empresa.com')
    inactive = EmailAccountFactory(is_active=False)
    EmailSenderRuleFactory(email_account=inactive, sender_domain='@empresa.com')

    # Evita chamar o GmailAdapter real (rede): cada conta recebe um fake vazio.
    monkeypatch.setattr(
        'email_ingestion.services.get_adapter',
        lambda account: FakeAdapter(account, messages=[]),
    )

    results = scan_all_active_accounts()

    assert active.pk in results
    assert inactive.pk not in results
