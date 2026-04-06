from django.db import models
from apps.users.models import Company
from apps.lockers.models import Locker
from apps.lockers.models import LockerLocation


class RaspberryPi(models.Model):
    """Raspberry Pi device dat lockers beheert."""

    class Status(models.TextChoices):
        ONLINE = 'online', 'Online'
        OFFLINE = 'offline', 'Offline'
        ERROR = 'error', 'Fout'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='raspberry_pis'
    )
    name = models.CharField(max_length=100)
    unique_code = models.CharField(max_length=100, unique=True, verbose_name='Unieke code')
    api_key = models.CharField(max_length=255, unique=True, editable=False, verbose_name='API sleutel')
    location = models.ForeignKey(
        LockerLocation,
        on_delete=models.PROTECT,
        related_name='raspberry_pis',
        verbose_name='Locatie',
        help_text='Locatie waaraan deze Pi gekoppeld is',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OFFLINE)
    last_sync = models.DateTimeField(null=True, blank=True, verbose_name='Laatste synchronisatie')
    last_whitelist_ack_at = models.DateTimeField(null=True, blank=True, verbose_name='Laatste whitelist bevestiging')
    last_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='Laatst bekende IP')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['company', 'name']
        unique_together = ['company', 'name']
        verbose_name = 'Raspberry Pi'
        verbose_name_plural = 'Raspberry Pi\'s'

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    def save(self, *args, **kwargs):
        if not self.api_key:
            import secrets
            self.api_key = f"pi_{self.company.id}_{secrets.token_urlsafe(32)}"
        super().save(*args, **kwargs)


class AccessEvent(models.Model):
    """Toegangsgebeurtenis gelogd door een Raspberry Pi."""

    class CredentialType(models.TextChoices):
        NFC = 'nfc', 'NFC-tag'
        PIN = 'pin', 'PIN-code'
        CASH = 'cash', ''
        SYSTEM = 'system', 'Systeem'

    class EventStatus(models.TextChoices):
        SUCCESS = 'success', 'Succesvol'
        FAILED = 'failed', 'Mislukt'
        ERROR = 'error', 'Fout'

    class LockerState(models.TextChoices):
        FREE = 'free', 'Vrij'
        OCCUPIED_PIN = 'occupied_pin', 'Bezet via PIN'
        OCCUPIED_NFC = 'occupied_nfc', 'Bezet via NFC'
        OPENED_AND_RELEASED = 'opened_and_released', 'Geopend en vrijgegeven'
        CONFLICT = 'conflict', 'Conflict'
        UNKNOWN = 'unknown', 'Onbekend'

    raspberry_pi = models.ForeignKey(
        RaspberryPi,
        on_delete=models.CASCADE,
        related_name='access_events'
    )
    locker = models.ForeignKey(
        Locker,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='access_events'
    )
    locker_number = models.IntegerField(verbose_name='Locker-nummer')
    credential_type = models.CharField(max_length=20, choices=CredentialType.choices)
    credential_value = models.CharField(max_length=255, blank=True, verbose_name='Credential')
    locker_state = models.CharField(
        max_length=32,
        choices=LockerState.choices,
        default=LockerState.UNKNOWN,
        verbose_name='Lockerstatus (Pi)'
    )
    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.FAILED)
    message = models.TextField(blank=True, verbose_name='Bericht/Fout')
    synced_at = models.DateTimeField(null=True, blank=True, verbose_name='Gesynchroniseerd op')
    pi_timestamp = models.DateTimeField(verbose_name='Timestamp Pi')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pi_timestamp']
        verbose_name = 'Toegangsgebeurtenis'
        verbose_name_plural = 'Toegangsgebeurtenissen'
        indexes = [
            models.Index(fields=['raspberry_pi', '-pi_timestamp']),
            models.Index(fields=['locker', '-pi_timestamp']),
            models.Index(fields=['locker_state', '-pi_timestamp']),
            models.Index(fields=['synced_at']),
        ]

    def __str__(self):
        return f"{self.get_status_display()} - {self.raspberry_pi.name} - Locker {self.locker_number}"
