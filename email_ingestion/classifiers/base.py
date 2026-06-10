"""Contrato comum dos classificadores de e-mail por LLM.

O sistema central nunca fala diretamente com o Ollama — sempre passa por um
classificador que respeita este contrato, exatamente como os adaptadores de
provedor de e-mail (``adapters/base.py``). Trocar o Ollama por outra LLM (Claude,
OpenAI) no futuro significa apenas uma nova subclasse, sem tocar no pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


class ClassifierError(Exception):
    """Falha ao classificar (LLM offline, timeout ou resposta invalida).

    Sinaliza ao pipeline que o e-mail deve permanecer pendente para nova
    tentativa, sem interromper o processamento dos demais.
    """


@dataclass
class DetectedOpportunity:
    """Nova oportunidade de emprego extraida de um e-mail pelo LLM."""

    company_name: str
    role_title: str
    source_url: str = ''


@dataclass
class ClassificationResult:
    """Resultado normalizado da analise de um e-mail por qualquer LLM.

    ``suggested_status`` deve ser um codigo valido de ``JobApplication.Status``
    (ou vazio); o classificador instrui o modelo a escolher entre eles, evitando
    mapeamento incerto no lado do servico.
    """

    summary: str = ''
    suggested_status: str = ''
    confidence: float = 0.0
    rationale: str = ''
    # Candidatura aberta identificada como destinataria (id) ou None.
    application_id: int | None = None
    # Quando o e-mail traz uma vaga nova (e nao atualizacao de processo existente).
    is_new_opportunity: bool = False
    opportunity: DetectedOpportunity | None = None


class LLMClassifierAdapter(ABC):
    """Interface que todo classificador de e-mail deve implementar."""

    @abstractmethod
    def classify(self, email, applications: Sequence) -> ClassificationResult:
        """Classifica ``email`` considerando as ``applications`` abertas do dono.

        Recebe um ``InboundEmail`` e a lista de candidaturas abertas (para ajudar
        a identificar a qual processo o e-mail pertence). Deve levantar
        ``ClassifierError`` em caso de falha do modelo.
        """
