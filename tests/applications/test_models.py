import pytest

from applications.models import CompanyAuditLog, JobApplication
from tests.factories import (
    CompanyFactory,
    JobApplicationFactory,
    JobFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


class TestCompany:
    def test_str_returns_name(self):
        company = CompanyFactory(name='Acme S.A.')
        assert str(company) == 'Acme S.A.'


class TestJob:
    def test_str_includes_role_and_company(self):
        job = JobFactory(role_title='Engenheiro de Software', company__name='Acme')
        assert 'Engenheiro de Software' in str(job)
        assert 'Acme' in str(job)


class TestJobApplication:
    def test_default_status_is_draft(self):
        application = JobApplicationFactory()
        assert application.status == JobApplication.Status.DRAFT

    def test_default_origin_is_manual(self):
        application = JobApplicationFactory()
        assert application.origin == JobApplication.Origin.MANUAL

    def test_str_includes_role_and_status(self):
        application = JobApplicationFactory(job__role_title='Dev Backend')
        assert 'Dev Backend' in str(application)
        assert 'Rascunho' in str(application)

    def test_active_manager_excludes_application_of_deleted_user(self):
        user = UserFactory()
        application = JobApplicationFactory(user=user)
        assert JobApplication.objects.filter(pk=application.pk).exists()

        user.soft_delete(keep_global_data=True)
        assert not JobApplication.objects.filter(pk=application.pk).exists()


class TestCompanyAuditLog:
    def test_log_change_creates_record(self):
        user = UserFactory()
        company = CompanyFactory(created_by=user)

        log = CompanyAuditLog.log_change(
            company=company,
            user=user,
            action=CompanyAuditLog.Action.UPDATED,
            field_name='name',
            old_value='Antigo',
            new_value='Novo',
        )

        assert log.pk is not None
        assert company.audit_logs.count() == 1
        assert log.action == CompanyAuditLog.Action.UPDATED
        assert log.old_value == 'Antigo'
        assert log.new_value == 'Novo'
