"""Camada real da IA (opt-in): roda o Ollama de verdade.

Ferramenta de AVALIAÇÃO — fica fora da suíte normal (marcador ``llm`` +
``-m "not llm"`` no pytest.ini). Rode explicitamente com o Ollama no ar:

    .\\.venv\\Scripts\\python.exe -m pytest -m llm -s tests/email_ingestion/test_llm_eval_real.py

A IA recebe exatamente o texto que a extração produziria em produção (incluindo
e-mails HTML-only que chegam sem corpo). O resumo de confiabilidade é impresso ao
fim da sessão (use ``-s`` para vê-lo). Se o Ollama estiver offline, o módulo é
pulado — nunca falha por indisponibilidade.

MODO SÓ-RELATÓRIO: o teste não falha quando o modelo erra um caso — ele apenas
mede e registra. A confiabilidade é lida no resumo (acertos por dimensão), não no
verde/vermelho da suíte. Assim dá para acompanhar a evolução do modelo sem suíte
vermelha. (A única falha possível é o Ollama recusar a requisição.)
"""
import pytest
import requests
from django.conf import settings

from email_ingestion.classifiers.base import ClassifierError
from email_ingestion.classifiers.ollama import OllamaClassifier
from email_ingestion.services import _open_applications
from tests.email_ingestion.llm_cases import (
    build_scenario,
    compare,
    load_cases,
    record_ai,
    record_ai_malformed,
)


def _ollama_online() -> bool:
    try:
        resp = requests.get(
            f'{settings.OLLAMA_HOST.rstrip("/")}/api/tags', timeout=3
        )
        resp.raise_for_status()
        return True
    except requests.RequestException:
        return False


if not _ollama_online():
    pytest.skip(
        'Ollama offline — avaliacao da IA real pulada.', allow_module_level=True
    )

pytestmark = [pytest.mark.django_db, pytest.mark.llm]

CASES = load_cases()


@pytest.mark.parametrize('case', CASES, ids=[c.id for c in CASES])
def test_real_ollama_classification(case, user):
    email, app_by_key = build_scenario(case, user)
    applications = _open_applications(user)

    # A qualidade (intent/status/vagas) NÃO é asserida — vai para o relatório.
    # Uma resposta fora do schema (alucinação) é registrada como tal, não falha.
    try:
        result = OllamaClassifier().classify(email, applications)
    except ClassifierError as exc:
        record_ai_malformed(case, email, str(exc))
        return

    record_ai(case, email, result, compare(result, case, app_by_key))
