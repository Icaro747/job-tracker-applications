"""Testes do adaptador de LLM (OllamaClassifier) — sem rede real.

A chamada HTTP a ``requests.post`` e substituida por um fake; o foco e a
montagem do contexto e o parse/normalizacao da resposta JSON do Ollama.
"""
import json

import pytest
import requests

from email_ingestion.classifiers import OllamaClassifier
from email_ingestion.classifiers.base import ClassifierError
from tests.factories import InboundEmailFactory, JobApplicationFactory

pytestmark = pytest.mark.django_db


class _FakeResponse:
    def __init__(self, content):
        # ``content`` e a string JSON que o modelo "respondeu".
        self._payload = {'message': {'content': content}}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _patch_post(monkeypatch, content):
    """Faz requests.post devolver uma resposta com ``content`` e captura o body."""
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['timeout'] = timeout
        return _FakeResponse(content)

    monkeypatch.setattr('email_ingestion.classifiers.ollama.requests.post', fake_post)
    return captured


def test_classify_parses_structured_json(monkeypatch):
    email = InboundEmailFactory(sender='rh@empresa.com', subject='Entrevista')
    app = JobApplicationFactory()
    content = json.dumps(
        {
            'summary': 'Convite para entrevista',
            'suggested_status': 'interview',
            'confidence': 92,
            'rationale': 'O e-mail marca uma entrevista',
            'application_id': app.pk,
            'intent': 'atualizacao',
            'opportunities': [],
        }
    )
    captured = _patch_post(monkeypatch, content)

    result = OllamaClassifier().classify(email, [app])

    assert result.summary == 'Convite para entrevista'
    assert result.suggested_status == 'interview'
    assert result.confidence == 92
    assert result.application_id == app.pk
    assert result.intent == 'atualizacao'
    assert result.opportunities == []
    # contexto enviado inclui a candidatura aberta e o e-mail
    user_msg = captured['json']['messages'][1]['content']
    assert f'id={app.pk}' in user_msg
    assert 'rh@empresa.com' in user_msg
    assert captured['url'].endswith('/api/chat')


def test_classify_parses_new_opportunity(monkeypatch):
    email = InboundEmailFactory()
    content = json.dumps(
        {
            'summary': 'Nova vaga de backend',
            'suggested_status': '',
            'confidence': 70,
            'rationale': 'Oferta de emprego nova',
            'application_id': None,
            'intent': 'nova_unica',
            'opportunities': [
                {
                    'company_name': 'ACME',
                    'role_title': 'Dev Backend',
                    'source_url': 'https://acme.com/vaga',
                }
            ],
        }
    )
    _patch_post(monkeypatch, content)

    result = OllamaClassifier().classify(email, [])

    assert result.intent == 'nova_unica'
    assert len(result.opportunities) == 1
    opp = result.opportunities[0]
    assert opp.company_name == 'ACME'
    assert opp.role_title == 'Dev Backend'
    assert opp.source_url == 'https://acme.com/vaga'


def test_classify_parses_list_of_opportunities(monkeypatch):
    email = InboundEmailFactory()
    content = json.dumps(
        {
            'summary': '3 vagas para voce',
            'suggested_status': '',
            'confidence': 60,
            'rationale': 'Newsletter de vagas',
            'application_id': None,
            'intent': 'lista',
            'opportunities': [
                {'company_name': 'ACME', 'role_title': 'Dev Backend'},
                {'company_name': 'Globex', 'role_title': 'Designer'},
                {
                    'company_name': 'Initech',
                    'role_title': 'QA',
                    'source_url': 'https://initech.com/qa',
                },
            ],
        }
    )
    _patch_post(monkeypatch, content)

    result = OllamaClassifier().classify(email, [])

    assert result.intent == 'lista'
    assert [o.company_name for o in result.opportunities] == [
        'ACME',
        'Globex',
        'Initech',
    ]
    # source_url ausente vira string vazia (parse defensivo)
    assert result.opportunities[0].source_url == ''
    assert result.opportunities[2].source_url == 'https://initech.com/qa'


def test_classify_invalid_intent_becomes_blank(monkeypatch):
    email = InboundEmailFactory()
    content = json.dumps(
        {
            'summary': 'Algo',
            'confidence': 10,
            'intent': 'xpto-invalido',
            'opportunities': [],
        }
    )
    _patch_post(monkeypatch, content)

    result = OllamaClassifier().classify(email, [])

    assert result.intent == ''


def test_classify_ignores_malformed_opportunity_entries(monkeypatch):
    email = InboundEmailFactory()
    content = json.dumps(
        {
            'summary': 'Lista com lixo',
            'confidence': 10,
            'intent': 'lista',
            'opportunities': [
                {'company_name': 'ACME', 'role_title': 'Dev'},
                'isto nao e um objeto',
                None,
            ],
        }
    )
    _patch_post(monkeypatch, content)

    result = OllamaClassifier().classify(email, [])

    assert len(result.opportunities) == 1
    assert result.opportunities[0].company_name == 'ACME'


def test_classify_raises_on_malformed_json(monkeypatch):
    email = InboundEmailFactory()
    _patch_post(monkeypatch, 'isto nao e json')

    with pytest.raises(ClassifierError):
        OllamaClassifier().classify(email, [])


def test_classify_raises_on_connection_error(monkeypatch):
    email = InboundEmailFactory()

    def boom(url, json=None, timeout=None):
        raise requests.ConnectionError('connection refused')

    monkeypatch.setattr('email_ingestion.classifiers.ollama.requests.post', boom)

    with pytest.raises(ClassifierError):
        OllamaClassifier().classify(email, [])
