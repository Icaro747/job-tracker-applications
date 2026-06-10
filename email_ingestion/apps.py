from django.apps import AppConfig


class EmailIngestionConfig(AppConfig):
    name = 'email_ingestion'

    def ready(self):
        from .diagnostics import should_run_startup_diagnostics, run_startup_diagnostics

        if should_run_startup_diagnostics():
            run_startup_diagnostics()
