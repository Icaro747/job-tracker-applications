"""Utilidades de proveniencia/duplicacao (Fatia 4).

A deteccao de duplicatas e *normalizada* e *nao bloqueante*: serve para alertar
o usuario e oferecer reuso, nunca para impedir a criacao.
"""
import re

from .models import Company, Job

# Sufixos societarios comuns ignorados na comparacao de nomes de empresa.
_CORPORATE_SUFFIXES = {
    'inc', 'ltda', 'ltd', 'llc', 'sa', 'me', 'epp', 'eireli',
    'co', 'corp', 'company', 'gmbh', 'ag', 'plc',
}


def normalize_name(value: str) -> str:
    """Normaliza um nome para comparacao de duplicatas.

    Minusculas, remove pontuacao (S.A. -> sa), colapsa espacos e descarta
    sufixos societarios comuns.
    """
    text = (value or '').lower().replace('.', '')
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = [t for t in text.split() if t not in _CORPORATE_SUFFIXES]
    return ' '.join(tokens)


def find_duplicate_company(name: str, exclude_pk=None) -> Company | None:
    """Empresa existente cujo nome normalizado coincide com ``name``."""
    target = normalize_name(name)
    if not target:
        return None
    qs = Company.objects.all()
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    for company in qs:
        if normalize_name(company.name) == target:
            return company
    return None


def find_duplicate_job(company, role_title: str) -> Job | None:
    """Vaga existente da mesma empresa com titulo normalizado coincidente."""
    target = normalize_name(role_title)
    if not target or company is None:
        return None
    for job in Job.objects.filter(company=company):
        if normalize_name(job.role_title) == target:
            return job
    return None
