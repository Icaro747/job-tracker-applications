"""Rotas da operacao manual (Etapa 2)."""
from django.urls import path

from . import views

app_name = 'applications'

urlpatterns = [
    # Empresas
    path('empresas/', views.CompanyListView.as_view(), name='company_list'),
    path('empresas/nova/', views.CompanyCreateView.as_view(), name='company_create'),
    path('empresas/<int:pk>/', views.CompanyDetailView.as_view(), name='company_detail'),
    path('empresas/<int:pk>/editar/', views.CompanyUpdateView.as_view(), name='company_update'),
    path('empresas/<int:pk>/excluir/', views.CompanyDeleteView.as_view(), name='company_delete'),
    # Vagas
    path('vagas/', views.JobListView.as_view(), name='job_list'),
    path('vagas/nova/', views.JobCreateView.as_view(), name='job_create'),
    path('vagas/<int:pk>/', views.JobDetailView.as_view(), name='job_detail'),
    path('vagas/<int:pk>/editar/', views.JobUpdateView.as_view(), name='job_update'),
    path('vagas/<int:pk>/excluir/', views.JobDeleteView.as_view(), name='job_delete'),
    # Candidaturas
    path('candidaturas/', views.ApplicationListView.as_view(), name='application_list'),
    path('candidaturas/nova/', views.ApplicationCreateView.as_view(), name='application_create'),
    path('candidaturas/<int:pk>/', views.ApplicationDetailView.as_view(), name='application_detail'),
    path('candidaturas/<int:pk>/editar/', views.ApplicationUpdateView.as_view(), name='application_update'),
    path('candidaturas/<int:pk>/excluir/', views.ApplicationDeleteView.as_view(), name='application_delete'),
    # Acoes HTMX da candidatura
    path('candidaturas/<int:pk>/status/', views.application_change_status, name='application_status'),
    path('candidaturas/<int:pk>/nota/', views.application_add_note, name='application_note'),
    path(
        'candidaturas/<int:pk>/proxima-acao/',
        views.application_set_next_action,
        name='application_next_action',
    ),
    path(
        'candidaturas/<int:pk>/proxima-acao/concluir/',
        views.application_complete_next_action,
        name='application_complete_next_action',
    ),
]
