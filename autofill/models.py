from django.db import models
from django.conf import settings


class AutofillFieldMapping(models.Model):
    site_domain = models.CharField(max_length=180)
    field_label = models.CharField(max_length=180)
    field_name = models.CharField(max_length=180, blank=True)
    profile_source = models.CharField(
        max_length=180,
        help_text='Exemplo: candidate_profile.full_name ou saved_answer.cover_letter.',
    )
    fallback_value = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['site_domain', 'field_label']
        unique_together = [('site_domain', 'field_label', 'field_name')]
        verbose_name = 'mapeamento de campo'
        verbose_name_plural = 'mapeamentos de campo'

    def __str__(self):
        return f'{self.site_domain}: {self.field_label}'


class AutofillSuggestion(models.Model):
    class Status(models.TextChoices):
        SUGGESTED = 'suggested', 'Sugerido'
        ACCEPTED = 'accepted', 'Aceito'
        REJECTED = 'rejected', 'Rejeitado'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='autofill_suggestions')
    application = models.ForeignKey(
        'applications.JobApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='autofill_suggestions',
    )
    site_domain = models.CharField(max_length=180)
    field_label = models.CharField(max_length=180)
    field_name = models.CharField(max_length=180, blank=True)
    suggested_value = models.TextField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUGGESTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'sugestao de preenchimento'
        verbose_name_plural = 'sugestoes de preenchimento'

    def __str__(self):
        return f'{self.field_label} em {self.site_domain}'
