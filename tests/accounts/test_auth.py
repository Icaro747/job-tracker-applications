import pytest
from django.urls import reverse

from accounts.models import User
from tests.factories import TEST_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


class TestHomeAccess:
    def test_anonymous_is_redirected_to_login(self, client):
        response = client.get('/')
        assert response.status_code == 302
        assert reverse('account_login') in response.url

    def test_authenticated_user_sees_home(self, auth_client):
        response = auth_client.get('/')
        assert response.status_code == 200


class TestSignup:
    def test_signup_creates_user_and_authenticates(self, client):
        response = client.post(
            reverse('account_signup'),
            {
                'email': 'novo@exemplo.com',
                'password1': 'umaSenhaForte123',
                'password2': 'umaSenhaForte123',
            },
        )
        assert response.status_code == 302
        assert User.objects.filter(email='novo@exemplo.com').exists()
        # Usuario fica autenticado apos o cadastro.
        assert '_auth_user_id' in client.session


class TestLogin:
    def test_login_with_email_and_password(self, client):
        user = UserFactory(email='login@exemplo.com')
        response = client.post(
            reverse('account_login'),
            {'login': 'login@exemplo.com', 'password': TEST_PASSWORD},
        )
        assert response.status_code == 302
        assert client.session.get('_auth_user_id') == str(user.pk)
