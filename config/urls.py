"""URL configuration for config project."""
from applications.views import home
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('email/', include('email_ingestion.urls')),
    path('', include('applications.urls')),
]
