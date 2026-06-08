"""CRUD + acoes HTMX de Candidatura — privada por usuario."""
import pytest
from django.urls import reverse
from django.utils import timezone

from applications.models import ApplicationTimelineEntry, JobApplication
from tests.factories import JobApplicationFactory, JobFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestApplicationListIsolation:
    def test_list_shows_only_own_applications(self, auth_client, user):
        mine = JobApplicationFactory(user=user, job__role_title='Minha Vaga')
        JobApplicationFactory(job__role_title='Vaga Alheia')  # outro usuario
        response = auth_client.get(reverse('applications:application_list'))
        assert response.status_code == 200
        assert b'Minha Vaga' in response.content
        assert b'Vaga Alheia' not in response.content
        assert mine.user == user


class TestApplicationDetailOwnership:
    def test_owner_sees_detail(self, auth_client, user):
        application = JobApplicationFactory(user=user)
        response = auth_client.get(
            reverse('applications:application_detail', args=[application.pk])
        )
        assert response.status_code == 200

    def test_non_owner_gets_404(self, auth_client):
        other = JobApplicationFactory(user=UserFactory())
        response = auth_client.get(
            reverse('applications:application_detail', args=[other.pk])
        )
        assert response.status_code == 404


class TestApplicationCreate:
    def test_create_sets_user_and_manual_origin(self, auth_client, user):
        job = JobFactory()
        response = auth_client.post(
            reverse('applications:application_create'),
            {
                'job': job.pk,
                'status': JobApplication.Status.DRAFT,
                'applied_at': '',
                'notes': '',
            },
        )
        assert response.status_code == 302
        application = JobApplication.objects.get(user=user, job=job)
        assert application.origin == JobApplication.Origin.MANUAL


class TestApplicationHtmxActions:
    def test_change_status_records_timeline(self, auth_client, user):
        application = JobApplicationFactory(user=user, status=JobApplication.Status.DRAFT)
        response = auth_client.post(
            reverse('applications:application_status', args=[application.pk]),
            {'status': JobApplication.Status.SCREENING},
        )
        assert response.status_code == 200
        application.refresh_from_db()
        assert application.status == JobApplication.Status.SCREENING
        assert application.timeline.filter(
            entry_type=ApplicationTimelineEntry.EntryType.STATUS_CHANGE
        ).exists()

    def test_add_note_records_timeline(self, auth_client, user):
        application = JobApplicationFactory(user=user)
        response = auth_client.post(
            reverse('applications:application_note', args=[application.pk]),
            {'text': 'Conversa com recrutador'},
        )
        assert response.status_code == 200
        assert application.timeline.filter(
            entry_type=ApplicationTimelineEntry.EntryType.MANUAL_NOTE
        ).exists()

    def test_set_and_complete_next_action(self, auth_client, user):
        application = JobApplicationFactory(user=user)
        when = (timezone.now() + timezone.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        set_response = auth_client.post(
            reverse('applications:application_next_action', args=[application.pk]),
            {
                'next_action_at': when,
                'next_action_type': JobApplication.NextActionType.FOLLOW_UP,
                'next_action_description': 'Retomar contato',
            },
        )
        assert set_response.status_code == 200
        application.refresh_from_db()
        assert application.next_action_at is not None

        complete_response = auth_client.post(
            reverse('applications:application_complete_next_action', args=[application.pk]),
        )
        assert complete_response.status_code == 200
        application.refresh_from_db()
        assert application.next_action_at is None
        assert application.timeline.filter(
            entry_type=ApplicationTimelineEntry.EntryType.REMINDER
        ).exists()

    def test_non_owner_cannot_act(self, auth_client):
        other = JobApplicationFactory(user=UserFactory())
        response = auth_client.post(
            reverse('applications:application_note', args=[other.pk]),
            {'text': 'hack'},
        )
        assert response.status_code == 404
