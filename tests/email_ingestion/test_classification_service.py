"""Testes da Fila 2 — servico classify_email (sem rede; classificador injetado).

A partir das melhorias da Etapa 4 (Fatia 1), a classificacao do LLM e *sempre
sugestao*: todo e-mail classificado vai para ``needs_review`` e nada e aplicado
ou criado automaticamente. A confianca so pre-seleciona e rotula.
"""
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
    EmailClassificationFactory,
    InboundEmailFactory,
    JobApplicationFactory,
)

pytestmark = pytest.mark.django_db


def _email_for(user):
    account = EmailAccountFactory(user=user)
    return InboundEmailFactory(email_account=account)


def test_high_confidence_pre_selects_but_does_not_apply():
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

    # A classificacao e gravada apenas como apoio.
    assert classification is not None
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    # Candidatura e status sugerido apenas pre-selecionados.
    assert email.application_id == app.pk
    assert email.inferred_application_status == JobApplication.Status.INTERVIEW
    # Nada e aplicado: status inalterado e sem evento na timeline.
    assert app.status == JobApplication.Status.APPLIED
    assert not app.timeline.filter(
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
    assert email.application_id == app.pk  # pre-vinculada para revisao
    assert app.status == JobApplication.Status.APPLIED  # inalterado


def test_new_opportunity_is_suggested_not_created():
    account = EmailAccountFactory()
    email = InboundEmailFactory(email_account=account)
    classifier = FakeClassifier(
        ClassificationResult(
            summary='Nova vaga de backend',
            confidence=88,
            intent=EmailClassification.Intent.NEW_SINGLE,
            opportunities=[
                DetectedOpportunity(
                    company_name='ACME Tech',
                    role_title='Dev Backend',
                    source_url='https://acme.com/vaga',
                )
            ],
        )
    )

    classify_email(email, classifier=classifier)
    email.refresh_from_db()

    # Recursos globais NAO sao criados a partir do palpite do LLM.
    assert not Company.objects.filter(name='ACME Tech').exists()
    assert not Job.objects.exists()
    assert not JobApplication.objects.exists()
    # Vira sugestao persistida como linha filha (emenda 13), em needs_review.
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    assert email.application_id is None
    classification = email.classification
    # O palpite do LLM e gravado em ``suggested_intent``; ``reviewed_intent``
    # fica em branco ate a revisao (passo 1).
    assert classification.suggested_intent == EmailClassification.Intent.NEW_SINGLE
    assert classification.reviewed_intent == ''
    opportunities = list(classification.opportunities.all())
    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.company_name == 'ACME Tech'
    assert opp.role_title == 'Dev Backend'
    assert opp.source_url == 'https://acme.com/vaga'
    assert opp.state == 'pending'


def test_list_intent_persists_one_row_per_opportunity():
    account = EmailAccountFactory()
    email = InboundEmailFactory(email_account=account)
    classifier = FakeClassifier(
        ClassificationResult(
            summary='3 vagas para voce',
            confidence=60,
            intent=EmailClassification.Intent.LIST,
            opportunities=[
                DetectedOpportunity(company_name='ACME', role_title='Dev Backend'),
                DetectedOpportunity(company_name='Globex', role_title='Designer'),
                DetectedOpportunity(company_name='Initech', role_title='QA'),
            ],
        )
    )

    classify_email(email, classifier=classifier)
    email.refresh_from_db()

    classification = email.classification
    assert classification.suggested_intent == EmailClassification.Intent.LIST
    assert email.processing_status == InboundEmail.ProcessingStatus.NEEDS_REVIEW
    opportunities = list(classification.opportunities.all())
    assert [o.company_name for o in opportunities] == ['ACME', 'Globex', 'Initech']
    assert all(o.state == 'pending' for o in opportunities)
    # Nada e materializado a partir do palpite.
    assert not Company.objects.exists()
    assert not Job.objects.exists()
    assert not JobApplication.objects.exists()


def test_no_opportunity_creates_no_detected_rows():
    app = JobApplicationFactory(status=JobApplication.Status.APPLIED)
    email = _email_for(app.user)
    classifier = FakeClassifier(
        ClassificationResult(
            summary='Convite para entrevista',
            suggested_status=JobApplication.Status.INTERVIEW,
            confidence=95,
            application_id=app.pk,
            intent=EmailClassification.Intent.UPDATE,
        )
    )

    classify_email(email, classifier=classifier)
    email.refresh_from_db()

    # Atualizacao de candidatura: nenhuma vaga detectada e intencao em branco.
    assert email.classification.opportunities.count() == 0
    assert email.classification.suggested_intent == EmailClassification.Intent.UPDATE
    assert email.classification.reviewed_intent == ''


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


@pytest.mark.parametrize(
    ('confidence', 'expected'),
    [(92, 'alta'), (80, 'alta'), (74, 'media'), (50, 'media'), (31, 'baixa')],
)
def test_confidence_band_labels(confidence, expected):
    classification = EmailClassificationFactory(confidence=confidence)
    assert classification.band == expected
