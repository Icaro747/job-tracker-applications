"""Reabre na fila de revisao os e-mails auto-classificados pelo comportamento antigo.

Ate a Fatia 1 da Etapa 4, a classificacao de alta confianca aplicava status e
criava Empresa/Vaga/Candidatura sozinha, deixando o e-mail em ``classified`` sem
nunca preencher ``classification.reviewed_at`` (a confirmacao manual sempre
preenche). Esse par — ``processing_status = classified`` + ``reviewed_at`` nulo —
identifica com seguranca o legado automatico.

A migracao devolve esses e-mails para ``needs_review`` para que o usuario confirme.
Nada e revertido: status ja aplicados e rascunhos auto-criados permanecem; a
sinalizacao ("aplicado/criado automaticamente") e derivada na UI. Reversao = no-op
(nao sabemos quais e-mails estavam ``classified`` antes da reabertura).
"""
from django.db import migrations


def reabrir_auto_classificados(apps, schema_editor):
    InboundEmail = apps.get_model('email_ingestion', 'InboundEmail')
    InboundEmail.objects.filter(
        processing_status='classified',
        classification__reviewed_at__isnull=True,
    ).update(processing_status='needs_review')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('email_ingestion', '0005_campos_sugestao_vaga_nova'),
    ]

    operations = [
        migrations.RunPython(reabrir_auto_classificados, noop),
    ]
