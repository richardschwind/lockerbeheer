from django import forms
from django.contrib import admin
from .models import Locker, LockerLocation


class LockerInline(admin.TabularInline):
    model = Locker
    extra = 1
    fields = ['number', 'size', 'status', 'floor', 'notes']
    show_change_link = True


@admin.register(LockerLocation)
class LockerLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'address', 'locker_count', 'created_at']
    list_filter = ['company']
    search_fields = ['name', 'address', 'company__name']
    autocomplete_fields = ['company']
    inlines = [LockerInline]

    def locker_count(self, obj):
        return obj.lockers.count()

    locker_count.short_description = 'Aantal lockers'


@admin.register(Locker)
class LockerAdmin(admin.ModelAdmin):
    class LockerAdminForm(forms.ModelForm):
        class Meta:
            model = Locker
            fields = '__all__'

        def clean(self):
            cleaned_data = super().clean()

            if not self.instance.pk:
                return cleaned_data

            current = Locker.objects.get(pk=self.instance.pk)
            locked_statuses = {
                Locker.Status.OCCUPIED,
                Locker.Status.OCCUPIED_PIN,
                Locker.Status.OCCUPIED_NFC,
            }
            if current.status not in locked_statuses:
                return cleaned_data

            tracked_fields = ['number', 'location', 'size', 'status', 'floor', 'notes']
            changed = [
                field
                for field in tracked_fields
                if field in cleaned_data and cleaned_data[field] != getattr(current, field)
            ]
            if changed:
                raise forms.ValidationError(
                    f"Locker {current.number} is bezet en kan niet via de website worden gewijzigd."
                )

            return cleaned_data

    form = LockerAdminForm
    list_display = ['number', 'company_name', 'location', 'size', 'status', 'floor', 'updated_at']
    list_filter = ['status', 'size', 'location', 'location__company']
    search_fields = ['number', 'location__name', 'location__company__name']
    list_select_related = ['location', 'location__company']
    autocomplete_fields = ['location']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basis', {'fields': ('number', 'location')}),
        ('Eigenschappen', {'fields': ('size', 'status', 'floor')}),
        ('Notities', {'fields': ('notes',)}),
        ('Tijdstempels', {'fields': ('created_at', 'updated_at')}),
    )

    def company_name(self, obj):
        return obj.location.company.name

    company_name.short_description = 'Bedrijf'

    def save_model(self, request, obj, form, change):
        if obj.pk and obj.status in {Locker.Status.OCCUPIED, Locker.Status.OCCUPIED_PIN}:
            from .access_rules import ensure_can_assign_pin

            ensure_can_assign_pin(obj)
        super().save_model(request, obj, form, change)
