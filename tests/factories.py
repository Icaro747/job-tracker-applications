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
