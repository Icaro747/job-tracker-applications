import factory
from django.contrib.auth import get_user_model

from django.utils import timezone

from applications.models import (
    ApplicationTimelineEntry,
    Company,
    Job,
    JobApplication,
)
from candidate_profile.models import CandidateProfile
from email_ingestion.models import (
    EmailAccount,
    EmailClassification,
    EmailDetectedOpportunity,
    EmailSenderRule,
    InboundEmail,
)

User = get_user_model()

TEST_PASSWORD = 'senha-de-teste-123'


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f'usuario_{n}')
    email = factory.Sequence(lambda n: f'usuario_{n}@exemplo.com')

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or TEST_PASSWORD)
        if create:
            self.save()


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company
        django_get_or_create = ('name',)

    name = factory.Sequence(lambda n: f'Empresa {n}')
    website = factory.Faker('url')
    created_by = factory.SubFactory(UserFactory)


class JobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Job

    company = factory.SubFactory(CompanyFactory)
    role_title = factory.Faker('job', locale='pt_BR')
    location = factory.Faker('city', locale='pt_BR')
    created_by = factory.SubFactory(UserFactory)


class JobApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobApplication

    user = factory.SubFactory(UserFactory)
    job = factory.SubFactory(JobFactory)
    status = JobApplication.Status.DRAFT
    origin = JobApplication.Origin.MANUAL


class ApplicationTimelineEntryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApplicationTimelineEntry

    application = factory.SubFactory(JobApplicationFactory)
    entry_type = ApplicationTimelineEntry.EntryType.MANUAL_NOTE
    title = factory.Sequence(lambda n: f'Evento {n}')
    occurred_at = factory.LazyFunction(timezone.now)


class CandidateProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CandidateProfile

    user = factory.SubFactory(UserFactory)
    full_name = factory.Faker('name', locale='pt_BR')
    headline = factory.Faker('job', locale='pt_BR')


class EmailAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailAccount

    user = factory.SubFactory(UserFactory)
    provider = EmailAccount.Provider.GMAIL
    email_address = factory.Sequence(lambda n: f'conta_{n}@gmail.com')


class EmailSenderRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailSenderRule

    email_account = factory.SubFactory(EmailAccountFactory)
    name = factory.Sequence(lambda n: f'Regra {n}')
    sender_domain = '@empresa.com'


class InboundEmailFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InboundEmail

    message_id = factory.Sequence(lambda n: f'msg-{n}')
    email_account = factory.SubFactory(EmailAccountFactory)
    sender = factory.Sequence(lambda n: f'remetente_{n}@empresa.com')
    subject = factory.Sequence(lambda n: f'Assunto {n}')
    received_at = factory.LazyFunction(timezone.now)


class EmailClassificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailClassification

    email = factory.SubFactory(InboundEmailFactory)
    confidence = 90
    summary = factory.Sequence(lambda n: f'Resumo {n}')
    suggested_status = JobApplication.Status.INTERVIEW
    rationale = 'Justificativa de teste'


class EmailDetectedOpportunityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailDetectedOpportunity

    classification = factory.SubFactory(EmailClassificationFactory)
    company_name = factory.Sequence(lambda n: f'Empresa detectada {n}')
    role_title = factory.Sequence(lambda n: f'Vaga detectada {n}')
    source_url = factory.Faker('url')
