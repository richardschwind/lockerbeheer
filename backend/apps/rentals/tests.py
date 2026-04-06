from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.devices.models import AccessEvent, RaspberryPi
from apps.lockers.models import Locker, LockerLocation
from apps.rentals.models import Rental
from apps.rentals.serializers import RentalSerializer
from apps.users.models import Company, LockerUser, User


class RentalValidationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ACME')
        self.website_user = User.objects.create_user(
            username='locker-user',
            email='locker-user@example.com',
            password='secret123',
            company=self.company,
            role=User.Role.COMPANY_USER,
        )
        self.location = LockerLocation.objects.create(name='HQ', company=self.company)
        self.locker = Locker.objects.create(
            number='1',
            location=self.location,
            status=Locker.Status.OCCUPIED_PIN,
        )
        self.locker_user = LockerUser.objects.create(
            website_user=self.website_user,
            first_name='Jan',
            last_name='Jansen',
            is_active=True,
        )
        self.pi = RaspberryPi.objects.create(
            company=self.company,
            name='Pi 01',
            unique_code='pi-01-rentals',
            location=self.location,
            is_active=True,
        )

    def test_cannot_create_active_rental_on_pin_occupied_locker(self):
        with self.assertRaises(ValidationError):
            Rental.objects.create(
                locker_user=self.locker_user,
                locker=self.locker,
                status=Rental.Status.ACTIVE,
                start_date='2026-04-02',
            )

    def test_cannot_reactivate_rental_when_pi_still_reports_occupied_pin(self):
        locker = Locker.objects.create(
            number='2',
            location=self.location,
            status=Locker.Status.AVAILABLE,
        )
        rental = Rental.objects.create(
            locker_user=self.locker_user,
            locker=locker,
            status=Rental.Status.ACTIVE,
            start_date='2026-04-02',
        )

        AccessEvent.objects.create(
            raspberry_pi=self.pi,
            locker=locker,
            locker_number=2,
            credential_type=AccessEvent.CredentialType.PIN,
            credential_value='1234',
            locker_state=AccessEvent.LockerState.OCCUPIED_PIN,
            status=AccessEvent.EventStatus.SUCCESS,
            message='PIN actief',
            synced_at='2026-04-02T12:00:00Z',
            pi_timestamp='2026-04-02T12:00:00Z',
        )

        rental.status = Rental.Status.ENDED
        rental.save()
        locker.refresh_from_db()
        self.assertEqual(locker.status, Locker.Status.OCCUPIED_PIN)

        rental.status = Rental.Status.CANCELLED
        rental.save()
        locker.refresh_from_db()
        self.assertEqual(locker.status, Locker.Status.OCCUPIED_PIN)

        rental.status = Rental.Status.ACTIVE
        with self.assertRaises(ValidationError):
            rental.save()

    def test_serializer_rejects_reactivate_when_pin_is_still_reported(self):
        locker = Locker.objects.create(
            number='3',
            location=self.location,
            status=Locker.Status.AVAILABLE,
        )
        rental = Rental.objects.create(
            locker_user=self.locker_user,
            locker=locker,
            status=Rental.Status.ACTIVE,
            start_date='2026-04-02',
        )

        AccessEvent.objects.create(
            raspberry_pi=self.pi,
            locker=locker,
            locker_number=3,
            credential_type=AccessEvent.CredentialType.PIN,
            credential_value='9876',
            locker_state=AccessEvent.LockerState.OCCUPIED_PIN,
            status=AccessEvent.EventStatus.SUCCESS,
            message='PIN actief',
            synced_at='2026-04-02T12:05:00Z',
            pi_timestamp='2026-04-02T12:05:00Z',
        )

        rental.status = Rental.Status.ENDED
        rental.save()

        serializer = RentalSerializer(
            instance=rental,
            data={'status': Rental.Status.ACTIVE},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
