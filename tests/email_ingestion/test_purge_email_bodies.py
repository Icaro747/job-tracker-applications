"""Testes do comando purge_email_bodies — minimizacao de dados retidos."""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from email_ingestion.models import InboundEmail
from tests.factories import InboundEmailFactory


@pytest.fixture
def antigo():
    """Data anterior ao limite padrao de retencao (90 dias)."""
    return timezone.now() - timedelta(days=120)


def test_limpa_corpo_de_email_antigo_ja_processado(db, antigo):
    email = InboundEmailFactory(
        body_text='conteudo sensivel',
        processing_status=InboundEmail.ProcessingStatus.CLASSIFIED,
        received_at=antigo,
    )
    call_command('purge_email_bodies')
    email.refresh_from_db()
    assert email.body_text == ''


def test_preserva_email_recente(db):
    email = InboundEmailFactory(
        body_text='ainda relevante',
        processing_status=InboundEmail.ProcessingStatus.CLASSIFIED,
        received_at=timezone.now(),
    )
    call_command('purge_email_bodies')
    email.refresh_from_db()
    assert email.body_text == 'ainda relevante'


def test_preserva_email_antigo_pendente(db, antigo):
    email = InboundEmailFactory(
        body_text='aguardando classificacao',
        processing_status=InboundEmail.ProcessingStatus.PENDING,
        received_at=antigo,
    )
    call_command('purge_email_bodies')
    email.refresh_from_db()
    assert email.body_text == 'aguardando classificacao'


def test_respeita_parametro_days(db):
    email = InboundEmailFactory(
        body_text='conteudo',
        processing_status=InboundEmail.ProcessingStatus.CLASSIFIED,
        received_at=timezone.now() - timedelta(days=10),
    )
    call_command('purge_email_bodies', '--days', '7')
    email.refresh_from_db()
    assert email.body_text == ''
