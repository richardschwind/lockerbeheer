from rest_framework import serializers
from .models import RaspberryPi, AccessEvent


class PiSyncEventSerializer(serializers.Serializer):
    locker_number = serializers.IntegerField(required=True)
    credential_type = serializers.ChoiceField(choices=['pin', 'nfc', 'system'])
    credential_value = serializers.CharField(required=False, allow_blank=True, default='')
    success = serializers.BooleanField()
    message = serializers.CharField(required=False, allow_blank=True, default='')
    timestamp = serializers.DateTimeField(required=True)
    locker_state = serializers.ChoiceField(
        choices=[
            AccessEvent.LockerState.FREE,
            AccessEvent.LockerState.OCCUPIED_PIN,
            AccessEvent.LockerState.OCCUPIED_NFC,
            AccessEvent.LockerState.OPENED_AND_RELEASED,
            AccessEvent.LockerState.CONFLICT,
            AccessEvent.LockerState.UNKNOWN,
        ],
        required=False,
        default=AccessEvent.LockerState.UNKNOWN,
    )


class RaspberryPiSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    last_sync_ago = serializers.SerializerMethodField()

    class Meta:
        model = RaspberryPi
        fields = ['id', 'company', 'company_name', 'name', 'unique_code', 'location', 'location_name',
                  'status', 'status_display', 'last_sync', 'last_sync_ago', 'last_ip',
                  'is_active', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'api_key', 'last_sync', 'last_ip', 'created_at', 'updated_at']

    def get_last_sync_ago(self, obj):
        if obj.last_sync:
            from django.utils import timezone
            delta = timezone.now() - obj.last_sync
            minutes = delta.total_seconds() // 60
            if minutes < 1:
                return 'Nu'
            elif minutes < 60:
                return f'{int(minutes)}m geleden'
            else:
                hours = minutes // 60
                if hours < 24:
                    return f'{int(hours)}h geleden'
                else:
                    days = hours // 24
                    return f'{int(days)}d geleden'
        return 'Nooit'


class AccessEventSerializer(serializers.ModelSerializer):
    raspberry_pi_name = serializers.CharField(source='raspberry_pi.name', read_only=True)
    locker_number_display = serializers.CharField(source='locker.number', read_only=True)
    credential_type_display = serializers.CharField(source='get_credential_type_display', read_only=True)
    locker_state_display = serializers.CharField(source='get_locker_state_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AccessEvent
        fields = ['id', 'raspberry_pi', 'raspberry_pi_name', 'locker', 'locker_number',
                  'locker_number_display', 'credential_type', 'credential_type_display',
                  'credential_value', 'locker_state', 'locker_state_display',
                  'status', 'status_display', 'message',
                  'synced_at', 'pi_timestamp', 'created_at']
        read_only_fields = ['id', 'synced_at', 'created_at']


class PiSyncRequestSerializer(serializers.Serializer):
    """Serializer voor inkomende Pi sync requests."""

    events = serializers.ListField(
        child=serializers.DictField(),
        help_text='Array van access events van de Pi'
    )

    def validate_events(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Events moet een array zijn.')
        if len(value) > 1000:
            raise serializers.ValidationError('Maximaal 1000 events per sync.')
        return value


class PiSyncResponseSerializer(serializers.Serializer):
    """Serializer voor reactie op Pi sync."""

    success = serializers.BooleanField()
    synced_count = serializers.IntegerField()
    failed_count = serializers.IntegerField(required=False)
    failed_indices = serializers.ListField(child=serializers.IntegerField(), required=False)
    message = serializers.CharField()
    errors = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
