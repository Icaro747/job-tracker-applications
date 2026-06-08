"""Rotas de contas de e-mail, conexao Gmail e regras de varredura (Etapa 3)."""
from django.urls import path

from . import views

app_name = 'email_ingestion'

urlpatterns = [
    # Contas de e-mail
    path('', views.EmailAccountListView.as_view(), name='account_list'),
    path('contas/<int:pk>/', views.EmailAccountDetailView.as_view(), name='account_detail'),
    path('contas/<int:pk>/editar/', views.EmailAccountUpdateView.as_view(), name='account_update'),
    path('contas/<int:pk>/excluir/', views.EmailAccountDeleteView.as_view(), name='account_delete'),
    path('contas/<int:pk>/ativar/', views.account_toggle_active, name='account_toggle_active'),
    path('contas/<int:pk>/desconectar/', views.account_disconnect, name='account_disconnect'),
    # Conexao Gmail (OAuth dedicado)
    path('gmail/conectar/', views.gmail_connect, name='gmail_connect'),
    path('gmail/callback/', views.gmail_callback, name='gmail_callback'),
    # Regras de varredura
    path(
        'contas/<int:account_pk>/regras/nova/',
        views.EmailSenderRuleCreateView.as_view(),
        name='rule_create',
    ),
    path('regras/<int:pk>/editar/', views.EmailSenderRuleUpdateView.as_view(), name='rule_update'),
    path('regras/<int:pk>/excluir/', views.EmailSenderRuleDeleteView.as_view(), name='rule_delete'),
]
