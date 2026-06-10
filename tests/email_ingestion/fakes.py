"""Adaptador fake para testar o pipeline sem chamar o Google."""
from email_ingestion.adapters.base import EmailProviderAdapter, FetchedMessage
from email_ingestion.classifiers.base import (
    ClassificationResult,
    ClassifierError,
    LLMClassifierAdapter,
)


def make_message(message_id='msg-1', sender='rh@empresa.com', subject='Assunto', **kwargs):
    """Atalho para criar uma FetchedMessage com defaults sensatos."""
    from django.utils import timezone

    return FetchedMessage(
        message_id=message_id,
        sender=sender,
        subject=subject,
        received_at=kwargs.get('received_at', timezone.now()),
        body_text=kwargs.get('body_text', ''),
    )


class FakeAdapter(EmailProviderAdapter):
    def __init__(self, account, messages=None):
        super().__init__(account)
        self.messages = list(messages or [])
        self.authenticated = False
        self.revoked = False
        self.since = None

    def authenticate(self):
        self.authenticated = True

    def fetch_messages(self, since):
        self.since = since
        return list(self.messages)

    def revoke(self):
        self.revoked = True
        self.account.clear_credentials()


class FakeClassifier(LLMClassifierAdapter):
    """Classificador de LLM fake — devolve um resultado canonico sem rede.

    Passe ``result`` para controlar a saida, ou ``error=True`` para simular a
    indisponibilidade do Ollama (levanta ``ClassifierError``).
    """

    def __init__(self, result=None, *, error=False):
        self.result = result or ClassificationResult()
        self.error = error
        self.calls = []

    def classify(self, email, applications):
        self.calls.append((email, list(applications)))
        if self.error:
            raise ClassifierError('Ollama indisponivel (fake)')
        return self.result
