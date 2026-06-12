"""Fatia 4 — aviso de duplicacao nao bloqueante (normalizado).

A comparacao ignora maiusculas, espacos nas pontas, pontuacao e sufixos
societarios comuns (Inc, Ltda, S.A., ME...). O aviso alerta e oferece reusar,
mas o usuario pode criar assim mesmo (``confirm_duplicate``).
"""
import pytest
from django.urls import reverse

from applications.models import Company, Job
from applications.utils import (
    find_duplicate_company,
    find_duplicate_job,
    normalize_name,
)
from tests.factories import CompanyFactory, JobFactory

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# normalize_name e find_duplicate_*.                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    'a,b',
    [
        ('Globex', 'globex'),
        ('Globex Inc.', 'Globex'),
        ('  Globex  ', 'Globex'),
        ('Acme S.A.', 'Acme'),
        ('Acme Ltda', 'acme'),
    ],
)
def test_normalize_name_treats_variants_as_equal(a, b):
    assert normalize_name(a) == normalize_name(b)


def test_normalize_name_keeps_distinct_names_distinct():
    assert normalize_name('Globex') != normalize_name('Initech')


def test_find_duplicate_company_matches_normalized_variant(db):
    existing = CompanyFactory(name='Globex')
    assert find_duplicate_company('Globex Inc.') == existing
    assert find_duplicate_company('Initech') is None


def test_find_duplicate_company_excludes_pk():
    existing = CompanyFactory(name='Globex')
    assert find_duplicate_company('Globex', exclude_pk=existing.pk) is None


def test_find_duplicate_job_same_company_and_title():
    company = CompanyFactory(name='Globex')
    job = JobFactory(company=company, role_title='Designer')
    other_company = CompanyFactory(name='Initech')

    assert find_duplicate_job(company, 'designer') == job
    assert find_duplicate_job(company, 'Backend') is None
    # Mesmo titulo em outra empresa nao e duplicata.
    assert find_duplicate_job(other_company, 'Designer') is None


# --------------------------------------------------------------------------- #
# Fluxo manual — CompanyCreateView.                                           #
# --------------------------------------------------------------------------- #
def test_company_create_warns_on_normalized_duplicate(auth_client):
    CompanyFactory(name='Globex')

    response = auth_client.post(
        reverse('applications:company_create'),
        {'name': 'Globex Inc.', 'website': '', 'careers_page': '', 'notes': ''},
    )

    assert response.status_code == 200  # re-renderiza o form com aviso
    assert 'Globex' in response.content.decode()
    # Nao criou ainda.
    assert not Company.objects.filter(name='Globex Inc.').exists()


def test_company_create_proceeds_with_confirm_duplicate(auth_client):
    CompanyFactory(name='Globex')

    response = auth_client.post(
        reverse('applications:company_create'),
        {
            'name': 'Globex Inc.',
            'website': '',
            'careers_page': '',
            'notes': '',
            'confirm_duplicate': '1',
        },
    )

    assert response.status_code == 302
    assert Company.objects.filter(name='Globex Inc.').exists()


def test_company_create_no_warning_when_unique(auth_client):
    response = auth_client.post(
        reverse('applications:company_create'),
        {'name': 'Initech', 'website': '', 'careers_page': '', 'notes': ''},
    )

    assert response.status_code == 302
    assert Company.objects.filter(name='Initech').exists()


# --------------------------------------------------------------------------- #
# Fluxo manual — JobCreateView.                                               #
# --------------------------------------------------------------------------- #
def test_job_create_warns_on_duplicate(auth_client):
    company = CompanyFactory(name='Globex')
    JobFactory(company=company, role_title='Designer')

    response = auth_client.post(
        reverse('applications:job_create'),
        {
            'company': company.pk,
            'role_title': 'designer',
            'source_url': '',
            'location': '',
            'remote': '',
            'directed_to': '',
        },
    )

    assert response.status_code == 200
    assert Job.objects.filter(company=company).count() == 1  # nao criou nova


def test_job_create_proceeds_with_confirm_duplicate(auth_client):
    company = CompanyFactory(name='Globex')
    JobFactory(company=company, role_title='Designer')

    response = auth_client.post(
        reverse('applications:job_create'),
        {
            'company': company.pk,
            'role_title': 'designer',
            'source_url': '',
            'location': '',
            'remote': '',
            'directed_to': '',
            'confirm_duplicate': '1',
        },
    )

    assert response.status_code == 302
    assert Job.objects.filter(company=company).count() == 2
