from django.contrib import admin

from .models import AutofillFieldMapping, AutofillSuggestion


@admin.register(AutofillFieldMapping)
class AutofillFieldMappingAdmin(admin.ModelAdmin):
    list_display = ('site_domain', 'field_label', 'field_name', 'profile_source')
    list_filter = ('site_domain',)
    search_fields = ('site_domain', 'field_label', 'field_name', 'profile_source')


@admin.register(AutofillSuggestion)
class AutofillSuggestionAdmin(admin.ModelAdmin):
    list_display = ('field_label', 'site_domain', 'user', 'application', 'status', 'created_at')
    list_filter = ('status', 'site_domain')
    search_fields = ('site_domain', 'field_label', 'field_name', 'suggested_value')
