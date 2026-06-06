from django.contrib import admin

from .models import ApplicationReminder, CalendarEvent


@admin.register(ApplicationReminder)
class ApplicationReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'application', 'user', 'due_at', 'channel', 'status')
    list_filter = ('channel', 'status')
    search_fields = ('title', 'description', 'application__role_title', 'application__company__name')
    date_hierarchy = 'due_at'


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'application', 'user', 'starts_at', 'status')
    list_filter = ('status',)
    search_fields = ('title', 'description', 'application__role_title', 'application__company__name')
    date_hierarchy = 'starts_at'
