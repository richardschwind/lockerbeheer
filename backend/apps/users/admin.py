from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Company, LockerUser, NFCTag
from apps.lockers.models import Locker
from apps.lockers.models import LockerLocation


class CompanyUserInline(admin.TabularInline):
    model = User
    fk_name = 'company'
    extra = 0
    fields = ['username', 'email', 'role', 'is_active']
    show_change_link = True


class CompanyLockerInline(admin.TabularInline):
    model = LockerLocation
    fk_name = 'company'
    extra = 0
    fields = ['name', 'address', 'description']
    show_change_link = True


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'phone', 'email', 'is_active', 'user_count', 'locker_count', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'city', 'email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [CompanyUserInline, CompanyLockerInline]

    fieldsets = (
        ('Bedrijf', {'fields': ('name', 'is_active')}),
        ('Contact', {'fields': ('address', 'city', 'phone', 'email')}),
        ('Tijdstempels', {'fields': ('created_at', 'updated_at')}),
    )

    def user_count(self, obj):
        return obj.users.count()

    user_count.short_description = 'Websitegebruikers'

    def locker_count(self, obj):
        return Locker.objects.filter(location__company=obj).count()

    locker_count.short_description = 'Lockers'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'company', 'is_active']
    list_filter = ['role', 'is_active', 'company']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['username']
    list_select_related = ['company']
    autocomplete_fields = ['company']

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra velden', {'fields': ('email', 'first_name', 'last_name', 'role', 'phone', 'company')}),
    )

    fieldsets = UserAdmin.fieldsets + (
        ('Extra velden', {'fields': ('role', 'phone', 'company')}),
    )


@admin.register(LockerUser)
class LockerUserAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'website_user', 'company_name', 'employee_number', 'email', 'phone', 'is_active']
    list_filter = ['is_active', 'website_user__company']
    search_fields = ['first_name', 'last_name', 'email', 'employee_number', 'website_user__username']
    list_select_related = ['website_user', 'website_user__company']
    autocomplete_fields = ['website_user']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Koppeling', {'fields': ('website_user',)}),
        ('Persoon', {'fields': ('first_name', 'last_name', 'employee_number')}),
        ('Contact', {'fields': ('email', 'phone')}),
        ('Status', {'fields': ('is_active', 'notes')}),
        ('Tijdstempels', {'fields': ('created_at', 'updated_at')}),
    )

    def company_name(self, obj):
        return obj.company.name if obj.company else '-'

    company_name.short_description = 'Bedrijf'


@admin.register(NFCTag)
class NFCTagAdmin(admin.ModelAdmin):
    list_display = ['uid', 'locker_user', 'company_name', 'status', 'issued_at', 'lost_at']
    list_filter = ['status']
    search_fields = ['uid', 'locker_user__first_name', 'locker_user__last_name']
    list_select_related = ['locker_user', 'locker_user__website_user', 'locker_user__website_user__company']
    autocomplete_fields = ['locker_user']
    readonly_fields = ['issued_at', 'created_at', 'updated_at']

    fieldsets = (
        ('Tag', {'fields': ('uid', 'status')}),
        ('Toewijzing', {'fields': ('locker_user',)}),
        ('Verlies/Notities', {'fields': ('lost_at', 'notes')}),
        ('Tijdstempels', {'fields': ('issued_at', 'created_at', 'updated_at')}),
    )

    def company_name(self, obj):
        locker_user = obj.locker_user
        if locker_user and locker_user.company:
            return locker_user.company.name
        return '-'

    company_name.short_description = 'Bedrijf'
