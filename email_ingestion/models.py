from django.db import models
from django.conf import settings


class EmailSenderRule(models.Model):
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
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'regra de remetente'
        verbose_name_plural = 'regras de remetente'

    def __str__(self):
        target = self.sender_email or self.sender_domain
        return f'{self.name}: {target}'


class InboundEmail(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        CLASSIFIED = 'classified', 'Classificado'
        IGNORED = 'ignored', 'Ignorado'
        NEEDS_REVIEW = 'needs_review', 'Precisa revisao'

    message_id = models.CharField(max_length=255, unique=True)
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


class EmailClassification(models.Model):
    email = models.OneToOneField(InboundEmail, on_delete=models.CASCADE, related_name='classification')
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    summary = models.TextField(blank=True)
    suggested_status = models.CharField(max_length=30, blank=True)
    rationale = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'classificacao de e-mail'
        verbose_name_plural = 'classificacoes de e-mail'

    def __str__(self):
        return f'Classificacao: {self.email.subject}'
