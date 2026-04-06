from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.lockers.serializers import LockerSerializer
from apps.users.serializers import LockerUserSerializer, UserSerializer
from .models import Rental


class RentalSerializer(serializers.ModelSerializer):
    locker_detail = LockerSerializer(source='locker', read_only=True)
    locker_user_detail = LockerUserSerializer(source='locker_user', read_only=True)
    created_by_detail = UserSerializer(source='created_by', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Rental
        fields = [
            'id', 'locker_user', 'locker_user_detail', 'locker', 'locker_detail',
            'created_by', 'created_by_detail', 'status', 'status_display',
            'start_date', 'end_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        locker = attrs.get('locker', self.instance.locker if self.instance else None)
        locker_user = attrs.get('locker_user', self.instance.locker_user if self.instance else None)
        status = attrs.get('status', self.instance.status if self.instance else Rental.Status.ACTIVE)
        start_date = attrs.get('start_date', self.instance.start_date if self.instance else None)
        end_date = attrs.get('end_date', self.instance.end_date if self.instance else None)
        notes = attrs.get('notes', self.instance.notes if self.instance else '')

        if not locker or not locker_user or status != Rental.Status.ACTIVE:
            return attrs

        try:
            rental = self.instance or Rental()
            rental.locker = locker
            rental.locker_user = locker_user
            rental.status = status
            rental.start_date = start_date
            rental.end_date = end_date
            rental.notes = notes
            rental.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, 'message_dict'):
                raise serializers.ValidationError(exc.message_dict)
            message = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
            raise serializers.ValidationError({'message': message})
        return attrs
