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
    pi_name = serializers.SerializerMethodField()
    pi_status = serializers.SerializerMethodField()
    pi_status_display = serializers.SerializerMethodField()
    pi_last_sync = serializers.SerializerMethodField()
    pi_last_sync_ago = serializers.SerializerMethodField()
    connection_status = serializers.SerializerMethodField()
    connection_status_display = serializers.SerializerMethodField()
    whitelist_status = serializers.SerializerMethodField()
    whitelist_status_display = serializers.SerializerMethodField()

    class Meta:
        model = Locker
        fields = [
            'id', 'number', 'company_id', 'company_name', 'location', 'location_name',
            'size', 'size_display', 'status', 'status_display',
            'pi_name', 'pi_status', 'pi_status_display', 'pi_last_sync', 'pi_last_sync_ago',
            'connection_status', 'connection_status_display',
            'whitelist_status', 'whitelist_status_display',
            'floor', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _get_location_pi(self, obj):
        location = getattr(obj, 'location', None)
        if not location:
            return None

        prefetched = getattr(location, '_prefetched_objects_cache', {}).get('raspberry_pis')
        pis = list(prefetched) if prefetched is not None else list(location.raspberry_pis.all())
        if not pis:
            return None

        active_pis = [pi for pi in pis if pi.is_active]
        return active_pis[0] if active_pis else pis[0]

    def _get_last_sync_ago(self, pi):
        if not pi or not pi.last_sync:
            return 'Nooit'

        from django.utils import timezone

        delta = timezone.now() - pi.last_sync
        minutes = delta.total_seconds() // 60
        if minutes < 1:
            return 'Nu'
        if minutes < 60:
            return f'{int(minutes)}m geleden'

        hours = minutes // 60
        if hours < 24:
            return f'{int(hours)}h geleden'

        days = hours // 24
        return f'{int(days)}d geleden'

    def get_pi_name(self, obj):
        pi = self._get_location_pi(obj)
        return pi.name if pi else None

    def get_pi_status(self, obj):
        pi = self._get_location_pi(obj)
        return pi.status if pi else 'unconfigured'

    def get_pi_status_display(self, obj):
        pi = self._get_location_pi(obj)
        if not pi:
            return 'Geen Pi gekoppeld'
        return pi.get_status_display()

    def get_pi_last_sync(self, obj):
        pi = self._get_location_pi(obj)
        return pi.last_sync if pi else None

    def get_pi_last_sync_ago(self, obj):
        return self._get_last_sync_ago(self._get_location_pi(obj))

    def get_connection_status(self, obj):
        pi = self._get_location_pi(obj)
        if not pi:
            return 'unconfigured'
        return 'connected' if pi.status == 'online' else 'disconnected'

    def get_connection_status_display(self, obj):
        status = self.get_connection_status(obj)
        if status == 'connected':
            return 'Verbonden'
        if status == 'disconnected':
            return 'Geen verbinding'
        return 'Geen Pi gekoppeld'

    def get_whitelist_status(self, obj):
        pi = self._get_location_pi(obj)
        if not pi:
            return 'unconfigured'

        if not obj.whitelist_changed_at:
            return 'synced'

        if not pi.last_whitelist_ack_at or pi.last_whitelist_ack_at < obj.whitelist_changed_at:
            return 'pending'

        return 'synced'

    def get_whitelist_status_display(self, obj):
        status = self.get_whitelist_status(obj)
        if status == 'pending':
            return 'Nieuwe whitelist gereed'
        if status == 'synced':
            return 'Whitelist gesynchroniseerd'
        return 'Geen Pi gekoppeld'

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
