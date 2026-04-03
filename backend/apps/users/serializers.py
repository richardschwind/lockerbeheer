from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from .models import User, Company, LockerUser, NFCTag


class CompanySerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(source='users.count', read_only=True)
    locker_user_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ['id', 'name', 'address', 'city', 'phone', 'email', 'is_active',
                  'user_count', 'locker_user_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_locker_user_count(self, obj):
        return LockerUser.objects.filter(website_user__company=obj).count()


class UserSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone',
                  'role', 'company', 'company_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone',
                  'role', 'company', 'password', 'password2']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Wachtwoorden komen niet overeen.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class NFCTagSerializer(serializers.ModelSerializer):
    locker_user_name = serializers.CharField(source='locker_user.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = NFCTag
        fields = ['id', 'uid', 'locker_user', 'locker_user_name', 'status', 'status_display',
                  'issued_at', 'lost_at', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'issued_at', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs = super().validate(attrs)

        status = attrs.get('status', self.instance.status if self.instance else NFCTag.Status.ACTIVE)
        locker_user = attrs.get('locker_user', self.instance.locker_user if self.instance else None)

        if status != NFCTag.Status.ACTIVE or not locker_user:
            return attrs

        from apps.lockers.access_rules import ensure_can_assign_nfc
        from apps.rentals.models import Rental

        active_rentals = Rental.objects.filter(
            locker_user=locker_user,
            status=Rental.Status.ACTIVE,
        ).select_related('locker')

        for rental in active_rentals:
            try:
                ensure_can_assign_nfc(rental.locker, exclude_tag_id=self.instance.pk if self.instance else None)
            except DjangoValidationError as exc:
                message = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
                raise serializers.ValidationError({'message': message})

        return attrs


class LockerUserSerializer(serializers.ModelSerializer):
    website_user_username = serializers.CharField(source='website_user.username', read_only=True)
    company_name = serializers.CharField(source='website_user.company.name', read_only=True)
    full_name = serializers.CharField(read_only=True)
    active_nfc_tag = serializers.SerializerMethodField()

    class Meta:
        model = LockerUser
        fields = ['id', 'website_user', 'website_user_username', 'company_name', 'first_name', 'last_name', 'full_name',
                  'email', 'phone', 'employee_number', 'is_active', 'notes',
                  'active_nfc_tag', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_website_user(self, value):
        if value is None:
            raise serializers.ValidationError('Website-gebruiker is verplicht.')
        if not value.company:
            raise serializers.ValidationError('Gekozen website-gebruiker is niet gekoppeld aan een bedrijf.')
        return value

    def validate(self, attrs):
        website_user = attrs.get('website_user', self.instance.website_user if self.instance else None)
        if website_user is None:
            raise serializers.ValidationError({'website_user': 'Website-gebruiker is verplicht.'})
        return attrs

    def get_active_nfc_tag(self, obj):
        tag = obj.nfc_tags.filter(status=NFCTag.Status.ACTIVE).first()
        if tag:
            return {'id': tag.id, 'uid': tag.uid}
        return None
