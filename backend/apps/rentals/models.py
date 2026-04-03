from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from apps.lockers.models import Locker
from apps.users.models import LockerUser


class Rental(models.Model):
    """Huurovereenkomst tussen een lockergebruiker en een locker. waarvan alles giesd is """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Actief'
        ENDED = 'ended', 'Beëindigd'
        CANCELLED = 'cancelled', 'Geannuleerd'

    locker_user = models.ForeignKey(
        LockerUser,
        on_delete=models.PROTECT,
        related_name='rentals',
        verbose_name='Lockergebruiker'
    )
    locker = models.ForeignKey(
        Locker,
        on_delete=models.PROTECT,
        related_name='rentals',
        verbose_name='Locker'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_rentals',
        verbose_name='Aangemaakt door'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Huurovereenkomst'
        verbose_name_plural = 'Huurovereenkomsten'

    def __str__(self):
        return f"{self.locker_user} → {self.locker} ({self.get_status_display()})"

    def clean(self):
        super().clean()

        if self.status != self.Status.ACTIVE or not self.locker_id or not self.locker_user_id:
            return

        from apps.lockers.access_rules import get_locker_access_state, get_latest_reported_locker_state

        is_same_active_rental = bool(self.pk) and Rental.objects.filter(
            pk=self.pk,
            locker_id=self.locker_id,
            status=self.Status.ACTIVE,
        ).exists()

        current_access_state = get_locker_access_state(self.locker, exclude_rental_id=self.pk)
        if current_access_state == 'pin' and not is_same_active_rental:
            raise ValidationError(f'Locker {self.locker.number} is al bezet via PIN.')

        from apps.lockers.access_rules import ensure_can_assign_pin
        from apps.users.models import NFCTag

        has_active_tag = NFCTag.objects.filter(
            locker_user_id=self.locker_user_id,
            status=NFCTag.Status.ACTIVE,
        ).exists()

        if has_active_tag:
            return

        try:
            ensure_can_assign_pin(self.locker, exclude_rental_id=self.pk)
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
            raise ValidationError(message)

    def save(self, *args, **kwargs):
        self.full_clean()
        from apps.lockers.access_rules import get_latest_reported_locker_state
        from apps.users.models import NFCTag

        # Locker status automatisch bijwerken
        if self.status == self.Status.ACTIVE:
            has_active_tag = NFCTag.objects.filter(
                locker_user_id=self.locker_user_id,
                status=NFCTag.Status.ACTIVE,
            ).exists()
            self.locker.status = Locker.Status.OCCUPIED_NFC if has_active_tag else Locker.Status.OCCUPIED_PIN
        elif self.status in [self.Status.ENDED, self.Status.CANCELLED]:
            latest_reported_state = get_latest_reported_locker_state(self.locker)
            if latest_reported_state == 'occupied_pin':
                self.locker.status = Locker.Status.OCCUPIED_PIN
            elif latest_reported_state == 'occupied_nfc':
                self.locker.status = Locker.Status.OCCUPIED_NFC
            else:
                self.locker.status = Locker.Status.AVAILABLE
        self.locker.save()
        super().save(*args, **kwargs)
