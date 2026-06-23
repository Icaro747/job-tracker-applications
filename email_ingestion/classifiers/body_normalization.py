"""Normalizacao do corpo antes de enviar ao LLM."""
from __future__ import annotations

import quopri
import re

_URL_RE = re.compile(r'https?://(?:=\r?\n[ \t]*|[^\s])+')


def _decode_text_segment(text: str) -> str:
    """Decodifica quoted-printable somente em trechos que nao sao URL."""
    if not text:
        return ''
    return quopri.decodestring(text.encode('utf-8')).decode(
        'utf-8', errors='replace'
    )


def normalize_body_for_llm(raw: str) -> str:
    """Normaliza o corpo do e-mail preservando URLs literalmente.

    Alguns corpos em texto chegam com codificacao quoted-printable ainda visivel
    (por exemplo ``S=C3=A3o Paulo``). URLs tambem podem conter sequencias como
    ``=3D`` em parametros de tracking; por isso elas sao mantidas intocadas.
    """
    if not raw:
        return ''

    parts: list[str] = []
    cursor = 0
    for match in _URL_RE.finditer(raw):
        parts.append(_decode_text_segment(raw[cursor:match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(_decode_text_segment(raw[cursor:]))
    return ''.join(parts)


_BLANK_LINES_RE = re.compile(r'\n[ \t]*\n[ \t]*(?:\n[ \t]*)+')
_INLINE_SPACES_RE = re.compile(r'[ \t]{2,}')
_REPEATED_DIVIDER_RE = re.compile(r"([\-_=*~])\1{3,}")

def body_for_classification(raw: str, max_chars: int = 4000) -> str:
    """Corpo enxuto para a 1a passada de classificacao pelo LLM.

    Diferente de :func:`normalize_body_for_llm` (que preserva URLs para etapas
    posteriores), aqui **removemos os links** e o ruido: alertas de vaga como os
    do LinkedIn trazem URLs de tracking enormes que afogam o conteudo e fazem o
    modelo se perder. A 1a passada precisa apenas do texto (empresa, cargo,
    intencao); os links sao recuperados depois (Fase 2).

    Passos: decodifica quoted-printable (via ``normalize_body_for_llm``), remove
    as URLs, colapsa espacos/linhas em branco e trunca em ``max_chars``.
    """
    text = _URL_RE.sub(' ', normalize_body_for_llm(raw))
    text = '\n'.join(line.strip() for line in text.splitlines())

    text = _limit_repeated_dividers(text)

    text = _BLANK_LINES_RE.sub('\n\n', text)
    text = _INLINE_SPACES_RE.sub(' ', text).strip()

    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + ' […]'
    return text

def _limit_repeated_dividers(text: str) -> str:
    """Reduz divisórias repetidas para no máximo 3 caracteres.

    Exemplo:
    -------------------- -> ---
    ==================== -> ===
    ******************** -> ***
    """
    return _REPEATED_DIVIDER_RE.sub(r"\1\1\1", text)