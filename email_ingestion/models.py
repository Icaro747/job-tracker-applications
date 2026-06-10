from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .fields import EncryptedTextField


def default_scan_times():
    """Padrao de varredura: uma vez por dia, a meia-noite."""
    return ['00:00']


class EmailAccount(models.Model):
    """Conta de e-mail conectada por um usuario, com credenciais de acesso.

    Privada por usuario. As credenciais OAuth (tokens) sao armazenadas aqui;
    em producao devem ser criptografadas — no dev ficam em texto plano.
    """

    class Provider(models.TextChoices):
        GMAIL = 'gmail', 'Gmail'
        OUTLOOK = 'outlook', 'Outlook / Microsoft 365'
        IMAP = 'imap', 'IMAP generico'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_accounts',
    )
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.GMAIL
    )
    email_address = models.EmailField()
    access_token = EncryptedTextField(blank=True)
    refresh_token = EncryptedTextField(blank=True)
    token_expiry = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Horarios de varredura no formato "HH:MM". Padrao: meia-noite.
    scan_times = models.JSONField(default=default_scan_times)
    last_scan_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['email_address']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'email_address'], name='unique_user_email_account'
            ),
        ]
        verbose_name = 'conta de e-mail'
        verbose_name_plural = 'contas de e-mail'

    def __str__(self):
        return f'{self.email_address} ({self.get_provider_display()})'

    def clear_credentials(self):
        """Limpa tokens e desativa a conta (usado ao desconectar)."""
        self.access_token = ''
        self.refresh_token = ''
        self.token_expiry = None
        self.is_active = False
        self.save(
            update_fields=['access_token', 'refresh_token', 'token_expiry', 'is_active']
        )


class EmailSenderRule(models.Model):
    """Filtro que define quais e-mails de uma conta devem ser capturados."""

    email_account = models.ForeignKey(
        EmailAccount, on_delete=models.CASCADE, related_name='rules'
    )
    company = models.ForeignKey(
        'applications.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_rules',
    )
    name = models.CharField(max_length=180)
    sender_email = models.EmailField(blank=True)
    sender_domain = models.CharField(max_length=180, blank=True)
    subject_keywords = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'regra de remetente'
        verbose_name_plural = 'regras de remetente'

    def __str__(self):
        target = self.sender_email or self.sender_domain or ', '.join(self.subject_keywords)
        return f'{self.name}: {target}'

    def clean(self):
        if not (self.sender_email or self.sender_domain or self.subject_keywords):
            raise ValidationError(
                'Preencha ao menos um filtro: remetente, dominio ou palavras-chave no assunto.'
            )

    def matches(self, message):
        """Implementa a logica de matching da spec 04.

        - So remetente  → captura qualquer e-mail daquele remetente/dominio.
        - So palavras-chave → captura qualquer remetente com os termos no assunto.
        - Ambos → as duas condicoes sao obrigatorias.
        """
        sender = (message.sender or '').lower()
        subject = (message.subject or '').lower()
        has_sender_filter = bool(self.sender_email or self.sender_domain)
        has_keyword_filter = bool(self.subject_keywords)

        sender_ok = not has_sender_filter
        if self.sender_email and sender == self.sender_email.lower():
            sender_ok = True
        if self.sender_domain:
            domain = self.sender_domain.lower().lstrip('@')
            if sender.endswith('@' + domain):
                sender_ok = True

        subject_ok = not has_keyword_filter
        if has_keyword_filter:
            subject_ok = any(kw.lower() in subject for kw in self.subject_keywords if kw)

        return sender_ok and subject_ok


class InboundEmail(models.Model):
    """E-mail capturado pela varredura. Um por mensagem, nunca duplicado."""

    class ProcessingStatus(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        CLASSIFIED = 'classified', 'Classificado'
        NEEDS_REVIEW = 'needs_review', 'Precisa revisao'
        IGNORED = 'ignored', 'Ignorado'

    message_id = models.CharField(max_length=255, unique=True)
    email_account = models.ForeignKey(
        EmailAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emails',
    )
    sender = models.EmailField()
    subject = models.CharField(max_length=255)
    received_at = models.DateTimeField()
    body_text = models.TextField(blank=True)
    matched_rule = models.ForeignKey(
        EmailSenderRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emails',
    )
    application = models.ForeignKey(
        'applications.JobApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emails',
    )
    processing_status = models.CharField(
        max_length=30,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    inferred_application_status = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'e-mail recebido'
        verbose_name_plural = 'e-mails recebidos'

    def __str__(self):
        return f'{self.subject} - {self.sender}'

    @property
    def provider_link(self):
        """Link best-effort para o e-mail original no provedor (Gmail).

        Usa o ``message_id`` da API do Gmail num deep-link da interface web.
        Retorna ``''`` para provedores sem link conhecido.
        """
        if self.email_account and self.email_account.provider == EmailAccount.Provider.GMAIL:
            return f'https://mail.google.com/mail/u/0/#all/{self.message_id}'
        return ''


class EmailClassification(models.Model):
    """Resultado da analise do LLM para um e-mail (preenchido na Etapa 4)."""

    email = models.OneToOneField(
        InboundEmail, on_delete=models.CASCADE, related_name='classification'
    )
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    summary = models.TextField(blank=True)
    suggested_status = models.CharField(max_length=30, blank=True)
    rationale = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_classifications',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'classificacao de e-mail'
        verbose_name_plural = 'classificacoes de e-mail'

    def __str__(self):
        return f'Classificacao: {self.email.subject}'
