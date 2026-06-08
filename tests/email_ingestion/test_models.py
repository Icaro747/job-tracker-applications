import pytest
from django.core.exceptions import ValidationError

from email_ingestion.models import EmailSenderRule
from tests.email_ingestion.fakes import make_message
from tests.factories import EmailAccountFactory


def test_scan_times_default_is_midnight(db):
    account = EmailAccountFactory()
    assert account.scan_times == ['00:00']


def test_rule_requires_at_least_one_filter():
    rule = EmailSenderRule(name='Vazia')
    with pytest.raises(ValidationError):
        rule.clean()


def test_rule_clean_passes_with_a_single_filter():
    EmailSenderRule(name='Ok', sender_domain='@empresa.com').clean()
    EmailSenderRule(name='Ok', subject_keywords=['vaga']).clean()


# -- tabela-verdade de matches() ------------------------------------------- #
def test_matches_sender_email_only_ignores_subject():
    rule = EmailSenderRule(sender_email='rh@empresa.com')
    assert rule.matches(make_message(sender='rh@empresa.com', subject='qualquer'))
    assert not rule.matches(make_message(sender='outro@empresa.com', subject='qualquer'))


def test_matches_sender_email_is_case_insensitive():
    rule = EmailSenderRule(sender_email='RH@Empresa.com')
    assert rule.matches(make_message(sender='rh@empresa.com'))


def test_matches_sender_domain_only():
    rule = EmailSenderRule(sender_domain='@empresa.com')
    assert rule.matches(make_message(sender='qualquer@empresa.com'))
    assert not rule.matches(make_message(sender='alguem@outra.com'))


def test_matches_domain_does_not_match_lookalike():
    rule = EmailSenderRule(sender_domain='empresa.com')
    assert not rule.matches(make_message(sender='fraude@malempresa.com'))


def test_matches_keywords_only_any_sender():
    rule = EmailSenderRule(subject_keywords=['vaga', 'entrevista'])
    assert rule.matches(make_message(sender='qualquer@x.com', subject='Convite para ENTREVISTA'))
    assert not rule.matches(make_message(sender='qualquer@x.com', subject='boleto'))


def test_matches_sender_and_keywords_requires_both():
    rule = EmailSenderRule(sender_domain='@empresa.com', subject_keywords=['vaga'])
    assert rule.matches(make_message(sender='rh@empresa.com', subject='Nova vaga'))
    # remetente certo, assunto errado → nao captura
    assert not rule.matches(make_message(sender='rh@empresa.com', subject='outro'))
    # assunto certo, remetente errado → nao captura
    assert not rule.matches(make_message(sender='rh@outra.com', subject='Nova vaga'))
