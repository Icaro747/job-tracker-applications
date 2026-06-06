from django.db import models
from django.conf import settings


class ApplicationReminder(models.Model):
    class Channel(models.TextChoices):
        APP = 'app', 'Aplicacao'
        EMAIL = 'email', 'E-mail'
        CALENDAR = 'calendar', 'Calendario'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        SENT = 'sent', 'Enviado'
        DISMISSED = 'dismissed', 'Dispensado'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='application_reminders')
    application = models.ForeignKey('applications.JobApplication', on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField()
    channel = models.CharField(max_length=30, choices=Channel.choices, default=Channel.APP)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_at']
        verbose_name = 'lembrete de candidatura'
        verbose_name_plural = 'lembretes de candidatura'

    def __str__(self):
        return f'{self.title} - {self.application}'


class CalendarEvent(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        SCHEDULED = 'scheduled', 'Agendado'
        CANCELED = 'canceled', 'Cancelado'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='calendar_events')
    application = models.ForeignKey('applications.JobApplication', on_delete=models.CASCADE, related_name='calendar_events')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    external_calendar_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at']
        verbose_name = 'evento de calendario'
        verbose_name_plural = 'eventos de calendario'

    def __str__(self):
        return self.title
