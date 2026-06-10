"""Fabrica de classificadores de e-mail por LLM.

Espelha ``adapters/`` — o pipeline conhece apenas o contrato; trocar o provedor
de LLM e questao de registrar outra classe aqui.
"""
from .base import (
    ClassificationResult,
    ClassifierError,
    DetectedOpportunity,
    LLMClassifierAdapter,
)
from .ollama import OllamaClassifier

__all__ = [
    'ClassificationResult',
    'ClassifierError',
    'DetectedOpportunity',
    'LLMClassifierAdapter',
    'OllamaClassifier',
    'get_classifier',
]


def get_classifier() -> LLMClassifierAdapter:
    """Retorna o classificador de LLM configurado (Ollama por padrao)."""
    return OllamaClassifier()
