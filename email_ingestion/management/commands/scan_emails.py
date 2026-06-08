"""Dispara a Fila 1 (varredura) manualmente.

    python manage.py scan_emails            # todas as contas ativas
    python manage.py scan_emails --account 3  # apenas a conta de id 3

Na Etapa 5 esta mesma logica sera agendada via Django Q2.
"""
from django.core.management.base import BaseCommand, CommandError

from email_ingestion.models import EmailAccount
from email_ingestion.services import scan_account, scan_all_active_accounts


class Command(BaseCommand):
    help = 'Varre as contas de e-mail ativas e registra os e-mails capturados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account',
            type=int,
            default=None,
            help='ID de uma conta especifica a varrer (em vez de todas as ativas).',
        )

    def handle(self, *args, **options):
        account_id = options['account']
        if account_id is not None:
            try:
                account = EmailAccount.objects.get(pk=account_id)
            except EmailAccount.DoesNotExist as exc:
                raise CommandError(f'Conta {account_id} nao encontrada.') from exc
            results = {account.pk: scan_account(account)}
        else:
            results = scan_all_active_accounts()

        total = sum(len(emails) for emails in results.values())
        self.stdout.write(
            self.style.SUCCESS(
                f'Varredura concluida: {len(results)} conta(s), {total} e-mail(s) capturado(s).'
            )
        )
