import pytest

from email_ingestion.models import EmailAccount
from tests.factories import EmailAccountFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_soft_delete_removes_email_accounts():
    user = UserFactory()
    EmailAccountFactory(user=user)
    EmailAccountFactory(user=user, email_address='outra@gmail.com')

    user.soft_delete(keep_global_data=False)

    assert EmailAccount.objects.filter(user=user).count() == 0


def test_soft_delete_keeping_global_data_still_removes_accounts():
    # Credenciais nao tem valor sem o dono — sao removidas em ambos os modos.
    user = UserFactory()
    EmailAccountFactory(user=user)

    user.soft_delete(keep_global_data=True)

    assert EmailAccount.objects.filter(user=user).count() == 0
