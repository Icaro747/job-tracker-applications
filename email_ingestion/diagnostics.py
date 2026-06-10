"""Diagnosticos locais das integracoes de e-mail e LLM.

As verificacoes retornam estado estruturado para views, comandos e startup.
Nenhuma falha deve impedir a aplicacao de subir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
import sys

import requests
from django.conf import settings

from .models import EmailAccount

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    component: str
    status: str
    message: str
    details: list[str] = field(default_factory=list)


def diagnose_ollama() -> DiagnosticResult:
    """Verifica se a API local do Ollama responde e possui o modelo configurado."""
    host = settings.OLLAMA_HOST.rstrip('/')
    model = settings.OLLAMA_MODEL
    try:
        response = requests.get(f'{host}/api/tags', timeout=3)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return DiagnosticResult(
            component='ollama',
            status='error',
            message='Ollama indisponivel.',
            details=[f'Nao foi possivel consultar {host}/api/tags: {exc}'],
        )

    raw_models = payload.get('models')
    if not isinstance(raw_models, list):
        return DiagnosticResult(
            component='ollama',
            status='error',
            message='Resposta inesperada do Ollama.',
            details=['A API nao retornou a lista "models".'],
        )

    model_names = [item.get('name', '') for item in raw_models if isinstance(item, dict)]
    configured = {model, f'{model}:latest'}
    if any(name in configured for name in model_names):
        return DiagnosticResult(
            component='ollama',
            status='ok',
            message=f'Ollama conectado com o modelo {model}.',
            details=[f'Modelos disponiveis: {", ".join(model_names) or "nenhum"}'],
        )

    return DiagnosticResult(
        component='ollama',
        status='warning',
        message=f'Ollama conectado, mas o modelo {model} nao foi encontrado.',
        details=[
            f'Modelos disponiveis: {", ".join(model_names) or "nenhum"}',
            f'Baixe com: ollama pull {model}',
        ],
    )


def diagnose_gmail(*, user=None) -> DiagnosticResult:
    """Verifica configuracao local do Gmail sem chamar a API do Google."""
    details: list[str] = []
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        details.append('GOOGLE_OAUTH_CLIENT_ID nao configurado.')
    if not settings.GOOGLE_OAUTH_CLIENT_SECRET:
        details.append('GOOGLE_OAUTH_CLIENT_SECRET nao configurado.')
    if details:
        return DiagnosticResult(
            component='gmail',
            status='error',
            message='Configuracao OAuth do Gmail incompleta.',
            details=details,
        )

    accounts = EmailAccount.objects.filter(provider=EmailAccount.Provider.GMAIL)
    if user is not None:
        accounts = accounts.filter(user=user)
    active_accounts = accounts.filter(is_active=True)

    warnings: list[str] = []
    if not active_accounts.exists():
        warnings.append('Nenhuma conta Gmail ativa encontrada.')
    else:
        without_token = active_accounts.filter(access_token='', refresh_token='').count()
        without_rules = sum(
            1 for account in active_accounts if not account.rules.filter(is_active=True).exists()
        )
        never_scanned = active_accounts.filter(last_scan_at__isnull=True).count()
        if without_token:
            warnings.append(f'{without_token} conta(s) ativa(s) sem token local.')
        if without_rules:
            warnings.append(f'{without_rules} conta(s) ativa(s) sem regra ativa.')
        if never_scanned:
            warnings.append(f'{never_scanned} conta(s) ativa(s) ainda sem varredura.')

    if warnings:
        return DiagnosticResult(
            component='gmail',
            status='warning',
            message='Gmail configurado, mas requer atencao.',
            details=warnings,
        )

    return DiagnosticResult(
        component='gmail',
        status='ok',
        message='Gmail configurado com conta ativa, token e regra.',
        details=[
            f'Contas ativas: {active_accounts.count()}',
            *[account.email_address for account in active_accounts],
        ],
    )


def run_diagnostics(*, user=None) -> list[DiagnosticResult]:
    """Executa os diagnosticos principais."""
    return [diagnose_gmail(user=user), diagnose_ollama()]


def should_run_startup_diagnostics(argv=None, environ=None) -> bool:
    """Evita diagnostico em migrate/testes e duplicidade no autoreload."""
    argv = argv if argv is not None else sys.argv
    environ = environ if environ is not None else os.environ
    if not any(arg.endswith('runserver') for arg in argv):
        return False
    return environ.get('RUN_MAIN') == 'true' or '--noreload' in argv


def run_startup_diagnostics() -> None:
    """Registra o estado das integracoes sem bloquear o startup."""
    try:
        for result in run_diagnostics():
            message = (
                f'Diagnostico de startup: {result.component} '
                f'{result.status} - {result.message}'
            )
            if result.status == 'ok':
                logger.info(message)
            else:
                logger.warning(message)
    except Exception:  # noqa: BLE001 - diagnostico nao pode impedir startup
        logger.exception('Falha inesperada ao executar diagnostico de startup.')
