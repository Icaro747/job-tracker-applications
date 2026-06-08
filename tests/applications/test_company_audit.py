"""Auditoria de empresa: um registro por campo alterado (spec 02 e 10)."""
import pytest

from applications.models import Company, CompanyAuditLog
from tests.factories import CompanyFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestCompanyAudit:
    def test_record_create_logs_single_created_entry(self):
        user = UserFactory()
        company = CompanyFactory(name='Acme')

        CompanyAuditLog.record_create(company, user)

        logs = company.audit_logs.all()
        assert logs.count() == 1
        assert logs[0].action == CompanyAuditLog.Action.CREATED
        assert logs[0].user == user

    def test_record_update_logs_one_entry_per_changed_field(self):
        user = UserFactory()
        company = CompanyFactory(name='Antigo', website='https://antigo.com')
        old_values = {
            'name': company.name,
            'website': company.website,
            'careers_page': company.careers_page,
            'notes': company.notes,
        }

        company.name = 'Novo'
        company.website = 'https://novo.com'
        company.save()
        CompanyAuditLog.record_update(company, user, old_values)

        updates = company.audit_logs.filter(action=CompanyAuditLog.Action.UPDATED)
        assert updates.count() == 2
        by_field = {log.field_name: log for log in updates}
        assert by_field['name'].old_value == 'Antigo'
        assert by_field['name'].new_value == 'Novo'
        assert by_field['website'].old_value == 'https://antigo.com'
        assert by_field['website'].new_value == 'https://novo.com'

    def test_record_update_no_changes_logs_nothing(self):
        user = UserFactory()
        company = CompanyFactory(name='Estavel')
        old_values = {
            'name': company.name,
            'website': company.website,
            'careers_page': company.careers_page,
            'notes': company.notes,
        }

        CompanyAuditLog.record_update(company, user, old_values)

        assert company.audit_logs.count() == 0

    def test_record_delete_logs_single_deleted_entry(self):
        user = UserFactory()
        company = CompanyFactory()

        CompanyAuditLog.record_delete(company, user)

        logs = company.audit_logs.filter(action=CompanyAuditLog.Action.DELETED)
        assert logs.count() == 1
