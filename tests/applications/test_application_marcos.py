"""Fatia 2 — Painel de marcos + aviso de pendencia na candidatura."""
import pytest
from django.urls import reverse
from django.utils import timezone

from applications.models import ApplicationTimelineEntry, JobApplication
from email_ingestion.models import InboundEmail
from tests.factories import (
    ApplicationTimelineEntryFactory,
    InboundEmailFactory,
    JobApplicationFactory,
)

pytestmark = pytest.mark.django_db


class TestAnnouncementReceivedAt:
    def test_returns_oldest_linked_email(self, user):
        application = JobApplicationFactory(user=user)
        antigo = timezone.now() - timezone.timedelta(days=5)
        recente = timezone.now() - timezone.timedelta(days=1)
        InboundEmailFactory(application=application, received_at=recente)
        InboundEmailFactory(application=application, received_at=antigo)
        assert application.announcement_received_at == antigo

    def test_none_when_no_email(self, user):
        application = JobApplicationFactory(user=user)
        assert application.announcement_received_at is None


class TestLastReturnAt:
    def test_returns_latest_email_update_entry(self, user):
        application = JobApplicationFactory(user=user)
        antigo = timezone.now() - timezone.timedelta(days=4)
        recente = timezone.now() - timezone.timedelta(days=1)
        ApplicationTimelineEntryFactory(
            application=application,
            entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE,
            occurred_at=antigo,
        )
        ApplicationTimelineEntryFactory(
            application=application,
            entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE,
            occurred_at=recente,
        )
        # Uma nota manual nao deve contar como retorno.
        ApplicationTimelineEntryFactory(
            application=application,
            entry_type=ApplicationTimelineEntry.EntryType.MANUAL_NOTE,
            occurred_at=timezone.now(),
        )
        assert application.last_return_at == recente

    def test_none_without_email_update(self, user):
        application = JobApplicationFactory(user=user)
        ApplicationTimelineEntryFactory(
            application=application,
            entry_type=ApplicationTimelineEntry.EntryType.MANUAL_NOTE,
        )
        assert application.last_return_at is None


class TestAwaitingReturn:
    def test_true_when_open_and_no_return(self, user):
        application = JobApplicationFactory(
            user=user, status=JobApplication.Status.APPLIED
        )
        assert application.awaiting_return is True

    def test_false_after_return(self, user):
        application = JobApplicationFactory(
            user=user, status=JobApplication.Status.SCREENING
        )
        ApplicationTimelineEntryFactory(
            application=application,
            entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE,
        )
        assert application.awaiting_return is False

    def test_false_when_closed_status(self, user):
        application = JobApplicationFactory(
            user=user, status=JobApplication.Status.REJECTED
        )
        assert application.awaiting_return is False


class TestPendingReviewWarning:
    def test_context_counts_needs_review_emails(self, auth_client, user):
        application = JobApplicationFactory(user=user)
        InboundEmailFactory(
            application=application,
            processing_status=InboundEmail.ProcessingStatus.NEEDS_REVIEW,
        )
        InboundEmailFactory(
            application=application,
            processing_status=InboundEmail.ProcessingStatus.CLASSIFIED,
        )
        response = auth_client.get(
            reverse('applications:application_detail', args=[application.pk])
        )
        assert response.status_code == 200
        assert response.context['pending_reviews_count'] == 1
        assert b'aguardando revis' in response.content

    def test_no_warning_without_pending(self, auth_client, user):
        application = JobApplicationFactory(user=user)
        response = auth_client.get(
            reverse('applications:application_detail', args=[application.pk])
        )
        assert response.context['pending_reviews_count'] == 0
        assert b'aguardando revis' not in response.content


class TestMarcosPanelRendered:
    def test_detail_shows_marcos_block(self, auth_client, user):
        application = JobApplicationFactory(
            user=user, status=JobApplication.Status.APPLIED
        )
        response = auth_client.get(
            reverse('applications:application_detail', args=[application.pk])
        )
        assert response.status_code == 200
        assert b'Marcos' in response.content
        assert b'Criada em' in response.content
