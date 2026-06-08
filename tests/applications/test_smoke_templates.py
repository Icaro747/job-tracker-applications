"""Smoke: paginas GET de formulario/exclusao renderizam sem erro de template."""
import pytest
from django.urls import reverse

from tests.factories import CompanyFactory, JobApplicationFactory, JobFactory

pytestmark = pytest.mark.django_db


def test_form_and_delete_pages_render(auth_client, user):
    company = CompanyFactory()
    job = JobFactory(company=company)
    application = JobApplicationFactory(user=user, job=job)
    urls = [
        reverse('applications:company_create'),
        reverse('applications:company_update', args=[company.pk]),
        reverse('applications:company_detail', args=[company.pk]),
        reverse('applications:company_delete', args=[company.pk]),
        reverse('applications:job_create'),
        reverse('applications:job_update', args=[job.pk]),
        reverse('applications:job_detail', args=[job.pk]),
        reverse('applications:job_delete', args=[job.pk]),
        reverse('applications:application_create'),
        reverse('applications:application_create') + f'?job={job.pk}',
        reverse('applications:application_update', args=[application.pk]),
        reverse('applications:application_detail', args=[application.pk]),
        reverse('applications:application_delete', args=[application.pk]),
    ]
    for url in urls:
        response = auth_client.get(url)
        assert response.status_code == 200, f'{url} -> {response.status_code}'
