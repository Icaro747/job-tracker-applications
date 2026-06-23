"""Relatórios de fim de sessão para os testes de extração + IA.

Imprime, depois dos testes, duas seções (quando houver dados coletados):
- perda de informação na transformação do e-mail;
- confiabilidade da IA real (intent/status/vagas/confiança).

Use ``-s`` para ver a saída no terminal.
"""
from tests.email_ingestion import llm_cases


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    lines = (
        llm_cases.build_extraction_report()
        + llm_cases.build_ai_report()
        + llm_cases.build_score_report()
    )
    if not lines:
        return
    terminalreporter.section('Avaliacao de e-mail / IA')
    for line in lines:
        terminalreporter.write_line(line)
