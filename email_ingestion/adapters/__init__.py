"""Fabrica de adaptadores de provedor de e-mail."""
from .base import EmailProviderAdapter, FetchedMessage
from .gmail import GmailAdapter

__all__ = ['EmailProviderAdapter', 'FetchedMessage', 'GmailAdapter', 'get_adapter']

_ADAPTERS = {
    'gmail': GmailAdapter,
}


def get_adapter(account) -> EmailProviderAdapter:
    """Retorna o adaptador correspondente ao provedor da conta."""
    try:
        adapter_cls = _ADAPTERS[account.provider]
    except KeyError:
        raise NotImplementedError(
            f'Provedor sem adaptador implementado: {account.provider}'
        ) from None
    return adapter_cls(account)
