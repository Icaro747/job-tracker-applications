"""Adaptador Gmail (OAuth2 via Google API).

Implementa o contrato ``EmailProviderAdapter`` usando a Gmail API. As chamadas
reais ao Google nao sao exercitadas em testes unitarios — o pipeline e testado
com um adaptador fake. Aqui mora a integracao concreta.
"""
from __future__ import annotations

import base64
from collections.abc import Iterable
from datetime import datetime
from datetime import timezone as dt_timezone
from email.utils import parseaddr

from django.conf import settings
from django.utils import timezone

from .base import EmailProviderAdapter, FetchedMessage

GMAIL_TOKEN_URI = 'https://oauth2.googleapis.com/token'
GMAIL_REVOKE_URI = 'https://oauth2.googleapis.com/revoke'


class GmailAdapter(EmailProviderAdapter):
    def __init__(self, account):
        super().__init__(account)
        self._service = None

    # -- autenticacao ------------------------------------------------------- #
    def _build_credentials(self):
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=self.account.access_token or None,
            refresh_token=self.account.refresh_token or None,
            token_uri=GMAIL_TOKEN_URI,
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=settings.GMAIL_OAUTH_SCOPES,
        )

    def authenticate(self) -> None:
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = self._build_credentials()
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            self.account.access_token = creds.token or ''
            if creds.expiry is not None:
                self.account.token_expiry = creds.expiry.replace(tzinfo=dt_timezone.utc)
            self.account.save(update_fields=['access_token', 'token_expiry'])
        self._service = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    # -- leitura ------------------------------------------------------------ #
    def fetch_messages(self, since: datetime | None) -> Iterable[FetchedMessage]:
        if self._service is None:
            self.authenticate()
        query = f'after:{int(since.timestamp())}' if since is not None else ''
        response = (
            self._service.users().messages().list(userId='me', q=query).execute()
        )
        results = []
        for ref in response.get('messages', []):
            full = (
                self._service.users()
                .messages()
                .get(userId='me', id=ref['id'], format='full')
                .execute()
            )
            results.append(self._parse_message(full))
        return results

    @staticmethod
    def _parse_message(msg: dict) -> FetchedMessage:
        payload = msg.get('payload', {})
        headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
        _, sender = parseaddr(headers.get('from', ''))
        internal = msg.get('internalDate')
        if internal:
            received_at = datetime.fromtimestamp(int(internal) / 1000, tz=dt_timezone.utc)
        else:
            received_at = timezone.now()
        return FetchedMessage(
            message_id=msg['id'],
            sender=sender,
            subject=headers.get('subject', ''),
            received_at=received_at,
            body_text=GmailAdapter._extract_body(payload),
        )

    @staticmethod
    def _extract_body(payload: dict) -> str:
        data = payload.get('body', {}).get('data')
        if payload.get('mimeType') == 'text/plain' and data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        for part in payload.get('parts', []) or []:
            text = GmailAdapter._extract_body(part)
            if text:
                return text
        return ''

    # -- revogacao ---------------------------------------------------------- #
    def revoke(self) -> bool:
        import logging

        import requests

        remote_ok = True
        token = self.account.refresh_token or self.account.access_token
        if token:
            try:
                response = requests.post(
                    GMAIL_REVOKE_URI, params={'token': token}, timeout=10
                )
                response.raise_for_status()
            except requests.RequestException:
                remote_ok = False
                logging.getLogger(__name__).warning(
                    'Falha ao revogar o token no Google para a conta %s; '
                    'credenciais locais limpas, mas a concessao pode seguir ativa.',
                    self.account.email_address,
                )
        self.account.clear_credentials()
        return remote_ok
