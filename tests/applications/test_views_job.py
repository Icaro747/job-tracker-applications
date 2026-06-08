"""CRUD de Vaga via templates — recurso global."""
import pytest
from django.urls import reverse

from applications.models import Job
from tests.factories import CompanyFactory, JobFactory

pytestmark = pytest.mark.django_db


class TestJobAccess:
    def test_anonymous_redirected_to_login(self, client):
        response = client.get(reverse('applications:job_list'))
        assert response.status_code == 302
        assert reverse('account_login') in response.url

    def test_authenticated_sees_list(self, auth_client):
        JobFactory(role_title='Dev Backend')
        response = auth_client.get(reverse('applications:job_list'))
        assert response.status_code == 200
        assert b'Dev Backend' in response.content


class TestJobCreate:
    def test_create_sets_created_by(self, auth_client, user):
        company = CompanyFactory()
        response = auth_client.post(
            reverse('applications:job_create'),
            {
                'company': company.pk,
                'role_title': 'Engenheiro de Dados',
                'source_url': '',
                'location': 'Remoto',
                'directed_to': '',
            },
        )
        assert response.status_code == 302
        job = Job.objects.get(role_title='Engenheiro de Dados')
        assert job.created_by == user


class TestJobDelete:
    def test_delete_removes_job(self, auth_client):
        job = JobFactory()
        response = auth_client.post(reverse('applications:job_delete', args=[job.pk]))
        assert response.status_code == 302
        assert not Job.objects.filter(pk=job.pk).exists()
