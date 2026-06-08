from django.db import models
from django.conf import settings


class ActiveProfileManager(models.Manager):
    """Exclui perfis com soft delete e os de usuarios excluidos."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(deleted_at__isnull=True, user__deleted_at__isnull=True)
        )


class CandidateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidate_profile')
    full_name = models.CharField(max_length=180)
    headline = models.CharField(max_length=220, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    location = models.CharField(max_length=160, blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    summary = models.TextField(blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveProfileManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'perfil do candidato'
        verbose_name_plural = 'perfis dos candidatos'

    def __str__(self):
        return self.full_name


class Experience(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='experiences')
    company = models.CharField(max_length=180)
    title = models.CharField(max_length=180)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'experiencia'
        verbose_name_plural = 'experiencias'

    def __str__(self):
        return f'{self.title} - {self.company}'


class Education(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='education')
    institution = models.CharField(max_length=180)
    course = models.CharField(max_length=180)
    degree = models.CharField(max_length=120, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-end_date', '-start_date']
        verbose_name = 'formacao'
        verbose_name_plural = 'formacoes'

    def __str__(self):
        return f'{self.course} - {self.institution}'


class Skill(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=120)
    level = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'competencia'
        verbose_name_plural = 'competencias'

    def __str__(self):
        return self.name


class SavedAnswer(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='saved_answers')
    key = models.SlugField(max_length=120)
    label = models.CharField(max_length=180)
    answer = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']
        unique_together = [('profile', 'key')]
        verbose_name = 'resposta salva'
        verbose_name_plural = 'respostas salvas'

    def __str__(self):
        return self.label
