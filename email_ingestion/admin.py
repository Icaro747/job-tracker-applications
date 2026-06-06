from django.contrib import admin

from .models import EmailClassification, EmailSenderRule, InboundEmail


@admin.register(EmailSenderRule)
class EmailSenderRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'sender_email', 'sender_domain', 'is_active', 'created_by')
    list_filter = ('is_active', 'company')
    search_fields = ('name', 'sender_email', 'sender_domain', 'company__name')


@admin.register(InboundEmail)
class InboundEmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'processing_status', 'application', 'received_at')
    list_filter = ('processing_status', 'matched_rule')
    search_fields = ('subject', 'sender', 'body_text', 'application__role_title')
    date_hierarchy = 'received_at'


@admin.register(EmailClassification)
class EmailClassificationAdmin(admin.ModelAdmin):
    list_display = ('email', 'suggested_status', 'confidence', 'reviewed_at')
    search_fields = ('email__subject', 'summary', 'rationale')
