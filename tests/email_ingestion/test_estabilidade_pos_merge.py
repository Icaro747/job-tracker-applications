"""Teste de estabilidade do sistema apos o merge da seguranca na Etapa 4.

Exercita o pipeline ponta a ponta (scan -> classify -> review) atravessando os
DOIS pontos de costura que o merge uniu pela primeira vez:

  (A) credenciais OAuth criptografadas com Fernet (``EncryptedTextField``);
  (B) o pipeline de classificacao por LLM (Filas 1 e 2 + tela de revisao).

Diferente dos demais testes, aqui a Fila 2 **nao** e isolada: o proprio
``scan_account`` dispara a classificacao. Injetamos um ``FakeClassifier`` no lugar
do Ollama via ``get_classifier`` (sem rede). E um teste de regressao/caracterizacao
do fluxo principal — se falhar, o merge quebrou alguma costura.
"""
import pytest
from django.urls import reverse

from applications.models import ApplicationTimelineEntry, JobApplication
from email_ingestion.classifiers.base import ClassificationResult
from email_ingestion.models import InboundEmail
from email_ingestion.services import scan_account
from tests.email_ingestion.fakes import FakeAdapter, FakeClassifier, make_message
from tests.factories import (
    EmailAccountFactory,
    EmailSenderRuleFactory,
    JobApplicationFactory,
)

pytestmark = pytest.mark.django_db


def _conta_com_credenciais(user):
    """Conta de e-mail com tokens preenchidos — exercita a criptografia (feature A)."""
    account = EmailAccountFactory(
        user=user,
        access_token='token-acesso-secreto',
        refresh_token='token-refresh-secreto',
    )
    EmailSenderRuleFactory(email_account=account, sender_domain='@empresa.com')
    return account


def _injeta_classificador(monkeypatch, classifier):
    """Faz o fluxo automatico (scan -> enqueue -> classify) usar o fake, sem rede."""
    monkeypatch.setattr(
        'email_ingestion.services.get_classifier', lambda: classifier
    )


def test_estabilidade_fluxo_alta_confianca_apenas_sugere(user, monkeypatch):
    """Scan dispara classificacao de alta confianca, mas nada e aplicado sozinho.

    Atravessa A (conta criptografada) + B (Fila 1 -> Fila 2): mesmo com 95% de
    confianca, o e-mail vai para ``needs_review`` com candidatura/status apenas
    pre-selecionados (Etapa 4, Fatia 1). A conta criptografada sobrevive ao
    pipeline inteiro.
    """
    account = _conta_com_credenciais(user)
    app = JobApplicationFactory(user=user, status=JobApplication.Status.APPLIED)

    _injeta_classificador(
        monkeypatch,
        FakeClassifier(
            ClassificationResult(
                summary='Convite de entrevista confirmado',
                suggested_status=JobApplication.Status.INTERVIEW,
                confidence=95,
                application_id=app.pk,
            )
        ),
    )

    created = scan_account(
        account,
        adapter=FakeAdapter(
            account,
            messages=[
                make_message('msg-1', sender='rh@empresa.com', subject='Entrevista'),
            ],
        ),
    )

    # Fila 1: capturou exatamente o e-mail que casa com a regra.
    assert len(created) == 1
    email = created[0]

    # Fila 2 (disparada pelo scan): alta confianca -> sugestao, nao aplicacao.
    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert email.application_id == app.pk  # pre-selecionada
    assert email.inferred_application_status == JobApplication.Status.INTERVIEW

    app.refresh_from_db()
    assert app.status == JobApplication.Status.APPLIED  # nada aplicado
    assert not app.timeline.filter(
        entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE
    ).exists()

    # Costura A: a conta criptografada continua legivel apos o pipeline inteiro.
    account.refresh_from_db()
    assert account.access_token == 'token-acesso-secreto'
    assert account.refresh_token == 'token-refresh-secreto'


def test_estabilidade_fluxo_revisao_manual(auth_client, user, monkeypatch):
    """E-mail cai na fila de revisao e e confirmado pela tela.

    Cobre o caminho de revisao manual ponta a ponta (scan -> needs_review ->
    confirmacao via HTMX), aplicando o status so na confirmacao do usuario.
    """
    account = _conta_com_credenciais(user)
    app = JobApplicationFactory(user=user, status=JobApplication.Status.APPLIED)

    _injeta_classificador(
        monkeypatch,
        FakeClassifier(
            ClassificationResult(
                summary='Possivel atualizacao, confianca baixa',
                suggested_status=JobApplication.Status.INTERVIEW,
                confidence=40,  # abaixo do LLM_CONFIDENCE_THRESHOLD (80)
                application_id=app.pk,
            )
        ),
    )

    created = scan_account(
        account,
        adapter=FakeAdapter(
            account,
            messages=[
                make_message('msg-rev', sender='rh@empresa.com', subject='Atualizacao'),
            ],
        ),
    )
    email = created[0]
    email.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW

    # O e-mail aparece na tela de revisao do dono.
    response = auth_client.get(reverse('email_ingestion:review_list'))
    assert response.status_code == 200
    assert 'Atualizacao'.encode() in response.content

    # Confirmacao manual aplica o status e marca como revisado.
    response = auth_client.post(
        reverse('email_ingestion:email_confirm', args=[email.pk]),
        {'application': app.pk, 'status': JobApplication.Status.INTERVIEW},
    )
    assert response.status_code == 200

    email.refresh_from_db()
    app.refresh_from_db()
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert app.status == JobApplication.Status.INTERVIEW
    email.classification.refresh_from_db()
    assert email.classification.reviewed_by == user
