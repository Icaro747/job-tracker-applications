from django.conf import settings
from django.db import models


class Company(models.Model):
    """Empresa — recurso global compartilhado por todos os usuarios."""

    name = models.CharField(max_length=180, unique=True)
    website = models.URLField(blank=True)
    careers_page = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_companies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'

    def __str__(self):
        return self.name


class CompanyAuditLog(models.Model):
    """Historico imutavel de alteracoes em empresas.

    Um registro por campo alterado (nao por operacao). Existe exclusivamente
    para empresas — nenhum outro modelo tem este nivel de rastreabilidade.
    """

    class Action(models.TextChoices):
        CREATED = 'created', 'Criado'
        UPDATED = 'updated', 'Atualizado'
        DELETED = 'deleted', 'Excluido'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='company_audit_logs',
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    field_name = models.CharField(max_length=120, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'log de auditoria de empresa'
        verbose_name_plural = 'logs de auditoria de empresa'

    def __str__(self):
        return f'{self.company} — {self.get_action_display()} ({self.field_name or "—"})'

    @classmethod
    def log_change(cls, company, user, action, field_name='', old_value='', new_value=''):
        return cls.objects.create(
            company=company,
            user=user,
            action=action,
            field_name=field_name,
            old_value='' if old_value is None else str(old_value),
            new_value='' if new_value is None else str(new_value),
        )


class Job(models.Model):
    """Vaga — recurso global. Uma posicao aberta em uma empresa."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='jobs')
    role_title = models.CharField(max_length=220)
    source_url = models.URLField(blank=True)
    location = models.CharField(max_length=160, blank=True)
    remote = models.BooleanField(default=False)
    # Vaga enviada diretamente a um usuario (ex: recrutador). Nulo = vaga publica.
    directed_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='directed_jobs',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_jobs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'vaga'
        verbose_name_plural = 'vagas'

    def __str__(self):
        return f'{self.role_title} — {self.company.name}'


class ActiveApplicationManager(models.Manager):
    """Exclui candidaturas com soft delete e as de usuarios excluidos."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(deleted_at__isnull=True, user__deleted_at__isnull=True)
        )


class JobApplication(models.Model):
    """Candidatura — processo de um usuario especifico em relacao a uma vaga."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        APPLIED = 'applied', 'Candidatura enviada'
        CONFIRMED = 'confirmed', 'Recebida pela empresa'
        SCREENING = 'screening', 'Triagem'
        INTERVIEW = 'interview', 'Entrevista'
        OFFER = 'offer', 'Oferta'
        REJECTED = 'rejected', 'Rejeitada'
        WITHDRAWN = 'withdrawn', 'Retirada'
        ARCHIVED = 'archived', 'Arquivada'

    class Origin(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        EMAIL = 'email', 'E-mail'
        EXTERNAL = 'external', 'Externo'

    class NextActionType(models.TextChoices):
        FOLLOW_UP = 'follow_up', 'Follow-up'
        INTERVIEW = 'interview', 'Entrevista'
        SEND_DOCUMENT = 'send_document', 'Enviar documento'
        AWAIT_RESPONSE = 'await_response', 'Aguardar retorno'
        OTHER = 'other', 'Outro'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='applications',
    )
    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name='applications')
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    origin = models.CharField(max_length=20, choices=Origin.choices, default=Origin.MANUAL)
    applied_at = models.DateTimeField(null=True, blank=True)
    last_status_at = models.DateTimeField(null=True, blank=True)
    next_action_at = models.DateTimeField(null=True, blank=True)
    next_action_type = models.CharField(
        max_length=30, choices=NextActionType.choices, blank=True
    )
    next_action_description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveApplicationManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'candidatura'
        verbose_name_plural = 'candidaturas'

    def __str__(self):
        return f'{self.job} ({self.get_status_display()})'


class ApplicationTimelineEntry(models.Model):
    """Linha do tempo append-only de eventos de uma candidatura."""

    class EntryType(models.TextChoices):
        MANUAL_NOTE = 'manual_note', 'Nota manual'
        EMAIL_UPDATE = 'email_update', 'Atualizacao por e-mail'
        STATUS_CHANGE = 'status_change', 'Mudanca de status'
        REMINDER = 'reminder', 'Lembrete'
        CALENDAR_EVENT = 'calendar_event', 'Evento de calendario'

    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='timeline')
    entry_type = models.CharField(max_length=30, choices=EntryType.choices)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        verbose_name = 'evento da candidatura'
        verbose_name_plural = 'eventos da candidatura'

    def __str__(self):
        return f'{self.title} ({self.application})'
