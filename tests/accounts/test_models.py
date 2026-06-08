import pytest
from django.db import IntegrityError

from applications.models import Company, Job, JobApplication
from candidate_profile.models import CandidateProfile
from tests.factories import (
    CandidateProfileFactory,
    CompanyFactory,
    JobApplicationFactory,
    JobFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


class TestUserModel:
    def test_email_must_be_unique(self):
        UserFactory(email='colisao@exemplo.com')
        with pytest.raises(IntegrityError):
            UserFactory(email='colisao@exemplo.com')

    def test_new_user_is_not_deleted(self):
        user = UserFactory()
        assert user.is_deleted is False
        assert user.deleted_at is None


class TestUserSoftDelete:
    def test_active_manager_excludes_deleted_user(self):
        from accounts.models import User

        user = UserFactory()
        user.soft_delete()

        assert not User.objects.filter(pk=user.pk).exists()
        assert User.all_objects.filter(pk=user.pk).exists()

    def test_soft_delete_marks_timestamp(self):
        user = UserFactory()
        user.soft_delete()
        assert user.is_deleted is True
        assert user.deleted_at is not None

    def test_option_a_cascades_personal_data(self):
        user = UserFactory()
        application = JobApplicationFactory(user=user)
        profile = CandidateProfileFactory(user=user)

        user.soft_delete(keep_global_data=False)

        assert not JobApplication.objects.filter(pk=application.pk).exists()
        assert JobApplication.all_objects.get(pk=application.pk).deleted_at is not None
        assert not CandidateProfile.objects.filter(pk=profile.pk).exists()
        assert CandidateProfile.all_objects.get(pk=profile.pk).deleted_at is not None

    def test_option_a_nulls_created_by_on_global_resources(self):
        user = UserFactory()
        company = CompanyFactory(created_by=user)
        job = JobFactory(created_by=user, company=company)

        user.soft_delete(keep_global_data=False)

        company.refresh_from_db()
        job.refresh_from_db()
        assert company.created_by is None
        assert job.created_by is None

    def test_option_b_keeps_global_data_and_applications(self):
        user = UserFactory()
        company = CompanyFactory(created_by=user)
        application = JobApplicationFactory(user=user)

        user.soft_delete(keep_global_data=True)

        company.refresh_from_db()
        assert company.created_by == user
        # A candidatura nao foi apagada; some das queries so por causa do usuario.
        assert JobApplication.all_objects.get(pk=application.pk).deleted_at is None
