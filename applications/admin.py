from django.contrib import admin

from .models import (
    ApplicationTimelineEntry,
    Company,
    CompanyAuditLog,
    Job,
    JobApplication,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'careers_page', 'created_by', 'updated_at')
    search_fields = ('name', 'website')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CompanyAuditLog)
class CompanyAuditLogAdmin(admin.ModelAdmin):
    list_display = ('company', 'action', 'field_name', 'user', 'changed_at')
    list_filter = ('action',)
    search_fields = ('company__name', 'field_name')
    readonly_fields = (
        'company', 'user', 'action', 'field_name', 'old_value', 'new_value', 'changed_at',
    )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('role_title', 'company', 'location', 'remote', 'directed_to', 'created_at')
    list_filter = ('remote', 'company')
    search_fields = ('role_title', 'company__name', 'location')


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('job', 'user', 'status', 'origin', 'next_action_at', 'updated_at')
    list_filter = ('status', 'origin')
    search_fields = ('job__role_title', 'job__company__name', 'user__email')
    date_hierarchy = 'updated_at'


@admin.register(ApplicationTimelineEntry)
class ApplicationTimelineEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'application', 'entry_type', 'occurred_at')
    list_filter = ('entry_type',)
    search_fields = ('title', 'description', 'application__job__role_title')
