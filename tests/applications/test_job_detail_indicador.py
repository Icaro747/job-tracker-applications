"""Fatia 3 — Vaga: datas de anuncio/cadastro + indicador "candidatei?"."""
import datetime

import pytest
from django.urls import reverse

from applications.forms import JobForm
from applications.models import Job, JobApplication
from tests.factories import (
    CompanyFactory,
    JobApplicationFactory,
    JobFactory,
)

pytestmark = pytest.mark.django_db


class TestPublishedAtDisplay:
    def test_shows_announced_when_set(self, auth_client):
        job = JobFactory(published_at=datetime.date(2026, 5, 28))
        response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
        assert response.status_code == 200
        assert b'Anunciada em' in response.content
        assert b'28/05/2026' in response.content

    def test_omits_announced_when_blank(self, auth_client):
        job = JobFactory(published_at=None)
        response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
        assert b'Anunciada em' not in response.content

    def test_always_shows_registered_at(self, auth_client):
        job = JobFactory(published_at=None)
        response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
        assert b'Cadastrada no sistema em' in response.content


class TestApplicationIndicator:
    def test_not_applied_shows_button(self, auth_client, user):
        job = JobFactory()
        response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
        assert response.context['user_application'] is None
        assert b'ainda nao se candidatou' in response.content
        assert b'Candidatar-se' in response.content

    def test_applied_shows_link_and_status(self, auth_client, user):
        job = JobFactory()
        application = JobApplicationFactory(
            user=user, job=job, status=JobApplication.Status.SCREENING
        )
        response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
        assert response.context['user_application'] == application
        assert b'Voce se candidatou em' in response.content
        assert b'Triagem' in response.content
        assert b'Candidatar-se' not in response.content

    def test_uses_most_recent_application(self, auth_client, user):
        job = JobFactory()
        JobApplicationFactory(user=user, job=job, status=JobApplication.Status.WITHDRAWN)
        recent = JobApplicationFactory(
            user=user, job=job, status=JobApplication.Status.INTERVIEW
        )
        response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
        assert response.context['user_application'] == recent

    def test_ignores_other_users_application(self, auth_client, user):
        job = JobFactory()
        JobApplicationFactory(job=job)  # outro usuario
        response = auth_client.get(reverse('applications:job_detail', args=[job.pk]))
        assert response.context['user_application'] is None


class TestJobFormPublishedAt:
    def test_form_persists_published_at(self):
        company = CompanyFactory()
        form = JobForm(
            data={
                'company': company.pk,
                'role_title': 'Designer',
                'source_url': '',
                'location': 'Remoto',
                'published_at': '2026-05-28',
            }
        )
        assert form.is_valid(), form.errors
        job = form.save()
        assert job.published_at == datetime.date(2026, 5, 28)

    def test_published_at_optional(self):
        company = CompanyFactory()
        form = JobForm(
            data={
                'company': company.pk,
                'role_title': 'Designer',
                'source_url': '',
                'location': '',
                'published_at': '',
            }
        )
        assert form.is_valid(), form.errors
        job = form.save()
        assert job.published_at is None
