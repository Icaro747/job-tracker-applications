"""Executa diagnosticos locais das integracoes externas."""
from django.core.management.base import BaseCommand

from email_ingestion.diagnostics import run_diagnostics


class Command(BaseCommand):
    help = 'Verifica o estado local das integracoes Gmail e Ollama.'

    def handle(self, *args, **options):
        for result in run_diagnostics():
            self.stdout.write(f'[{result.status}] {result.component}: {result.message}')
            for detail in result.details:
                self.stdout.write(f'  - {detail}')
