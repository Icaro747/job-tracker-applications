from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


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

    def get_absolute_url(self):
        return reverse('applications:company_detail', args=[self.pk])


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

    # Campos da empresa rastreados pela auditoria de edicao.
    AUDITED_FIELDS = ('name', 'website', 'careers_page', 'notes')

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

    @classmethod
    def record_create(cls, company, user):
        """Registra a criacao da empresa (um unico log)."""
        return cls.log_change(company, user, cls.Action.CREATED)

    @classmethod
    def record_update(cls, company, user, old_values):
        """Registra a edicao: um log por campo alterado.

        ``old_values`` e um dict {campo: valor_antigo} capturado antes do save.
        Campos sem alteracao nao geram registro.
        """
        logs = []
        for field in cls.AUDITED_FIELDS:
            if field not in old_values:
                continue
            old = old_values[field]
            new = getattr(company, field)
            if old != new:
                logs.append(
                    cls.log_change(
                        company,
                        user,
                        cls.Action.UPDATED,
                        field_name=field,
                        old_value=old,
                        new_value=new,
                    )
                )
        return logs

    @classmethod
    def record_delete(cls, company, user):
        """Registra a exclusao da empresa (um unico log)."""
        return cls.log_change(company, user, cls.Action.DELETED)


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

    def get_absolute_url(self):
        return reverse('applications:job_detail', args=[self.pk])


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

    def get_absolute_url(self):
        return reverse('applications:application_detail', args=[self.pk])

    @property
    def next_action_overdue(self):
        """True quando ha proxima acao agendada com data ja vencida."""
        return self.next_action_at is not None and self.next_action_at < timezone.now()

    def change_status(self, new_status, *, occurred_at=None):
        """Avanca o status, carimba ``last_status_at`` e registra na timeline.

        No-op quando o status nao muda. Ao entrar em ``applied`` pela primeira
        vez, preenche ``applied_at``.
        """
        if new_status == self.status:
            return None

        old_label = self.get_status_display()
        now = occurred_at or timezone.now()
        self.status = new_status
        self.last_status_at = now
        if new_status == self.Status.APPLIED and self.applied_at is None:
            self.applied_at = now
        self.save(update_fields=['status', 'last_status_at', 'applied_at', 'updated_at'])

        return ApplicationTimelineEntry.objects.create(
            application=self,
            entry_type=ApplicationTimelineEntry.EntryType.STATUS_CHANGE,
            title=f'Status: {old_label} → {self.get_status_display()}',
            description='',
            occurred_at=now,
        )

    def set_next_action(self, *, at, action_type, description=''):
        """Define a proxima acao programada da candidatura."""
        self.next_action_at = at
        self.next_action_type = action_type
        self.next_action_description = description
        self.save(
            update_fields=[
                'next_action_at',
                'next_action_type',
                'next_action_description',
                'updated_at',
            ]
        )

    def complete_next_action(self, *, note=''):
        """Conclui a proxima acao: registra na timeline e limpa os campos."""
        action_label = self.get_next_action_type_display() if self.next_action_type else ''
        title = 'Proxima acao concluida'
        if action_label:
            title = f'{title}: {action_label}'
        entry = ApplicationTimelineEntry.objects.create(
            application=self,
            entry_type=ApplicationTimelineEntry.EntryType.REMINDER,
            title=title,
            description=note,
            occurred_at=timezone.now(),
        )
        self.next_action_at = None
        self.next_action_type = ''
        self.next_action_description = ''
        self.save(
            update_fields=[
                'next_action_at',
                'next_action_type',
                'next_action_description',
                'updated_at',
            ]
        )
        return entry

    def add_note(self, text, *, occurred_at=None):
        """Adiciona uma nota manual a linha do tempo."""
        return ApplicationTimelineEntry.objects.create(
            application=self,
            entry_type=ApplicationTimelineEntry.EntryType.MANUAL_NOTE,
            title='Nota manual',
            description=text,
            occurred_at=occurred_at or timezone.now(),
        )

    def register_email_update(self, *, email, new_status='', summary=''):
        """Registra uma atualizacao vinda de e-mail na linha do tempo.

        Cria uma entrada ``email_update`` (origem da atualizacao) e, quando
        ``new_status`` e um status valido e diferente do atual, avanca o status
        (o que gera a propria entrada ``status_change``). Retorna a entrada
        ``email_update`` criada.
        """
        entry = ApplicationTimelineEntry.objects.create(
            application=self,
            entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE,
            title=f'E-mail: {email.subject}',
            description=summary,
            occurred_at=email.received_at,
        )
        if new_status and new_status in self.Status.values and new_status != self.status:
            self.change_status(new_status, occurred_at=email.received_at)
        return entry


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
