"""Camada de transformação: o que entra (e-mail bruto) x o que sai (texto p/ IA).

Exercita o mecanismo REAL ``GmailAdapter._extract_body`` com os e-mails do
``llm_cases.yaml`` e mede a perda de informação. Não toca no banco nem na IA.

Hoje NÃO existe conversão HTML→texto: a extração só aproveita a parte
``text/plain``. Estes testes documentam esse comportamento (e-mail HTML-only sai
vazio) e alimentam o relatório de perda impresso ao fim da sessão.
"""
import pytest

from tests.email_ingestion.llm_cases import (
    check_extraction,
    load_cases,
    record_extraction,
)

CASES = load_cases()


@pytest.mark.parametrize('case', CASES, ids=[c.id for c in CASES])
def test_extraction_preserves_or_loses_information(case):
    info = check_extraction(case)
    record_extraction(case, info)

    # Comportamento determinístico atual: sem parte text/plain (HTML-only),
    # a extração retorna vazio — perda total antes de chegar à IA.
    if case.body_text is None and case.body_html is not None:
        assert info['extracted_text'] == '', (
            'E-mail HTML-only deveria sair vazio na extração atual '
            '(sem conversor HTML→texto).'
        )

    # Quando há parte de texto puro, é exatamente ela que segue para a IA.
    if case.body_text is not None:
        assert info['extracted_text'] == case.body_text

    # A perda de marcadores NÃO falha o teste — é medida no relatório final.
