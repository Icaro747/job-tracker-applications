"""Emenda 13 — esqueleto da revisao orientada a intencao (Fatia 1).

Adiciona ``EmailClassification.reviewed_intent`` (intencao confirmada pelo
usuario) e cria ``EmailDetectedOpportunity`` (uma linha por vaga detectada). A
migracao de dados (0008) move os ``suggested_*`` para uma linha filha antes de
remove-los (0009).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0003_company_source_email_job_source_email_and_more'),
        ('email_ingestion', '0006_reabrir_legado_auto'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailclassification',
            name='reviewed_intent',
            field=models.CharField(
                blank=True,
                choices=[
                    ('atualizacao', 'Atualizacao de candidatura'),
                    ('nova_unica', 'Nova oportunidade unica'),
                    ('lista', 'Lista de oportunidades'),
                    ('irrelevante', 'Irrelevante / informativo'),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='EmailDetectedOpportunity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(blank=True, max_length=180)),
                ('role_title', models.CharField(blank=True, max_length=220)),
                ('source_url', models.URLField(blank=True)),
                ('state', models.CharField(choices=[('pending', 'Pendente'), ('created', 'Criada'), ('dismissed', 'Descartada')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('classification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='opportunities', to='email_ingestion.emailclassification')),
                ('job', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='applications.job')),
                ('application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='applications.jobapplication')),
            ],
            options={
                'verbose_name': 'oportunidade detectada',
                'verbose_name_plural': 'oportunidades detectadas',
                'ordering': ['pk'],
            },
        ),
    ]
