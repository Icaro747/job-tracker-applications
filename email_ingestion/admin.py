from django.contrib import admin

from .models import EmailAccount, EmailClassification, EmailSenderRule, InboundEmail


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ('email_address', 'user', 'provider', 'is_active', 'last_scan_at')
    list_filter = ('provider', 'is_active')
    search_fields = ('email_address', 'user__email')
    # Tokens nunca sao exibidos/editados pelo Admin.
    exclude = ('access_token', 'refresh_token')
    readonly_fields = ('token_expiry', 'last_scan_at', 'created_at')


@admin.register(EmailSenderRule)
class EmailSenderRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'email_account', 'company', 'sender_email', 'sender_domain', 'is_active')
    list_filter = ('is_active', 'company')
    search_fields = ('name', 'sender_email', 'sender_domain', 'company__name')


@admin.register(InboundEmail)
class InboundEmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'processing_status', 'application', 'received_at')
    list_filter = ('processing_status', 'matched_rule')
    search_fields = ('subject', 'sender', 'body_text')
    date_hierarchy = 'received_at'


@admin.register(EmailClassification)
class EmailClassificationAdmin(admin.ModelAdmin):
    list_display = ('email', 'suggested_status', 'confidence', 'reviewed_by', 'reviewed_at')
    search_fields = ('email__subject', 'summary', 'rationale')
