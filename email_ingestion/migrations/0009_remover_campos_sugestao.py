"""Emenda 13 (Fatia 1) — remove a vaga sugerida unica da classificacao.

Os campos ``is_new_opportunity`` e ``suggested_*`` foram movidos para
``EmailDetectedOpportunity`` na 0008. A vaga sugerida deixa de ser um campo
unico e passa a ser "a primeira (e talvez unica) linha filha".
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('email_ingestion', '0008_migrar_sugestoes_para_oportunidade'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='emailclassification',
            name='is_new_opportunity',
        ),
        migrations.RemoveField(
            model_name='emailclassification',
            name='suggested_company_name',
        ),
        migrations.RemoveField(
            model_name='emailclassification',
            name='suggested_role_title',
        ),
        migrations.RemoveField(
            model_name='emailclassification',
            name='suggested_source_url',
        ),
    ]
