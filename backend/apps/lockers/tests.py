from django.test import TestCase
from django.utils import timezone

from apps.devices.models import RaspberryPi
from apps.lockers.models import Locker, LockerLocation
from apps.lockers.serializers import LockerSerializer
from apps.users.models import Company


class LockerSerializerPiFieldsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ACME')
        self.location = LockerLocation.objects.create(name='HQ', company=self.company)
        self.locker = Locker.objects.create(number='1', location=self.location)

    def test_serializer_marks_missing_pi_as_unconfigured(self):
        serializer = LockerSerializer(instance=self.locker)

        self.assertEqual(serializer.data['connection_status'], 'unconfigured')
        self.assertEqual(serializer.data['connection_status_display'], 'Geen Pi gekoppeld')

    def test_serializer_exposes_location_pi_connection_status(self):
        RaspberryPi.objects.create(
            company=self.company,
            name='Pi 01',
            unique_code='pi-01-lockers',
            location=self.location,
            status=RaspberryPi.Status.ONLINE,
            is_active=True,
        )

        serializer = LockerSerializer(instance=self.locker)

        self.assertEqual(serializer.data['pi_name'], 'Pi 01')
        self.assertEqual(serializer.data['pi_status'], RaspberryPi.Status.ONLINE)
        self.assertEqual(serializer.data['connection_status'], 'connected')
        self.assertEqual(serializer.data['connection_status_display'], 'Verbonden')

    def test_serializer_marks_whitelist_as_pending_when_pi_has_not_synced_latest_change(self):
        RaspberryPi.objects.create(
            company=self.company,
            name='Pi 01',
            unique_code='pi-01-whitelist-pending',
            location=self.location,
            status=RaspberryPi.Status.ONLINE,
            is_active=True,
            last_whitelist_ack_at=timezone.now() - timezone.timedelta(minutes=10),
        )
        self.locker.whitelist_changed_at = timezone.now()
        self.locker.save(update_fields=['whitelist_changed_at'])

        serializer = LockerSerializer(instance=self.locker)

        self.assertEqual(serializer.data['whitelist_status'], 'pending')
        self.assertEqual(serializer.data['whitelist_status_display'], 'Nieuwe whitelist gereed')

    def test_serializer_marks_whitelist_as_synced_when_pi_sync_is_newer(self):
        RaspberryPi.objects.create(
            company=self.company,
            name='Pi 01',
            unique_code='pi-01-whitelist-synced',
            location=self.location,
            status=RaspberryPi.Status.ONLINE,
            is_active=True,
            last_whitelist_ack_at=timezone.now(),
        )
        self.locker.whitelist_changed_at = timezone.now() - timezone.timedelta(minutes=5)
        self.locker.save(update_fields=['whitelist_changed_at'])

        serializer = LockerSerializer(instance=self.locker)

        self.assertEqual(serializer.data['whitelist_status'], 'synced')
        self.assertEqual(serializer.data['whitelist_status_display'], 'Whitelist gesynchroniseerd')