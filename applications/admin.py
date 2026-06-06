from django.contrib import admin

from .models import ApplicationTimelineEntry, Company, JobApplication


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'careers_page', 'created_at')
    search_fields = ('name', 'website')


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('role_title', 'company', 'status', 'applied_at', 'next_action_at', 'updated_at')
    list_filter = ('status', 'remote', 'company')
    search_fields = ('role_title', 'company__name', 'location')
    date_hierarchy = 'updated_at'


@admin.register(ApplicationTimelineEntry)
class ApplicationTimelineEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'application', 'entry_type', 'occurred_at')
    list_filter = ('entry_type',)
    search_fields = ('title', 'description', 'application__role_title', 'application__company__name')
