"""Testes da Fila 2 — servico classify_email (sem rede; classificador injetado)."""
import pytest

from applications.models import (
    ApplicationTimelineEntry,
    Company,
    Job,
    JobApplication,
)
from email_ingestion.classifiers.base import ClassificationResult, DetectedOpportunity
from email_ingestion.models import EmailClassification, InboundEmail
from email_ingestion.services import classify_email
from tests.email_ingestion.fakes import FakeClassifier
from tests.factories import (
    EmailAccountFactory,
    InboundEmailFactory,
    JobApplicationFactory,
)

pytestmark = pytest.mark.django_db


def _email_for(user):
    account = EmailAccountFactory(user=user)
    return InboundEmailFactory(email_account=account)


def test_high_confidence_match_applies_status_and_classifies():
    app = JobApplicationFactory(status=JobApplication.Status.APPLIED)
    email = _email_for(app.user)
    classifier = FakeClassifier(
        ClassificationResult(
            summary='Convite para entrevista',
            suggested_status=JobApplication.Status.INTERVIEW,
            confidence=95,
            application_id=app.pk,
        )
    )

    classification = classify_email(email, classifier=classifier)
    email.refresh_from_db()
    app.refresh_from_db()

    assert classification is not None
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED
    assert email.application_id == app.pk
    assert app.status == JobApplication.Status.INTERVIEW
    assert app.timeline.filter(
        entry_type=ApplicationTimelineEntry.EntryType.EMAIL_UPDATE
    ).exists()


def test_low_confidence_routes_to_review_without_status_change():
    app = JobApplicationFactory(status=JobApplication.Status.APPLIED)
    email = _email_for(app.user)
    classifier = FakeClassifier(
        ClassificationResult(
            summary='Talvez seja sobre a vaga',
            suggested_status=JobApplication.Status.INTERVIEW,
            confidence=40,
            application_id=app.pk,
        )
    )

    classify_email(email, classifier=classifier)
    email.refresh_from_db()
    app.refresh_from_db()

    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert app.status == JobApplication.Status.APPLIED  # inalterado


def test_invalid_suggested_status_routes_to_review():
    app = JobApplicationFactory(status=JobApplication.Status.APPLIED)
    email = _email_for(app.user)
    classifier = FakeClassifier(
        ClassificationResult(
            suggested_status='status_inexistente',
            confidence=99,
            application_id=app.pk,
        )
    )

    classify_email(email, classifier=classifier)
    email.refresh_from_db()
    app.refresh_from_db()

    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert app.status == JobApplication.Status.APPLIED


def test_new_opportunity_creates_job_and_draft_application():
    account = EmailAccountFactory()
    email = InboundEmailFactory(email_account=account)
    classifier = FakeClassifier(
        ClassificationResult(
            summary='Nova vaga de backend',
            confidence=88,
            is_new_opportunity=True,
            opportunity=DetectedOpportunity(
                company_name='ACME Tech',
                role_title='Dev Backend',
                source_url='https://acme.com/vaga',
            ),
        )
    )

    classify_email(email, classifier=classifier)
    email.refresh_from_db()

    company = Company.objects.get(name='ACME Tech')
    job = Job.objects.get(company=company)
    assert job.directed_to == account.user
    assert job.source_url == 'https://acme.com/vaga'
    application = JobApplication.objects.get(job=job, user=account.user)
    assert application.status == JobApplication.Status.DRAFT
    assert application.origin == JobApplication.Origin.EMAIL
    assert email.application_id == application.pk
    assert email.processing_status == InboundEmail.ProcessingStatus.CLASSIFIED


def test_classifier_failure_leaves_email_pending():
    email = _email_for(EmailAccountFactory().user)
    classifier = FakeClassifier(error=True)

    result = classify_email(email, classifier=classifier)
    email.refresh_from_db()

    assert result is None
    assert email.processing_status == InboundEmail.ProcessingStatus.PENDING
    assert not EmailClassification.objects.filter(email=email).exists()


def test_does_not_link_application_of_other_user():
    other_app = JobApplicationFactory(status=JobApplication.Status.APPLIED)
    email = _email_for(EmailAccountFactory().user)  # dono diferente
    classifier = FakeClassifier(
        ClassificationResult(
            suggested_status=JobApplication.Status.INTERVIEW,
            confidence=99,
            application_id=other_app.pk,  # candidatura de outro usuario
        )
    )

    classify_email(email, classifier=classifier)
    email.refresh_from_db()
    other_app.refresh_from_db()

    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert email.application_id is None
    assert other_app.status == JobApplication.Status.APPLIED
