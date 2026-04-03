from django import forms
from django.contrib import admin

from apps.lockers.models import Locker

from .models import Rental


class RentalAdminForm(forms.ModelForm):
    class Meta:
        model = Rental
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        locker = cleaned_data.get('locker')
        status = cleaned_data.get('status')

        is_same_active_rental = bool(self.instance.pk) and self.instance.status == Rental.Status.ACTIVE and self.instance.locker_id == getattr(locker, 'id', None)

        if (
            locker
            and status == Rental.Status.ACTIVE
            and locker.status in {Locker.Status.OCCUPIED, Locker.Status.OCCUPIED_PIN}
            and not is_same_active_rental
        ):
            message = f'Locker {locker.number} is al bezet via PIN. Koppel hier geen nieuwe huurovereenkomst aan.'
            self.add_error('locker', message)
            self.add_error(None, message)

        return cleaned_data


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    form = RentalAdminForm
    list_display = ['locker_user', 'company_name', 'locker', 'status', 'start_date', 'end_date', 'created_by', 'created_at']
    list_filter = ['status', 'locker__location', 'locker_user__website_user__company']
    search_fields = ['locker_user__first_name', 'locker_user__last_name', 'locker__number']
    list_editable = ['status']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    list_select_related = ['locker_user', 'locker', 'locker_user__website_user', 'locker_user__website_user__company', 'created_by']
    autocomplete_fields = ['locker_user', 'locker', 'created_by']

    fieldsets = (
        ('Koppeling', {'fields': ('locker_user', 'locker')}),
        ('Status & periode', {'fields': ('status', 'start_date', 'end_date')}),
        ('Notities', {'fields': ('notes',)}),
        ('Audit', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'locker',
            'locker_user',
            'locker_user__website_user',
            'locker_user__website_user__company',
            'created_by',
        )

    def company_name(self, obj):
        locker_user = obj.locker_user
        if locker_user and locker_user.company:
            return locker_user.company.name
        return '-'

    company_name.short_description = 'Bedrijf'

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
