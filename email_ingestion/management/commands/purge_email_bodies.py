"""Expurga o corpo de e-mails antigos ja processados (minimizacao de dados).

    python manage.py purge_email_bodies            # limpa corpos com mais de 90 dias
    python manage.py purge_email_bodies --days 30  # usa outro limite

So afeta e-mails ja processados (status != pendente): o assunto/remetente e o
vinculo com a candidatura sao mantidos; apenas o ``body_text`` integral e
descartado. Na Etapa 5 deve rodar periodicamente via Django Q2.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from email_ingestion.models import InboundEmail

DEFAULT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = 'Limpa o corpo de e-mails ja processados mais antigos que N dias.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=f'Idade minima (em dias) para expurgo. Padrao: {DEFAULT_RETENTION_DAYS}.',
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['days'])
        alvos = (
            InboundEmail.objects.filter(received_at__lt=cutoff)
            .exclude(processing_status=InboundEmail.ProcessingStatus.PENDING)
            .exclude(body_text='')
        )
        total = alvos.update(body_text='')
        self.stdout.write(
            self.style.SUCCESS(f'Corpo expurgado de {total} e-mail(s).')
        )
