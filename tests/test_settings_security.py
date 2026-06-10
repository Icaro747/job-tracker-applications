"""Testes da configuracao de seguranca em producao (DEBUG=False).

Carregam o modulo de settings num subprocesso com ambiente controlado
(DJANGO_SKIP_DOTENV=1 ignora o .env local), para nao perturbar o Django ja
configurado da sessao de testes.
"""
import subprocess
import sys

VALID_FERNET_KEY = 'ZGV2LWluc2VjdXJlLWtleS1jaGFuZ2UtaW4tcHJvZCE='


def _load_settings(env_extra, attr_expr='True'):
    """Importa config.settings num subprocesso e imprime ``attr_expr``."""
    code = (
        'from django.conf import settings; '
        f'print(repr({attr_expr}))'
    )
    env = {
        'DJANGO_SETTINGS_MODULE': 'config.settings',
        'DJANGO_SKIP_DOTENV': '1',
        'SystemRoot': __import__('os').environ.get('SystemRoot', ''),
        'PATH': __import__('os').environ.get('PATH', ''),
    }
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True,
        text=True,
        env=env,
    )


def test_secret_key_obrigatoria_em_producao():
    result = _load_settings(
        {'DJANGO_DEBUG': 'false', 'DJANGO_FIELD_ENCRYPTION_KEY': VALID_FERNET_KEY},
        attr_expr='settings.SECRET_KEY',
    )
    assert result.returncode != 0
    assert 'ImproperlyConfigured' in result.stderr
    assert 'DJANGO_SECRET_KEY' in result.stderr


def test_chave_de_criptografia_obrigatoria_em_producao():
    result = _load_settings(
        {'DJANGO_DEBUG': 'false', 'DJANGO_SECRET_KEY': 'x' * 50},
        attr_expr='settings.FIELD_ENCRYPTION_KEY',
    )
    assert result.returncode != 0
    assert 'ImproperlyConfigured' in result.stderr
    assert 'DJANGO_FIELD_ENCRYPTION_KEY' in result.stderr


def test_cookies_e_hsts_seguros_quando_nao_debug():
    result = _load_settings(
        {
            'DJANGO_DEBUG': 'false',
            'DJANGO_SECRET_KEY': 'x' * 50,
            'DJANGO_FIELD_ENCRYPTION_KEY': VALID_FERNET_KEY,
            'DJANGO_ALLOWED_HOSTS': 'exemplo.com',
        },
        attr_expr='('
        'settings.SESSION_COOKIE_SECURE, '
        'settings.CSRF_COOKIE_SECURE, '
        'settings.SECURE_SSL_REDIRECT, '
        'settings.SECURE_HSTS_SECONDS > 0'
        ')',
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '(True, True, True, True)'


def test_em_debug_usa_fallback_sem_exigir_envs():
    result = _load_settings(
        {'DJANGO_DEBUG': 'true'},
        attr_expr='(bool(settings.SECRET_KEY), bool(settings.FIELD_ENCRYPTION_KEY))',
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '(True, True)'
