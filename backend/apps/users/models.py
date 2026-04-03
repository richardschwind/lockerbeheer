from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class Company(models.Model):
    """Klant/bedrijf dat lockers beheert."""

    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Bedrijf'
        verbose_name_plural = 'Bedrijven'

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Website-gebruiker (beheerder of medewerker van een bedrijf)."""

    class Role(models.TextChoices):
        SUPERADMIN = 'superadmin', 'Superadmin'
        COMPANY_ADMIN = 'company_admin', 'Bedrijfsbeheerder'
        COMPANY_USER = 'company_user', 'Bedrijfsgebruiker'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.COMPANY_USER)
    phone = models.CharField(max_length=20, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        ordering = ['username']
        verbose_name = 'Gebruiker'
        verbose_name_plural = 'Gebruikers'

    def __str__(self):
        return self.username

    @property
    def is_superadmin(self):
        return self.role == self.Role.SUPERADMIN or self.is_superuser

    @property
    def is_company_admin(self):
        return self.role == self.Role.COMPANY_ADMIN


class LockerUser(models.Model):
    """Fysieke lockergebruiker gekoppeld aan een website-gebruiker."""

    website_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='locker_users',
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    employee_number = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Lockergebruiker'
        verbose_name_plural = 'Lockergebruikers'

    def __str__(self):
        company_name = self.company.name if self.company else 'Geen bedrijf'
        return f"{self.first_name} {self.last_name} ({company_name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def company(self):
        return self.website_user.company if self.website_user else None


class NFCTag(models.Model):
    """NFC tag toegewezen aan een lockergebruiker."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Actief'
        LOST = 'lost', 'Verloren'
        DEACTIVATED = 'deactivated', 'Gedeactiveerd'

    uid = models.CharField(max_length=100, unique=True, verbose_name='Tag UID')
    locker_user = models.ForeignKey(
        LockerUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nfc_tags'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    issued_at = models.DateField(auto_now_add=True)
    lost_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'NFC Tag'
        verbose_name_plural = 'NFC Tags'

    def __str__(self):
        user_str = str(self.locker_user) if self.locker_user else 'Niet toegewezen'
        return f"NFC {self.uid} – {user_str} ({self.get_status_display()})"

    def clean(self):
        super().clean()

        if self.status != self.Status.ACTIVE or not self.locker_user_id:
            return

        from apps.lockers.access_rules import ensure_can_assign_nfc
        from apps.rentals.models import Rental

        active_rentals = Rental.objects.filter(
            locker_user_id=self.locker_user_id,
            status=Rental.Status.ACTIVE,
        ).select_related('locker')

        for rental in active_rentals:
            try:
                ensure_can_assign_nfc(rental.locker, exclude_tag_id=self.pk)
            except ValidationError as exc:
                message = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
                raise ValidationError({'locker_user': message})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
