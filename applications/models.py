from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=180, unique=True)
    website = models.URLField(blank=True)
    careers_page = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'

    def __str__(self):
        return self.name


class JobApplication(models.Model):
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

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='applications')
    role_title = models.CharField(max_length=220)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    source_url = models.URLField(blank=True)
    location = models.CharField(max_length=160, blank=True)
    remote = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)
    last_status_at = models.DateTimeField(null=True, blank=True)
    next_action_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'candidatura'
        verbose_name_plural = 'candidaturas'

    def __str__(self):
        return f'{self.role_title} - {self.company.name}'


class ApplicationTimelineEntry(models.Model):
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
