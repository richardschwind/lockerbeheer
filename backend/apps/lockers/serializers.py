from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Locker, LockerLocation


class LockerLocationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    locker_count = serializers.IntegerField(source='lockers.count', read_only=True)

    class Meta:
        model = LockerLocation
        fields = ['id', 'company', 'company_name', 'name', 'address', 'description', 'locker_count', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'company': {'required': False},
        }


class LockerSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(source='location.company_id', read_only=True)
    company_name = serializers.CharField(source='location.company.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    size_display = serializers.CharField(source='get_size_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Locker
        fields = [
            'id', 'number', 'company_id', 'company_name', 'location', 'location_name',
            'size', 'size_display', 'status', 'status_display',
            'floor', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        if self.instance:
            locked_statuses = {
                Locker.Status.OCCUPIED,
                Locker.Status.OCCUPIED_PIN,
                Locker.Status.OCCUPIED_NFC,
            }
            if self.instance.status in locked_statuses:
                tracked_fields = ['number', 'location', 'size', 'status', 'floor', 'notes']
                has_changes = any(
                    field in attrs and attrs[field] != getattr(self.instance, field)
                    for field in tracked_fields
                )
                if has_changes:
                    raise serializers.ValidationError({
                        'message': f'Locker {self.instance.number} is bezet en kan niet via de website worden gewijzigd.'
                    })

        status = attrs.get('status', self.instance.status if self.instance else Locker.Status.AVAILABLE)
        if self.instance and status in {Locker.Status.OCCUPIED, Locker.Status.OCCUPIED_PIN}:
            from .access_rules import ensure_can_assign_pin

            try:
                ensure_can_assign_pin(self.instance)
            except DjangoValidationError as exc:
                message = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
                raise serializers.ValidationError({'message': message})
        return attrs
