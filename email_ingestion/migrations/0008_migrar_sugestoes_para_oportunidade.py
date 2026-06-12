"""Emenda 13 (Fatia 1) — move a vaga sugerida para uma linha filha.

Para cada ``EmailClassification`` que tinha oportunidade sugerida
(``is_new_opportunity``), cria **uma** ``EmailDetectedOpportunity`` carregando os
``suggested_*``. O estado e derivado (ja ha candidatura ligada ao e-mail →
``created`` com job/candidatura; senao ``pending``) e ``reviewed_intent`` e
inferido (tem candidatura → atualizacao; senao tinha oportunidade → nova unica;
senao em branco, decide-se na revisao).

Nada e reenviado ao LLM — apenas reorganizado. Reversao = no-op (a remocao dos
campos ``suggested_*`` vem na 0009; revertendo, os dados ja foram migrados).
"""
from django.db import migrations


def migrar_sugestoes(apps, schema_editor):
    EmailClassification = apps.get_model('email_ingestion', 'EmailClassification')
    EmailDetectedOpportunity = apps.get_model(
        'email_ingestion', 'EmailDetectedOpportunity'
    )

    for classification in EmailClassification.objects.select_related('email').all():
        email = classification.email
        application = getattr(email, 'application', None)

        if classification.is_new_opportunity:
            if application is not None:
                state, job = 'created', application.job
            else:
                state, job = 'pending', None
            EmailDetectedOpportunity.objects.create(
                classification=classification,
                company_name=classification.suggested_company_name or '',
                role_title=classification.suggested_role_title or '',
                source_url=classification.suggested_source_url or '',
                state=state,
                job=job,
                application=application,
            )

        if application is not None:
            classification.reviewed_intent = 'atualizacao'
        elif classification.is_new_opportunity:
            classification.reviewed_intent = 'nova_unica'
        else:
            classification.reviewed_intent = ''
        classification.save(update_fields=['reviewed_intent'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('email_ingestion', '0007_intencao_e_oportunidade'),
    ]

    operations = [
        migrations.RunPython(migrar_sugestoes, noop),
    ]
