"""CRUD de Empresa via templates — recurso global, auditoria automatica."""
import pytest
from django.urls import reverse

from applications.models import Company, CompanyAuditLog, Job
from tests.factories import CompanyFactory, JobFactory

pytestmark = pytest.mark.django_db


class TestCompanyAccess:
    def test_anonymous_redirected_to_login(self, client):
        response = client.get(reverse('applications:company_list'))
        assert response.status_code == 302
        assert reverse('account_login') in response.url

    def test_authenticated_sees_list(self, auth_client):
        CompanyFactory(name='Acme')
        response = auth_client.get(reverse('applications:company_list'))
        assert response.status_code == 200
        assert b'Acme' in response.content


class TestCompanyCreate:
    def test_create_sets_created_by_and_logs_audit(self, auth_client, user):
        response = auth_client.post(
            reverse('applications:company_create'),
            {'name': 'Nova Empresa', 'website': '', 'careers_page': '', 'notes': ''},
        )
        assert response.status_code == 302
        company = Company.objects.get(name='Nova Empresa')
        assert company.created_by == user
        assert company.audit_logs.filter(action=CompanyAuditLog.Action.CREATED).count() == 1


class TestCompanyUpdate:
    def test_update_logs_one_audit_per_changed_field(self, auth_client):
        company = CompanyFactory(name='Antigo', website='https://antigo.com')
        response = auth_client.post(
            reverse('applications:company_update', args=[company.pk]),
            {
                'name': 'Novo',
                'website': 'https://novo.com',
                'careers_page': '',
                'notes': '',
            },
        )
        assert response.status_code == 302
        company.refresh_from_db()
        assert company.name == 'Novo'
        assert company.audit_logs.filter(action=CompanyAuditLog.Action.UPDATED).count() == 2


class TestCompanyDelete:
    def test_delete_removes_company(self, auth_client):
        company = CompanyFactory()
        response = auth_client.post(reverse('applications:company_delete', args=[company.pk]))
        assert response.status_code == 302
        assert not Company.objects.filter(pk=company.pk).exists()

    def test_delete_protected_company_shows_message(self, auth_client):
        job = JobFactory()
        company = job.company
        response = auth_client.post(
            reverse('applications:company_delete', args=[company.pk]), follow=True
        )
        # Empresa com vaga vinculada (PROTECT) nao e excluida.
        assert Company.objects.filter(pk=company.pk).exists()
        assert Job.objects.filter(pk=job.pk).exists()
