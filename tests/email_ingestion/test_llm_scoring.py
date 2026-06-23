"""Pontuacao da avaliacao da IA (funcoes puras) + persistencia em historico.

Sempre rodam (nao dependem do Ollama): exercitam o calculo do score e o
arquivo de historico que registra cada execucao para comparacao ao longo do
tempo. Confiabilidade = acuracia vs gabarito; completude = quantos campos a IA
respondeu; score = blend dos dois.
"""
import json

from tests.email_ingestion import llm_cases


# --------------------------------------------------------------------------- #
# Helpers de fixture local.                                                    #
# --------------------------------------------------------------------------- #
def _checks(intent=True, status=True, application=True, opportunities=True,
            opportunities_expected=True):
    return {
        'intent': intent,
        'suggested_status': status,
        'application': application,
        'opportunities': opportunities,
        'opportunities_expected': opportunities_expected,
        'confidence_value': 90.0,
        'min_confidence_ok': True,
    }


def _full_record():
    """Registro com TODOS os 7 campos respondidos."""
    return {
        'summary': 'um resumo',
        'suggested_status': 'interview',
        'confidence': 90.0,
        'rationale': 'porque sim',
        'application_id': 7,
        'intent': 'atualizacao',
        'opportunities': [('ACME', 'Dev', '')],
    }


def _empty_record():
    return {
        'summary': '',
        'suggested_status': '',
        'confidence': 0.0,
        'rationale': '',
        'application_id': None,
        'intent': '',
        'opportunities': [],
    }


# --------------------------------------------------------------------------- #
# reliability_score — acuracia vs gabarito.                                    #
# --------------------------------------------------------------------------- #
def test_reliability_all_correct_is_100():
    assert llm_cases.reliability_score(_checks()) == 100.0


def test_reliability_all_wrong_is_zero():
    assert llm_cases.reliability_score(
        _checks(intent=False, status=False, application=False, opportunities=False)
    ) == 0.0


def test_reliability_partial_is_proportional():
    # 2 de 4 checagens aplicaveis passaram.
    score = llm_cases.reliability_score(
        _checks(intent=True, status=True, application=False, opportunities=False)
    )
    assert score == 50.0


def test_reliability_ignores_opportunities_when_not_expected():
    # opportunities nao esperado: so contam intent/status/application (3 checagens).
    # 2 de 3 passaram (application falha).
    score = llm_cases.reliability_score(
        _checks(application=False, opportunities=False, opportunities_expected=False)
    )
    assert round(score, 1) == 66.7


# --------------------------------------------------------------------------- #
# completeness_score — quantos campos a IA respondeu.                          #
# --------------------------------------------------------------------------- #
def test_completeness_full_record_is_100():
    assert llm_cases.completeness_score(_full_record()) == 100.0


def test_completeness_empty_record_is_zero():
    assert llm_cases.completeness_score(_empty_record()) == 0.0


def test_completeness_partial_is_proportional():
    record = _empty_record()
    record['summary'] = 'algo'
    record['intent'] = 'lista'
    record['opportunities'] = [('ACME', 'Dev', '')]
    # 3 de 7 campos preenchidos.
    assert round(llm_cases.completeness_score(record), 1) == round(300 / 7, 1)


# --------------------------------------------------------------------------- #
# overall_score — blend confiabilidade/completude.                            #
# --------------------------------------------------------------------------- #
def test_overall_blends_with_weights():
    # 0.7*100 + 0.3*0 = 70
    assert llm_cases.overall_score(100.0, 0.0) == 70.0
    # 0.7*0 + 0.3*100 = 30
    assert llm_cases.overall_score(0.0, 100.0) == 30.0


# --------------------------------------------------------------------------- #
# append_run_history — persistencia e delta vs run anterior.                   #
# --------------------------------------------------------------------------- #
def test_append_history_creates_file_and_returns_no_previous(tmp_path, monkeypatch):
    history = tmp_path / 'hist.json'
    monkeypatch.setattr(llm_cases, 'HISTORY_FILE', history)

    previous = llm_cases.append_run_history({'overall': 50.0, 'label': 'baseline'})

    assert previous is None
    saved = json.loads(history.read_text(encoding='utf-8'))
    assert len(saved) == 1
    assert saved[0]['overall'] == 50.0


def test_append_history_returns_previous_entry(tmp_path, monkeypatch):
    history = tmp_path / 'hist.json'
    monkeypatch.setattr(llm_cases, 'HISTORY_FILE', history)

    llm_cases.append_run_history({'overall': 50.0, 'label': 'baseline'})
    previous = llm_cases.append_run_history({'overall': 71.0, 'label': 'temp0'})

    assert previous['overall'] == 50.0
    saved = json.loads(history.read_text(encoding='utf-8'))
    assert [r['overall'] for r in saved] == [50.0, 71.0]
