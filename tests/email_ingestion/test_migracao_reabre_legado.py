"""Teste da migracao de dados que reabre o legado auto-classificado (Fatia 1).

E-mails que vieram do caminho automatico antigo sao identificados por
``processing_status = classified`` + ``classification.reviewed_at`` nulo (a
confirmacao manual sempre preenche ``reviewed_at``). A migracao os devolve para
``needs_review`` sem reverter status ou rascunhos ja gravados.
"""
import importlib

import pytest
from django.apps import apps as global_apps
from django.utils import timezone

from email_ingestion.models import InboundEmail
from tests.factories import EmailClassificationFactory, InboundEmailFactory

pytestmark = pytest.mark.django_db

_migration = importlib.import_module(
    'email_ingestion.migrations.0006_reabrir_legado_auto'
)


def _classified(reviewed_at):
    email = InboundEmailFactory(
        processing_status=InboundEmail.ProcessingStatus.CLASSIFIED
    )
    EmailClassificationFactory(email=email, reviewed_at=reviewed_at)
    return email


def test_reabre_apenas_auto_classificados():
    auto = _classified(reviewed_at=None)
    confirmado = _classified(reviewed_at=timezone.now())
    pendente = InboundEmailFactory(
        processing_status=InboundEmail.ProcessingStatus.PENDING
    )
    ja_em_revisao = InboundEmailFactory(
        processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW
    )

    _migration.reabrir_auto_classificados(global_apps, None)

    for email in (auto, confirmado, pendente, ja_em_revisao):
        email.refresh_from_db()

    assert auto.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert confirmado.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert pendente.processing_status == InboundEmail.ProcessingStatus.PENDING
    assert ja_em_revisao.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
