"""Apaga tokens OAuth gravados em texto plano antes da criptografia.

Os tokens legados (anteriores ao EncryptedTextField) ficaram em texto plano no
banco. Por seguranca, zeramos todas as credenciais e desativamos as contas — o
usuario reconecta o Gmail uma vez pelo fluxo OAuth. Operacao irreversivel por
natureza; a reversao e um no-op.
"""
from django.db import migrations


def apagar_tokens(apps, schema_editor):
    EmailAccount = apps.get_model('email_ingestion', 'EmailAccount')
    EmailAccount.objects.update(
        access_token='',
        refresh_token='',
        token_expiry=None,
        is_active=False,
    )


def noop(apps, schema_editor):
    # Nao ha como restaurar tokens apagados.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('email_ingestion', '0002_alter_emailaccount_access_token_and_more'),
    ]

    operations = [
        migrations.RunPython(apagar_tokens, noop),
    ]
