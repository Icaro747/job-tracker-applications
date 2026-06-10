"""Contrato comum de adaptadores de provedor de e-mail.

O sistema central nunca fala diretamente com Gmail/IMAP — sempre passa por um
adaptador que respeita este contrato. Adicionar um provedor novo no futuro
significa apenas criar uma subclasse, sem tocar no pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FetchedMessage:
    """Mensagem normalizada retornada por qualquer adaptador.

    A filtragem por regras acontece no pipeline (services), nao aqui — o
    adaptador apenas busca mensagens novas desde um instante.
    """

    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str = ''


class EmailProviderAdapter(ABC):
    """Interface que todo provedor de e-mail deve implementar."""

    def __init__(self, account):
        self.account = account

    @abstractmethod
    def authenticate(self) -> None:
        """Autentica com o provedor usando as credenciais da conta."""

    @abstractmethod
    def fetch_messages(self, since: datetime | None) -> Iterable[FetchedMessage]:
        """Busca mensagens recebidas apos ``since`` (ou todas, se ``None``)."""

    @abstractmethod
    def revoke(self) -> bool:
        """Revoga o acesso e limpa as credenciais (desconectar a conta).

        Retorna ``True`` se a revogacao remota foi confirmada (ou nao havia o
        que revogar) e ``False`` se a chamada ao provedor falhou — nesse caso a
        concessao pode seguir ativa no provedor, ainda que as credenciais locais
        tenham sido limpas.
        """
