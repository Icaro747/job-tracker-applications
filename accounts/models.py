from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class ActiveUserManager(UserManager):
    """Manager padrao: exclui automaticamente usuarios com soft delete.

    Usuarios marcados com ``deleted_at`` ficam invisiveis para autenticacao,
    admin e qualquer query que use ``User.objects``. Para acessar todos os
    registros (inclusive excluidos) use ``User.all_objects``.
    """

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class User(AbstractUser):
    # Diferente do padrao Django, o e-mail e obrigatorio e unico neste sistema.
    email = models.EmailField('endereco de e-mail', unique=True)
    deleted_at = models.DateTimeField(
        'excluido em',
        null=True,
        blank=True,
        help_text='Preenchido no soft delete; nulo significa conta ativa.',
    )

    objects = ActiveUserManager()
    all_objects = UserManager()

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self, keep_global_data=False):
        """Marca a conta como excluida (soft delete).

        ``keep_global_data=False`` (Opcao A — "Excluir tudo que e meu"):
        soft delete em cascata dos dados pessoais (candidaturas, perfil) e o
        vinculo ``created_by`` de empresas/vagas vira nulo.

        ``keep_global_data=True`` (Opcao B — "Manter dados globais"):
        apenas o usuario e marcado; empresas e vagas criadas por ele
        permanecem associadas como referencia historica.
        """
        from applications.models import Company, Job, JobApplication
        from candidate_profile.models import CandidateProfile

        now = timezone.now()
        self.deleted_at = now
        self.save(update_fields=['deleted_at'])

        if keep_global_data:
            return

        JobApplication.all_objects.filter(
            user=self, deleted_at__isnull=True
        ).update(deleted_at=now)
        CandidateProfile.all_objects.filter(
            user=self, deleted_at__isnull=True
        ).update(deleted_at=now)
        Company.objects.filter(created_by=self).update(created_by=None)
        Job.objects.filter(created_by=self).update(created_by=None)
