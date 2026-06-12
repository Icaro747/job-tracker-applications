"""Classificador de e-mail via Ollama (LLM local).

Monta um contexto em portugues com o e-mail e as candidaturas abertas do dono,
pede ao modelo uma resposta JSON estruturada e a normaliza em
``ClassificationResult``. Qualquer falha (conexao, timeout, JSON invalido) vira
``ClassifierError`` para que o pipeline deixe o e-mail pendente.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

import requests
from django.conf import settings

from applications.models import JobApplication
from email_ingestion.models import EmailClassification

from .base import (
    ClassificationResult,
    ClassifierError,
    DetectedOpportunity,
    LLMClassifierAdapter,
)

# Codigos de status que o modelo pode sugerir (os mesmos da candidatura).
_VALID_STATUSES = [choice.value for choice in JobApplication.Status]
# Intencoes validas (emenda 13) — qualquer outro valor do modelo vira vazio.
_VALID_INTENTS = frozenset(EmailClassification.Intent.values)

_SYSTEM_PROMPT = (
    'Voce e um assistente que classifica e-mails de processos seletivos de '
    'emprego, escrevendo sempre em portugues do Brasil. Analise o e-mail e '
    'responda SOMENTE com um objeto JSON valido, sem texto fora dele, com as '
    'chaves: "summary" (resumo curto e claro do e-mail), "suggested_status" '
    '(uma das opcoes: {statuses}, ou string vazia se nao se aplicar), '
    '"confidence" (numero de 0 a 100), "rationale" (justificativa curta), '
    '"application_id" (o id da candidatura aberta mais provavel destinataria, '
    'ou null se nenhuma), "intent" (a intencao do e-mail, uma das opcoes: '
    '"atualizacao" = resposta de um processo existente; "nova_unica" = um '
    'recrutador direciona UMA vaga ao usuario; "lista" = newsletter/lista com '
    'VARIAS vagas, de uma ou varias empresas; "irrelevante" = nao representa '
    'processo nem vaga) e "opportunities" (lista de vagas extraidas do e-mail; '
    'cada item e um objeto com "company_name", "role_title" e "source_url"; '
    'use lista vazia para "atualizacao" e "irrelevante", um item para '
    '"nova_unica" e um item por vaga para "lista").'
)


class OllamaClassifier(LLMClassifierAdapter):
    """Conversa com o servidor Ollama local via API HTTP de chat."""

    def __init__(self, *, host=None, model=None, timeout=None):
        self.host = (host or settings.OLLAMA_HOST).rstrip('/')
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT

    # -- montagem do contexto ------------------------------------------------ #
    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT.format(statuses=', '.join(_VALID_STATUSES))

    def _user_prompt(self, email, applications: Sequence) -> str:
        if applications:
            linhas = [
                f'- id={app.pk}: {app.job.company.name} / {app.job.role_title} '
                f'(status atual: {app.get_status_display()})'
                for app in applications
            ]
            candidaturas = '\n'.join(linhas)
        else:
            candidaturas = '(nenhuma candidatura aberta)'
        return (
            f'Remetente: {email.sender}\n'
            f'Assunto: {email.subject}\n'
            f'Corpo:\n{email.body_text}\n\n'
            f'Candidaturas abertas do usuario:\n{candidaturas}'
        )

    # -- chamada ao modelo --------------------------------------------------- #
    def classify(self, email, applications: Sequence) -> ClassificationResult:
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': self._system_prompt()},
                {'role': 'user', 'content': self._user_prompt(email, applications)},
            ],
            'format': 'json',
            'stream': False,
        }
        try:
            response = requests.post(
                f'{self.host}/api/chat', json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            content = response.json()['message']['content']
            data = json.loads(content)
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise ClassifierError(f'Falha ao classificar via Ollama: {exc}') from exc

        return self._to_result(data)

    def _to_result(self, data: dict) -> ClassificationResult:
        opportunities = [
            DetectedOpportunity(
                company_name=raw.get('company_name', '') or '',
                role_title=raw.get('role_title', '') or '',
                source_url=raw.get('source_url', '') or '',
            )
            for raw in (data.get('opportunities') or [])
            if isinstance(raw, dict)
        ]

        intent = data.get('intent', '') or ''
        if intent not in _VALID_INTENTS:
            intent = ''

        try:
            confidence = float(data.get('confidence', 0) or 0)
        except (TypeError, ValueError):
            confidence = 0.0

        return ClassificationResult(
            summary=data.get('summary', '') or '',
            suggested_status=data.get('suggested_status', '') or '',
            confidence=confidence,
            rationale=data.get('rationale', '') or '',
            application_id=data.get('application_id'),
            intent=intent,
            opportunities=opportunities,
        )
