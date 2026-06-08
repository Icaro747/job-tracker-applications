"""Comportamento de dominio da candidatura: status, proxima acao e notas.

Cada metodo de `JobApplication` encapsula a regra de negocio e o registro
append-only na linha do tempo (`ApplicationTimelineEntry`).
"""
import pytest
from django.utils import timezone

from applications.models import ApplicationTimelineEntry, JobApplication
from tests.factories import JobApplicationFactory

pytestmark = pytest.mark.django_db


class TestChangeStatus:
    def test_updates_status_and_stamps_last_status_at(self):
        application = JobApplicationFactory(status=JobApplication.Status.DRAFT)
        assert application.last_status_at is None

        application.change_status(JobApplication.Status.APPLIED)

        application.refresh_from_db()
        assert application.status == JobApplication.Status.APPLIED
        assert application.last_status_at is not None

    def test_appends_status_change_timeline_entry(self):
        application = JobApplicationFactory(status=JobApplication.Status.DRAFT)

        application.change_status(JobApplication.Status.SCREENING)

        entry = application.timeline.get(
            entry_type=ApplicationTimelineEntry.EntryType.STATUS_CHANGE
        )
        assert 'Rascunho' in entry.title
        assert 'Triagem' in entry.title

    def test_same_status_is_noop(self):
        application = JobApplicationFactory(status=JobApplication.Status.DRAFT)

        application.change_status(JobApplication.Status.DRAFT)

        assert application.timeline.count() == 0
        assert application.last_status_at is None

    def test_moving_to_applied_sets_applied_at_once(self):
        application = JobApplicationFactory(status=JobApplication.Status.DRAFT)

        application.change_status(JobApplication.Status.APPLIED)

        application.refresh_from_db()
        assert application.applied_at is not None
        first_applied_at = application.applied_at

        # Voltar para applied de novo nao sobrescreve a data original.
        application.change_status(JobApplication.Status.CONFIRMED)
        application.change_status(JobApplication.Status.APPLIED)
        application.refresh_from_db()
        assert application.applied_at == first_applied_at


class TestNextAction:
    def test_set_next_action_fills_fields(self):
        application = JobApplicationFactory()
        when = timezone.now() + timezone.timedelta(days=2)

        application.set_next_action(
            at=when,
            action_type=JobApplication.NextActionType.INTERVIEW,
            description='Entrevista tecnica',
        )

        application.refresh_from_db()
        assert application.next_action_at == when
        assert application.next_action_type == JobApplication.NextActionType.INTERVIEW
        assert application.next_action_description == 'Entrevista tecnica'

    def test_complete_next_action_clears_fields_and_logs_reminder(self):
        application = JobApplicationFactory()
        application.set_next_action(
            at=timezone.now() - timezone.timedelta(hours=1),
            action_type=JobApplication.NextActionType.FOLLOW_UP,
        )

        application.complete_next_action(note='Liguei para o RH')

        application.refresh_from_db()
        assert application.next_action_at is None
        assert application.next_action_type == ''
        assert application.next_action_description == ''
        entry = application.timeline.get(
            entry_type=ApplicationTimelineEntry.EntryType.REMINDER
        )
        assert 'Liguei para o RH' in entry.description


class TestAddNote:
    def test_add_note_creates_manual_note_entry(self):
        application = JobApplicationFactory()

        application.add_note('Recrutador pediu portfolio')

        entry = application.timeline.get(
            entry_type=ApplicationTimelineEntry.EntryType.MANUAL_NOTE
        )
        assert 'portfolio' in entry.description
