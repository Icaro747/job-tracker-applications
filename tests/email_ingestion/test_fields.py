"""Testes do EncryptedTextField — criptografia transparente dos tokens OAuth."""
from django.db import connection

from email_ingestion.models import EmailAccount
from tests.factories import EmailAccountFactory


def test_token_round_trips_as_plaintext_through_orm(db):
    """Atribuir e ler o token pelo ORM devolve o texto original."""
    account = EmailAccountFactory(access_token='meu-token', refresh_token='meu-refresh')
    recarregada = EmailAccount.objects.get(pk=account.pk)
    assert recarregada.access_token == 'meu-token'
    assert recarregada.refresh_token == 'meu-refresh'


def test_token_is_encrypted_at_rest_in_the_database(db):
    """A coluna crua no banco nao pode conter o texto plano do token."""
    account = EmailAccountFactory(access_token='segredo-secreto', refresh_token='refresh-secreto')
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT access_token, refresh_token FROM email_ingestion_emailaccount WHERE id = %s',
            [account.pk],
        )
        raw_access, raw_refresh = cursor.fetchone()
    assert 'segredo-secreto' not in (raw_access or '')
    assert 'refresh-secreto' not in (raw_refresh or '')
    # Token criptografado com Fernet comeca com o prefixo "gAAAA".
    assert raw_access.startswith('gAAAA')
    assert raw_refresh.startswith('gAAAA')


def test_empty_token_is_stored_without_encryption(db):
    """Valor vazio nao e criptografado (evita ruido em contas sem credenciais)."""
    account = EmailAccountFactory(access_token='', refresh_token='')
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT access_token, refresh_token FROM email_ingestion_emailaccount WHERE id = %s',
            [account.pk],
        )
        raw_access, raw_refresh = cursor.fetchone()
    assert raw_access == ''
    assert raw_refresh == ''
    recarregada = EmailAccount.objects.get(pk=account.pk)
    assert recarregada.access_token == ''
    assert recarregada.refresh_token == ''


def test_reads_legacy_plaintext_value_without_error(db):
    """Valor gravado em texto plano (legado) e lido sem estourar."""
    account = EmailAccountFactory(access_token='')
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE email_ingestion_emailaccount SET access_token = %s WHERE id = %s',
            ['token-legado-plano', account.pk],
        )
    recarregada = EmailAccount.objects.get(pk=account.pk)
    assert recarregada.access_token == 'token-legado-plano'
