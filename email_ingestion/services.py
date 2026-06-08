"""Fila 1 — Varredura.

Captura e-mails novos de cada conta ativa, aplica as regras de filtragem e
registra os que passam como ``InboundEmail`` pendentes. Implementado como
servico sincrono e testavel; o agendamento periodico (Django Q2) chega na
Etapa 5. O enfileiramento na Fila 2 (classificacao LLM) e um gancho da Etapa 4.
"""
from __future__ import annotations

from django.utils import timezone

from .adapters import get_adapter
from .models import EmailAccount, InboundEmail


def enqueue_classification(email: InboundEmail) -> None:
    """Gancho da Fila 2 (classificacao LLM) — implementado na Etapa 4."""
    # No-op por enquanto. Mantido para fixar o ponto de integracao Fila 1 → Fila 2.
    return None


def scan_account(account: EmailAccount, adapter=None) -> list[InboundEmail]:
    """Varre uma conta: autentica, busca novas mensagens, filtra e registra.

    Deduplicacao por ``message_id`` (unico no sistema). Apos varrer, carimba
    ``last_scan_at`` para que a proxima execucao busque so o que chegou depois.
    """
    adapter = adapter or get_adapter(account)
    adapter.authenticate()
    rules = list(account.rules.filter(is_active=True))

    created: list[InboundEmail] = []
    for message in adapter.fetch_messages(since=account.last_scan_at):
        if InboundEmail.objects.filter(message_id=message.message_id).exists():
            continue  # deduplicacao: nunca registra a mesma mensagem duas vezes
        matched_rule = next((rule for rule in rules if rule.matches(message)), None)
        if matched_rule is None:
            continue
        email = InboundEmail.objects.create(
            message_id=message.message_id,
            email_account=account,
            sender=message.sender,
            subject=message.subject,
            received_at=message.received_at,
            body_text=message.body_text,
            matched_rule=matched_rule,
            processing_status=InboundEmail.ProcessingStatus.PENDING,
        )
        created.append(email)
        enqueue_classification(email)

    account.last_scan_at = timezone.now()
    account.save(update_fields=['last_scan_at'])
    return created


def scan_all_active_accounts() -> dict[int, list[InboundEmail]]:
    """Varre todas as contas ativas. Retorna {account_id: e-mails criados}."""
    results: dict[int, list[InboundEmail]] = {}
    for account in EmailAccount.objects.filter(is_active=True):
        results[account.pk] = scan_account(account)
    return results
