"""Fase 2 — atribuicao deterministica de links as vagas detectadas.

A 1a passada (classificacao) ve o corpo SEM links e devolve as vagas
(empresa/cargo). Aqui recuperamos os links do corpo original e os atribuimos a
vaga certa por casamento de texto — sem IA, evitando alucinacao de URL.

Estrategia: cada bloco do corpo terminado em uma URL de vaga (``.../jobs/view/``)
descreve aquela vaga (cargo, empresa). Para cada vaga detectada pela IA, casamos
seu ``empresa + cargo`` com o bloco de texto mais parecido e copiamos a URL limpa.
"""
from __future__ import annotations

import quopri
import re
import unicodedata
from collections.abc import Sequence

from .body_normalization import _URL_RE, normalize_body_for_llm

# Confianca minima do casamento (fracao dos tokens da vaga presentes no bloco).
# URLs de ruido (ex.: "gerenciar alertas") nao casam com nenhuma vaga e ficam de
# fora naturalmente — por isso nao filtramos por formato de URL (funciona tanto
# para o LinkedIn quanto para links de vaga genericos).
_MATCH_THRESHOLD = 0.4


def clean_url(token: str) -> str:
    """Reconstroi a URL real: decodifica quoted-printable e junta soft breaks."""
    return quopri.decodestring(token.encode('utf-8')).decode('utf-8', 'replace').strip()


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize('NFKD', text.lower())
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r'\w+', _strip_accents(text)) if len(t) > 2]


def _similarity(needle: str, block: str) -> float:
    """Fracao dos tokens significativos de ``needle`` presentes em ``block``."""
    tokens = _tokens(needle)
    if not tokens:
        return 0.0
    block_norm = _strip_accents(block)
    hits = sum(1 for t in tokens if t in block_norm)
    return hits / len(tokens)


def extract_job_blocks(raw_body: str) -> list[dict]:
    """Blocos de vaga do corpo: ``[{'text': <descricao>, 'url': <url limpa>}]``.

    Cada bloco e o texto que antecede uma URL de vaga individual.
    """
    normalized = normalize_body_for_llm(raw_body)
    blocks: list[dict] = []
    cursor = 0
    for match in _URL_RE.finditer(normalized):
        url = clean_url(match.group(0))
        blocks.append({'text': normalized[cursor:match.start()], 'url': url})
        cursor = match.end()
    return blocks


def attribute_source_urls(
    opportunities: Sequence, raw_body: str, threshold: float = _MATCH_THRESHOLD
) -> Sequence:
    """Preenche ``source_url`` de cada vaga com o link casado no corpo.

    URLs que a IA tenha inventado sao descartadas: confiamos apenas no casamento
    deterministico. Cada bloco e usado no maximo uma vez.
    """
    blocks = extract_job_blocks(raw_body)
    used: set[int] = set()
    for opp in opportunities:
        needle = f'{opp.company_name} {opp.role_title}'
        best_idx, best_score = None, threshold
        for i, block in enumerate(blocks):
            if i in used:
                continue
            score = _similarity(needle, block['text'])
            if score >= best_score:
                best_idx, best_score = i, score
        if best_idx is not None:
            opp.source_url = blocks[best_idx]['url']
            used.add(best_idx)
        else:
            opp.source_url = ''  # descarta link alucinado / sem correspondencia
    return opportunities
