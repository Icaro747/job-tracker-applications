"""Camada mockada da IA: valida o pipeline caso a caso, sem Ollama.

Para cada e-mail do ``llm_cases.yaml``, injeta uma resposta canônica (derivada do
gabarito ``expect``) via ``FakeClassifier`` e confirma que ``classify_email``
persiste tudo corretamente. Roda sempre (inclusive no CI). É o teste de regressão
do mapeamento resposta-do-LLM → banco.
"""
import pytest

from email_ingestion.models import InboundEmail
from email_ingestion.services import classify_email
from tests.email_ingestion.fakes import FakeClassifier
from tests.email_ingestion.llm_cases import (
    build_scenario,
    expected_result,
    load_cases,
)

pytestmark = pytest.mark.django_db

CASES = load_cases()


@pytest.mark.parametrize('case', CASES, ids=[c.id for c in CASES])
def test_pipeline_maps_canonical_response(case, user):
    email, app_by_key = build_scenario(case, user)
    result = expected_result(case, app_by_key)

    classification = classify_email(email, classifier=FakeClassifier(result))

    assert classification is not None
    classification.refresh_from_db()
    email.refresh_from_db()

    expected_status = case.expect.get('suggested_status', '')
    assert classification.suggested_intent == case.expect.get('intent', '')
    assert classification.suggested_status == expected_status
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert email.inferred_application_status == expected_status

    app_key = case.expect.get('application')
    if app_key:
        assert email.application_id == app_by_key[app_key].pk
    else:
        assert email.application_id is None

    expected_opps = sorted(
        (o['company'].strip(), o['role'].strip())
        for o in case.expect.get('opportunities', [])
    )
    actual_opps = sorted(
        (o.company_name, o.role_title) for o in classification.opportunities.all()
    )
    assert actual_opps == expected_opps
