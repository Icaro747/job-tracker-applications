"""Emenda 13 (Fatia 2) — intencao sugerida pelo LLM vira campo persistido.

Na Fatia 1 o palpite de intencao era uma property derivada da existencia de
oportunidades. Com o LLM passando a emitir a intencao explicita (que distingue
``lista`` de ``nova_unica``, indistinguiveis pela contagem de vagas), o palpite
precisa ser armazenado. Esta migracao adiciona o campo e faz o backfill dos
e-mails ja classificados com a antiga logica derivada — sem reenviar ao LLM.
"""
from django.db import migrations, models


def backfill_suggested_intent(apps, schema_editor):
    EmailClassification = apps.get_model('email_ingestion', 'EmailClassification')
    for classification in EmailClassification.objects.all():
        if classification.opportunities.exists():
            classification.suggested_intent = 'nova_unica'
        else:
            classification.suggested_intent = 'atualizacao'
        classification.save(update_fields=['suggested_intent'])


class Migration(migrations.Migration):

    dependencies = [
        ('email_ingestion', '0009_remover_campos_sugestao'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailclassification',
            name='suggested_intent',
            field=models.CharField(
                blank=True,
                choices=[
                    ('atualizacao', 'Atualizacao de candidatura'),
                    ('nova_unica', 'Nova oportunidade unica'),
                    ('lista', 'Lista de oportunidades'),
                    ('irrelevante', 'Irrelevante / informativo'),
                ],
                default='',
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            backfill_suggested_intent, migrations.RunPython.noop
        ),
    ]
