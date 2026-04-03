from django.db import models
from apps.users.models import Company


class LockerLocation(models.Model):
    """Locatie/gebouw waar lockers staan."""
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='locker_locations',
    )
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['company', 'name']
        unique_together = ['company', 'name']
        verbose_name = 'Locatie'
        verbose_name_plural = 'Locaties'

    def __str__(self): 
        return f"{self.name} ({self.company.name})"


class Locker(models.Model):
    """Een individuele locker."""

    class Size(models.TextChoices):
        SMALL = 'S', 'Klein'
        MEDIUM = 'M', 'Medium'
        LARGE = 'L', 'Groot'
        EXTRA_LARGE = 'XL', 'Extra Groot'

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Beschikbaar'
        OCCUPIED = 'occupied', 'Bezet (algemeen)'
        OCCUPIED_PIN = 'occupied_pin', 'Bezet via PIN'
        OCCUPIED_NFC = 'occupied_nfc', 'Bezet via NFC'
        MAINTENANCE = 'maintenance', 'Onderhoud'
        RESERVED = 'reserved', 'Gereserveerd'

    number = models.CharField(max_length=20)
    location = models.ForeignKey(LockerLocation, on_delete=models.CASCADE, related_name='lockers')
    size = models.CharField(max_length=2, choices=Size.choices, default=Size.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    floor = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['location', 'number']
        unique_together = ['location', 'number']
        verbose_name = 'Locker'
        verbose_name_plural = 'Lockers'

    def __str__(self):
        return f"Locker {self.number} – {self.location.name}"
