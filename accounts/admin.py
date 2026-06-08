from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'deleted_at')
    list_filter = BaseUserAdmin.list_filter + ('deleted_at',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Soft delete', {'fields': ('deleted_at',)}),
    )
    readonly_fields = ('deleted_at',)
