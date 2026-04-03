from django.contrib import admin
from .models import RaspberryPi, AccessEvent


@admin.register(RaspberryPi)
class RaspberryPiAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'location', 'unique_code', 'status', 'last_sync', 'last_ip', 'is_active']
    list_filter = ['status', 'is_active', 'company', 'created_at']
    search_fields = ['name', 'unique_code', 'location__name', 'last_ip']
    list_select_related = ['company', 'location']
    readonly_fields = ['api_key', 'created_at', 'updated_at', 'last_sync', 'last_ip']

    fieldsets = (
        ('Basis', {'fields': ('company', 'name', 'unique_code', 'is_active')}),
        ('Locatie', {'fields': ('location',)}),
        ('Connection', {'fields': ('status', 'last_sync', 'last_ip', 'api_key')}),
        ('Notities', {'fields': ('notes',)}),
        ('Tijdstempels', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(AccessEvent)
class AccessEventAdmin(admin.ModelAdmin):
    list_display = ['pi_timestamp', 'raspberry_pi', 'locker_number', 'credential_type', 'locker_state', 'status', 'synced_at']
    list_filter = ['status', 'credential_type', 'locker_state', 'raspberry_pi__company', 'pi_timestamp']
    search_fields = ['raspberry_pi__name', 'locker__number', 'credential_value']
    list_select_related = ['raspberry_pi', 'locker']
    readonly_fields = ['created_at', 'synced_at']
    date_hierarchy = 'pi_timestamp'
    list_per_page = 100

    fieldsets = (
        ('Device', {'fields': ('raspberry_pi', 'locker')}),
        ('Locker', {'fields': ('locker_number',)}),
        ('Credential', {'fields': ('credential_type', 'credential_value')}),
        ('Resultaat', {'fields': ('status', 'locker_state', 'message')}),
        ('Sync', {'fields': ('pi_timestamp', 'synced_at')}),
        ('Audit', {'fields': ('created_at',)}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
