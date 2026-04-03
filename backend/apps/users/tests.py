from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.lockers.models import Locker, LockerLocation
from apps.rentals.models import Rental
from apps.users.models import Company, LockerUser, NFCTag, User


class LockerAccessMethodValidationTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ACME')
        self.admin_user = User.objects.create_user(
            username='company-admin',
            email='admin@example.com',
            password='secret123',
            company=self.company,
            role=User.Role.COMPANY_ADMIN,
        )

        self.website_user = User.objects.create_user(
            username='employee-user',
            email='employee@example.com',
            password='secret123',
            company=self.company,
            role=User.Role.COMPANY_USER,
        )

        self.location = LockerLocation.objects.create(name='HQ', company=self.company)
        self.locker = Locker.objects.create(
            number='3',
            location=self.location,
            status=Locker.Status.AVAILABLE,
        )

        self.locker_user = LockerUser.objects.create(
            website_user=self.website_user,
            first_name='Jan',
            last_name='Jansen',
            email='jan@example.com',
            is_active=True,
        )

        self.client.force_authenticate(user=self.admin_user)

    def test_nfc_tag_create_is_blocked_when_locker_is_pin_occupied(self):
        rental = Rental.objects.create(
            locker_user=self.locker_user,
            locker=self.locker,
            status=Rental.Status.ACTIVE,
            start_date='2026-04-01',
        )

        response = self.client.post(
            '/api/users/nfc-tags/',
            data={
                'uid': '04PINBLOCK001',
                'locker_user': self.locker_user.id,
                'status': NFCTag.Status.ACTIVE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('message', response.data)
        self.assertIn('bezet via PIN', str(response.data['message']))

    def test_nfc_tag_model_save_is_blocked_when_locker_is_pin_occupied(self):
        rental = Rental.objects.create(
            locker_user=self.locker_user,
            locker=self.locker,
            status=Rental.Status.ACTIVE,
            start_date='2026-04-01',
        )

        with self.assertRaises(ValidationError):
            NFCTag.objects.create(
                uid='04PINBLOCK002',
                locker_user=self.locker_user,
                status=NFCTag.Status.ACTIVE,
            )

    def test_locker_pin_status_update_is_blocked_when_locker_is_nfc_occupied(self):
        NFCTag.objects.create(
            uid='04NFCACTIVE001',
            locker_user=self.locker_user,
            status=NFCTag.Status.ACTIVE,
        )

        rental = Rental.objects.create(
            locker_user=self.locker_user,
            locker=self.locker,
            status=Rental.Status.ACTIVE,
            start_date='2026-04-01',
        )

        response = self.client.patch(
            f'/api/lockers/{self.locker.id}/',
            data={'status': Locker.Status.OCCUPIED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('message', response.data)
        self.assertIn('bezet via NFC', str(response.data['message']))
