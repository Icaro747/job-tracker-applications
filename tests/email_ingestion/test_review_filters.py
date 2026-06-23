"""Filtros da fila de revisao (status / faixa de confianca / busca de texto).

Comportamento-chave (emenda 13, polimento): e-mails ja **ignorados** nao
aparecem na lista por padrao; so surgem quando o usuario seleciona o status
``Ignorado`` (ou ``Todos``). Os tres filtros combinam por E (AND).
"""
import pytest
from django.conf import settings
from django.urls import reverse

from applications.models import JobApplication
from email_ingestion.models import InboundEmail
from tests.factories import (
    EmailAccountFactory,
    EmailClassificationFactory,
    InboundEmailFactory,
)

pytestmark = pytest.mark.django_db

URL = 'email_ingestion:review_list'


def _email(user, status=InboundEmail.ProcessingStatus.NEEDS_REVIEW, confidence=90, **kwargs):
    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(email_account=account, processing_status=status, **kwargs)
    EmailClassificationFactory(
        email=email,
        confidence=confidence,
        suggested_status=JobApplication.Status.INTERVIEW,
    )
    return email


# --------------------------------------------------------------------------- #
# Filtro de status — ignorados escondidos por padrao.                         #
# --------------------------------------------------------------------------- #
def test_default_hides_ignored(auth_client, user):
    _email(user, subject='Em revisao')
    _email(user, status=InboundEmail.ProcessingStatus.IGNORED, subject='Ja ignorado')

    response = auth_client.get(reverse(URL))

    assert b'Em revisao' in response.content
    assert b'Ja ignorado' not in response.content


def test_status_ignored_shows_only_ignored(auth_client, user):
    _email(user, subject='Em revisao')
    _email(user, status=InboundEmail.ProcessingStatus.IGNORED, subject='Ja ignorado')

    response = auth_client.get(reverse(URL), {'status': InboundEmail.ProcessingStatus.IGNORED})

    assert b'Ja ignorado' in response.content
    assert b'Em revisao' not in response.content


def test_status_all_includes_ignored(auth_client, user):
    _email(user, subject='Em revisao')
    _email(user, status=InboundEmail.ProcessingStatus.IGNORED, subject='Ja ignorado')

    response = auth_client.get(reverse(URL), {'status': 'all'})

    assert b'Em revisao' in response.content
    assert b'Ja ignorado' in response.content


def test_status_classified_filters_to_one(auth_client, user):
    _email(user, status=InboundEmail.ProcessingStatus.NEEDS_REVIEW, subject='Aguardando triagem')
    _email(user, status=InboundEmail.ProcessingStatus.CLASSIFIED, subject='Classificado ja')

    response = auth_client.get(
        reverse(URL), {'status': InboundEmail.ProcessingStatus.CLASSIFIED}
    )

    assert b'Classificado ja' in response.content
    assert b'Aguardando triagem' not in response.content


# --------------------------------------------------------------------------- #
# Filtro de faixa de confianca (mesmos limiares do selo, emenda 12).          #
# --------------------------------------------------------------------------- #
def test_band_alta(auth_client, user):
    high = settings.LLM_CONFIDENCE_THRESHOLD
    med = settings.LLM_CONFIDENCE_BAND_MEDIUM
    _email(user, confidence=high + 1, subject='Bem confiante')
    _email(user, confidence=med + 1, subject='Mais ou menos')
    _email(user, confidence=med - 1, subject='Pouco confiante')

    response = auth_client.get(reverse(URL), {'band': 'alta'})

    assert b'Bem confiante' in response.content
    assert b'Mais ou menos' not in response.content
    assert b'Pouco confiante' not in response.content


def test_band_media(auth_client, user):
    high = settings.LLM_CONFIDENCE_THRESHOLD
    med = settings.LLM_CONFIDENCE_BAND_MEDIUM
    _email(user, confidence=high + 1, subject='Bem confiante')
    _email(user, confidence=med + 1, subject='Mais ou menos')
    _email(user, confidence=med - 1, subject='Pouco confiante')

    response = auth_client.get(reverse(URL), {'band': 'media'})

    assert b'Mais ou menos' in response.content
    assert b'Bem confiante' not in response.content
    assert b'Pouco confiante' not in response.content


def test_band_baixa(auth_client, user):
    high = settings.LLM_CONFIDENCE_THRESHOLD
    med = settings.LLM_CONFIDENCE_BAND_MEDIUM
    _email(user, confidence=high + 1, subject='Bem confiante')
    _email(user, confidence=med - 1, subject='Pouco confiante')

    response = auth_client.get(reverse(URL), {'band': 'baixa'})

    assert b'Pouco confiante' in response.content
    assert b'Bem confiante' not in response.content


# --------------------------------------------------------------------------- #
# Busca por texto (assunto ou remetente).                                     #
# --------------------------------------------------------------------------- #
def test_search_by_subject(auth_client, user):
    _email(user, subject='Entrevista na Acme')
    _email(user, subject='Newsletter de vagas')

    response = auth_client.get(reverse(URL), {'q': 'entrevista'})

    assert b'Entrevista na Acme' in response.content
    assert b'Newsletter de vagas' not in response.content


def test_search_by_sender(auth_client, user):
    _email(user, sender='rh@acme.com', subject='Assunto generico A')
    _email(user, sender='news@vagas.com', subject='Assunto generico B')

    response = auth_client.get(reverse(URL), {'q': 'acme'})

    assert b'Assunto generico A' in response.content
    assert b'Assunto generico B' not in response.content


# --------------------------------------------------------------------------- #
# Combinacao dos filtros (AND).                                               #
# --------------------------------------------------------------------------- #
def test_filters_combine_with_and(auth_client, user):
    high = settings.LLM_CONFIDENCE_THRESHOLD
    # Alvo: ignorado + alta confianca + casa a busca.
    _email(
        user,
        status=InboundEmail.ProcessingStatus.IGNORED,
        confidence=high + 1,
        subject='Vaga Python ignorada',
    )
    # Mesmo texto, mas nao-ignorado: excluido pelo status.
    _email(user, confidence=high + 1, subject='Vaga Python em revisao')
    # Ignorado e casa o texto, mas confianca baixa: excluido pela faixa.
    _email(
        user,
        status=InboundEmail.ProcessingStatus.IGNORED,
        confidence=settings.LLM_CONFIDENCE_BAND_MEDIUM - 1,
        subject='Vaga Python fraca',
    )

    response = auth_client.get(
        reverse(URL),
        {'status': InboundEmail.ProcessingStatus.IGNORED, 'band': 'alta', 'q': 'python'},
    )

    assert b'Vaga Python ignorada' in response.content
    assert b'Vaga Python em revisao' not in response.content
    assert b'Vaga Python fraca' not in response.content
