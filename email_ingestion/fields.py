"""Campo de modelo com criptografia transparente em repouso.

Usado para os tokens OAuth (``access_token``/``refresh_token``): o valor trafega
em texto plano pelo ORM, mas e gravado criptografado (Fernet) no banco. A chave
vem de ``settings.FIELD_ENCRYPTION_KEY``.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """Instancia o Fernet uma unica vez a partir da chave configurada."""
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


class EncryptedTextField(models.TextField):
    """TextField que criptografa o conteudo ao salvar e descriptografa ao ler.

    Valor vazio nao e criptografado. Valores legados em texto plano (gravados
    antes da adocao deste campo) sao tolerados na leitura — se a string nao for
    um token Fernet valido, e devolvida como esta.
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == '':
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Valor legado em texto plano (anterior a criptografia).
            return value
