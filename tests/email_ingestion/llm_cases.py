"""Carregador e utilidades dos casos de teste de extração + IA.

Fonte única de verdade: ``llm_cases.yaml`` (ao lado deste arquivo). Cada caso
descreve um e-mail (texto e/ou HTML bruto) e o gabarito esperado. As três camadas
de teste reusam estas funções:

- ``test_email_extraction``  → mede o que o mecanismo ``GmailAdapter._extract_body``
  preserva/perde ao transformar o e-mail em texto.
- ``test_llm_eval_mocked``   → valida o pipeline com uma resposta canônica.
- ``test_llm_eval_real``     → roda o Ollama de verdade e compara com o gabarito.

Fluxo fiel à produção: conteúdo bruto → ``_extract_body`` → texto que a IA vê.

Este módulo NÃO começa com ``test_`` de propósito — não é coletado como teste.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from django.conf import settings

from email_ingestion.adapters.gmail import GmailAdapter
from email_ingestion.classifiers.base import ClassificationResult, DetectedOpportunity
from email_ingestion.classifiers.body_normalization import body_for_classification

_CASES_FILE = Path(__file__).parent / 'llm_cases.yaml'


# --------------------------------------------------------------------------- #
# Carregamento dos casos.                                                      #
# --------------------------------------------------------------------------- #
@dataclass
class LlmCase:
    """Um caso de e-mail do YAML."""

    id: str
    sender: str
    subject: str
    body_text: str | None = None
    body_html: str | None = None
    expect_extraction: dict = field(default_factory=dict)
    open_applications: list = field(default_factory=list)
    expect: dict = field(default_factory=dict)


def load_cases() -> list[LlmCase]:
    """Lê o YAML ao lado e devolve a lista de casos."""
    raw = yaml.safe_load(_CASES_FILE.read_text(encoding='utf-8')) or []
    return [
        LlmCase(
            id=item['id'],
            sender=item['sender'],
            subject=item['subject'],
            body_text=item.get('body_text'),
            body_html=item.get('body_html'),
            expect_extraction=item.get('expect_extraction') or {},
            open_applications=item.get('open_applications') or [],
            expect=item.get('expect') or {},
        )
        for item in raw
    ]


# --------------------------------------------------------------------------- #
# Transformação (HTML/texto bruto → texto que a IA vê).                        #
# --------------------------------------------------------------------------- #
def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode('utf-8')).decode('ascii')


def _part(mime: str, text: str) -> dict:
    return {'mimeType': mime, 'body': {'data': _b64(text)}}


def build_gmail_payload(case: LlmCase) -> dict:
    """Monta um payload MIME no formato da Gmail API a partir do caso.

    Espelha o que a Gmail API entrega ao adaptador: ``text/plain`` e/ou
    ``text/html`` (multipart quando há os dois).
    """
    parts = []
    if case.body_text is not None:
        parts.append(_part('text/plain', case.body_text))
    if case.body_html is not None:
        parts.append(_part('text/html', case.body_html))
    if not parts:
        raise ValueError(f'Caso {case.id!r} sem body_text nem body_html.')
    if len(parts) == 1:
        return parts[0]
    return {'mimeType': 'multipart/alternative', 'parts': parts}


def extract_body(case: LlmCase) -> str:
    """Roda o mecanismo REAL de extração e devolve o texto que a IA verá."""
    return GmailAdapter._extract_body(build_gmail_payload(case))


def check_extraction(case: LlmCase) -> dict:
    """Mede a perda de informação na transformação do e-mail."""
    extracted = extract_body(case)
    contains = case.expect_extraction.get('contains', [])
    present = [m for m in contains if m in extracted]
    missing = [m for m in contains if m not in extracted]
    return {
        'extracted_text': extracted,
        'markers_present': present,
        'markers_missing': missing,
    }


# --------------------------------------------------------------------------- #
# Cenário (cria candidaturas abertas + InboundEmail com o texto extraído).     #
# --------------------------------------------------------------------------- #
def build_scenario(case: LlmCase, user):
    """Cria o cenário do caso e devolve ``(email, app_by_key)``.

    O ``InboundEmail`` recebe como ``body_text`` exatamente o resultado de
    ``extract_body`` — ou seja, a IA vê o que a produção entregaria.
    """
    from tests.factories import (
        CompanyFactory,
        EmailAccountFactory,
        InboundEmailFactory,
        JobApplicationFactory,
        JobFactory,
    )

    app_by_key = {}
    for spec in case.open_applications:
        company = CompanyFactory(name=spec['company'])
        job = JobFactory(company=company, role_title=spec['role'])
        app = JobApplicationFactory(
            user=user, job=job, status=spec.get('status', 'applied')
        )
        app_by_key[spec['key']] = app

    account = EmailAccountFactory(user=user)
    email = InboundEmailFactory(
        email_account=account,
        sender=case.sender,
        subject=case.subject,
        body_text=extract_body(case),
    )
    return email, app_by_key


def expected_result(case: LlmCase, app_by_key: dict) -> ClassificationResult:
    """Converte ``expect`` numa resposta canônica do LLM (camada mockada)."""
    expect = case.expect
    app_key = expect.get('application')
    application_id = app_by_key[app_key].pk if app_key else None
    opportunities = [
        DetectedOpportunity(
            company_name=o['company'],
            role_title=o['role'],
            source_url=o.get('url', ''),
        )
        for o in expect.get('opportunities', [])
    ]
    return ClassificationResult(
        summary=f'[teste] {case.id}',
        suggested_status=expect.get('suggested_status', ''),
        confidence=float(expect.get('min_confidence', 90) or 90),
        rationale='resultado canonico de teste',
        application_id=application_id,
        intent=expect.get('intent', ''),
        opportunities=opportunities,
    )


# --------------------------------------------------------------------------- #
# Comparação observado x gabarito (camada real + relatório).                   #
# --------------------------------------------------------------------------- #
def _norm(value: str) -> str:
    return (value or '').strip().lower()


def compare(result: ClassificationResult, case: LlmCase, app_by_key: dict) -> dict:
    """Compara um resultado observado com o gabarito → dict de checagens."""
    expect = case.expect
    app_key = expect.get('application')
    expected_app_id = app_by_key[app_key].pk if app_key else None
    expected_companies = {_norm(o['company']) for o in expect.get('opportunities', [])}
    actual_companies = {_norm(o.company_name) for o in result.opportunities}
    min_conf = float(expect.get('min_confidence', 0) or 0)
    return {
        'intent': result.intent == expect.get('intent', ''),
        'suggested_status': result.suggested_status == expect.get('suggested_status', ''),
        'application': result.application_id == expected_app_id,
        'opportunities': actual_companies == expected_companies,
        'opportunities_expected': bool(expected_companies),
        'confidence_value': float(result.confidence),
        'min_confidence_ok': float(result.confidence) >= min_conf,
    }


# --------------------------------------------------------------------------- #
# Pontuação (confiabilidade x completude) + histórico entre execuções.         #
# --------------------------------------------------------------------------- #
# Pesos do score combinado: a confiabilidade (acertou vs gabarito) pesa mais
# que a completude (quantos campos respondeu). Ajuste aqui se quiser recalibrar.
RELIABILITY_WEIGHT = 0.7
COMPLETENESS_WEIGHT = 0.3

# Os 7 campos que pedimos ao modelo — a completude mede quantos vieram preenchidos.
_COMPLETENESS_FIELDS = (
    'summary',
    'suggested_status',
    'confidence',
    'rationale',
    'application_id',
    'intent',
    'opportunities',
)

# Histórico de execuções (uma linha por run real); artefato local, gitignorado.
HISTORY_FILE = Path(__file__).parent / 'llm_eval_history.json'


def reliability_score(checks: dict) -> float:
    """Acurácia vs gabarito (0–100): fração das checagens aplicáveis que passaram.

    ``opportunities`` só conta quando o caso esperava vagas
    (``opportunities_expected``). Os demais (intent/status/application) sempre
    contam.
    """
    applicable = ['intent', 'suggested_status', 'application']
    if checks.get('opportunities_expected'):
        applicable.append('opportunities')
    passed = sum(1 for key in applicable if checks.get(key))
    return 100.0 * passed / len(applicable)


def completeness_score(record: dict) -> float:
    """Quantos dos 7 campos pedidos a IA respondeu (0–100).

    ``confidence`` conta como respondido quando > 0; ``application_id`` quando
    não-nulo; ``opportunities`` quando a lista não está vazia; os demais quando
    a string não está vazia.
    """
    filled = 0
    for nome in _COMPLETENESS_FIELDS:
        valor = record.get(nome)
        if nome == 'confidence':
            filled += float(valor or 0) > 0
        elif nome == 'application_id':
            filled += valor is not None
        else:
            filled += bool(valor)
    return 100.0 * filled / len(_COMPLETENESS_FIELDS)


def overall_score(reliability: float, completeness: float) -> float:
    """Score combinado 0–100 (confiabilidade pondera mais que completude)."""
    return RELIABILITY_WEIGHT * reliability + COMPLETENESS_WEIGHT * completeness


def _format_mode() -> str:
    """Modo do ``format`` enviado ao Ollama: 'schema' (JSON Schema) ou 'json'."""
    try:
        from email_ingestion.classifiers.ollama import RESPONSE_FORMAT
    except ImportError:
        return 'json'
    return 'schema' if isinstance(RESPONSE_FORMAT, dict) else 'json'


# --------------------------------------------------------------------------- #
# Coletor + relatórios (impressos por conftest.pytest_terminal_summary).       #
# --------------------------------------------------------------------------- #
EXTRACTION_RESULTS: list[dict] = []
AI_RESULTS: list[dict] = []


def record_extraction(case: LlmCase, info: dict) -> None:
    EXTRACTION_RESULTS.append(
        {
            'case_id': case.id,
            'has_text': case.body_text is not None,
            'has_html': case.body_html is not None,
            **info,
        }
    )


def record_ai(case: LlmCase, email, result: ClassificationResult, checks: dict) -> None:
    AI_RESULTS.append(
        {
            'case_id': case.id,
            'malformed': False,
            'sender': email.sender,
            'subject': email.subject,
            'body': body_for_classification(email.body_text),
            'intent': result.intent,
            'expected_intent': case.expect.get('intent', ''),
            'suggested_status': result.suggested_status,
            'expected_status': case.expect.get('suggested_status', ''),
            'confidence': float(result.confidence),
            'application_id': result.application_id,
            'summary': result.summary,
            'rationale': result.rationale,
            'opportunities': [
                (o.company_name, o.role_title, o.source_url) for o in result.opportunities
            ],
            'checks': checks,
        }
    )
    registro = AI_RESULTS[-1]
    registro['reliability'] = reliability_score(checks)
    registro['completeness'] = completeness_score(registro)


def record_ai_malformed(case: LlmCase, email, message: str) -> None:
    """Registra que a IA devolveu um formato fora do schema (alucinacao)."""
    AI_RESULTS.append(
        {
            'case_id': case.id,
            'malformed': True,
            'message': message,
            'sender': email.sender,
            'subject': email.subject,
            'body': body_for_classification(email.body_text),
        }
    )


def _pct(part: int, total: int) -> str:
    return f'{(100 * part / total):.0f}%' if total else 'n/a'


def _mark(ok: bool) -> str:
    return 'OK' if ok else 'X'


def _short(text: str, limit: int = 280) -> str:
    """Texto em uma linha, truncado, para caber no relatório."""
    one_line = ' '.join((text or '').split())
    if not one_line:
        return '(vazio)'
    return one_line if len(one_line) <= limit else one_line[:limit] + ' […]'


def build_extraction_report() -> list[str]:
    if not EXTRACTION_RESULTS:
        return []
    lossy = [r for r in EXTRACTION_RESULTS if r['markers_missing']]
    lines = [
        '',
        '=== Transformacao do e-mail: o que ENTRA -> o que SAI p/ a IA ===',
        f'casos com perda de marcadores : {len(lossy)}/{len(EXTRACTION_RESULTS)}',
    ]
    for r in EXTRACTION_RESULTS:
        formato = (
            'texto+HTML' if r['has_text'] and r['has_html']
            else 'HTML' if r['has_html']
            else 'texto'
        )
        lines.append('')
        lines.append(f"[{r['case_id']}]  (entrada: {formato})")
        lines.append(f"  corpo extraido p/ IA: {_short(r['extracted_text'])}")
        if r['markers_missing']:
            lines.append(f"  PERDIDO na transformacao: {', '.join(r['markers_missing'])}")
        else:
            lines.append('  perda de informacao: nenhuma')
    return lines


def build_ai_report() -> list[str]:
    if not AI_RESULTS:
        return []
    n = len(AI_RESULTS)
    conformant = [r for r in AI_RESULTS if not r['malformed']]
    malformed = [r for r in AI_RESULTS if r['malformed']]
    intent_ok = sum(r['checks']['intent'] for r in conformant)
    status_ok = sum(r['checks']['suggested_status'] for r in conformant)
    opp_cases = [r for r in conformant if r['checks']['opportunities_expected']]
    opp_ok = sum(r['checks']['opportunities'] for r in opp_cases)
    perfect = sum(
        1
        for r in conformant
        if r['checks']['intent']
        and r['checks']['suggested_status']
        and r['checks']['application']
        and r['checks']['opportunities']
    )
    avg_conf = (
        sum(r['confidence'] for r in conformant) / len(conformant) if conformant else 0.0
    )

    lines = [
        '',
        f'=== Confiabilidade da IA (Ollama: {settings.OLLAMA_MODEL}) ===',
        f'respostas fora do schema (alucinacao): {len(malformed)}/{n}',
        f'intent           : {intent_ok}/{n}  ({_pct(intent_ok, n)})',
        f'suggested_status : {status_ok}/{n}  ({_pct(status_ok, n)})',
        f'opportunities    : {opp_ok}/{len(opp_cases)}  ({_pct(opp_ok, len(opp_cases))})',
        f'casos perfeitos  : {perfect}/{n}',
        f'confianca media  : {avg_conf:.1f}  (sobre {len(conformant)} respostas validas)',
        '',
        '--- Resposta da IA por e-mail (corpo enviado -> resultado) ---',
    ]
    for r in AI_RESULTS:
        lines.append('')
        lines.append(f"[{r['case_id']}]")
        lines.append(f"  ENVIADO -> assunto: {_short(r['subject'], 120)}")
        lines.append(f"             corpo  : {_short(r['body'])}")
        if r['malformed']:
            lines.append(f"  IA -> RESPOSTA FORA DO SCHEMA (alucinacao): {r['message']}")
            continue
        c = r['checks']
        lines.append(
            f"  IA -> intent          : {r['intent'] or '(vazio)'} "
            f"[{_mark(c['intent'])}] (esperado: {r['expected_intent'] or '(vazio)'})"
        )
        lines.append(
            f"        suggested_status: {r['suggested_status'] or '(vazio)'} "
            f"[{_mark(c['suggested_status'])}] (esperado: {r['expected_status'] or '(vazio)'})"
        )
        lines.append(f"        confianca       : {r['confidence']:.0f}")
        lines.append(f"        application_id  : {r['application_id']}")
        if r['opportunities']:
            for company, role, url in r['opportunities']:
                extra = f' <{url}>' if url else ''
                lines.append(f"        vaga            : {company} / {role}{extra}")
        else:
            lines.append('        vagas           : (nenhuma)')
        if r['summary']:
            lines.append(f"        resumo          : {_short(r['summary'])}")
        if r['rationale']:
            lines.append(f"        justificativa   : {_short(r['rationale'])}")
        lines.append(
            f"        score           : confiab. {r['reliability']:.0f} / "
            f"completude {r['completeness']:.0f}"
        )
    return lines


def summarize_run() -> dict | None:
    """Agrega ``AI_RESULTS`` num registro de execução (None se nada coletado).

    Malformadas (alucinação) entram com confiabilidade e completude 0 — não
    respondem nada útil e não acertam o gabarito.
    """
    if not AI_RESULTS:
        return None
    n = len(AI_RESULTS)
    reliabilities, completenesses = [], []
    for r in AI_RESULTS:
        if r['malformed']:
            reliabilities.append(0.0)
            completenesses.append(0.0)
        else:
            reliabilities.append(r['reliability'])
            completenesses.append(r['completeness'])
    reliability = sum(reliabilities) / n
    completeness = sum(completenesses) / n
    return {
        'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'label': os.environ.get('LLM_EVAL_LABEL', ''),
        'model': settings.OLLAMA_MODEL,
        'temperature': settings.LLM_TEMPERATURE,
        'seed': settings.LLM_SEED,
        'format_mode': _format_mode(),
        'n_cases': n,
        'malformed': sum(1 for r in AI_RESULTS if r['malformed']),
        'reliability': round(reliability, 1),
        'completeness': round(completeness, 1),
        'overall': round(overall_score(reliability, completeness), 1),
    }


def append_run_history(summary: dict) -> dict | None:
    """Anexa ``summary`` ao histórico JSON e devolve o registro ANTERIOR (p/ delta)."""
    try:
        historico = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
        if not isinstance(historico, list):
            historico = []
    except (FileNotFoundError, ValueError):
        historico = []
    previous = historico[-1] if historico else None
    historico.append(summary)
    HISTORY_FILE.write_text(
        json.dumps(historico, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return previous


def build_score_report() -> list[str]:
    """Bloco final: score desta execução + delta vs a anterior (persistido)."""
    summary = summarize_run()
    if summary is None:
        return []
    previous = append_run_history(summary)
    rotulo = f" [{summary['label']}]" if summary['label'] else ''
    lines = [
        '',
        f"=== Pontuacao desta execucao{rotulo} ===",
        f"config           : modelo={summary['model']} temp={summary['temperature']} "
        f"seed={summary['seed']} format={summary['format_mode']}",
        f"confiabilidade   : {summary['reliability']:.1f}/100  (acuracia vs gabarito)",
        f"completude       : {summary['completeness']:.1f}/100  (campos respondidos)",
        f"SCORE GERAL      : {summary['overall']:.1f}/100",
    ]
    if previous:
        delta = summary['overall'] - previous['overall']
        sinal = '+' if delta >= 0 else ''
        prev_rotulo = f" [{previous['label']}]" if previous.get('label') else ''
        lines.append(
            f"vs run anterior{prev_rotulo}: {previous['overall']:.1f} -> "
            f"{summary['overall']:.1f}  ({sinal}{delta:.1f})"
        )
    return lines
