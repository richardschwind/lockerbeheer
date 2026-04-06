from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from apps.devices.models import AccessEvent, RaspberryPi
from apps.lockers.models import Locker, LockerLocation
from apps.rentals.models import Rental
from apps.users.models import Company, LockerUser, NFCTag, User


class PiSyncApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ACME')
        self.website_user = User.objects.create_user(
            username='company-user',
            email='company@example.com',
            password='secret123',
            company=self.company,
            role=User.Role.COMPANY_USER,
        )

        self.location = LockerLocation.objects.create(name='HQ', company=self.company)
        self.locker = Locker.objects.create(
            number='1',
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

        NFCTag.objects.create(
            uid='04A1B2C301',
            locker_user=self.locker_user,
            status=NFCTag.Status.ACTIVE,
        )

        rental = Rental.objects.create(
            locker_user=self.locker_user,
            locker=self.locker,
            status=Rental.Status.ACTIVE,
            start_date='2026-03-31',
        )

        self.pi = RaspberryPi.objects.create(
            company=self.company,
            name='Pi 01',
            unique_code='pi-01',
            location=self.location,
            is_active=True,
        )

    def test_sync_accepts_locker_number_zero(self):
        response = self.client.post(
            '/api/devices/pi-sync/sync/',
            data={
                'events': [
                    {
                        'locker_number': 0,
                        'credential_type': 'nfc',
                        'credential_value': 'AABBCCDD',
                        'success': False,
                        'message': 'Onbekende kaart',
                        'timestamp': '2026-03-30T14:30:00Z',
                        'locker_state': 'unknown',
                    }
                ]
            },
            format='json',
            HTTP_X_PI_KEY=self.pi.api_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['synced_count'], 1)

        event = AccessEvent.objects.get()
        self.assertEqual(event.locker_number, 0)
        self.assertIsNone(event.locker)
        self.assertEqual(event.locker_state, AccessEvent.LockerState.UNKNOWN)

    def test_sync_returns_partial_success_with_failed_indices(self):
        response = self.client.post(
            '/api/devices/pi-sync/sync/',
            data={
                'events': [
                    {
                        'locker_number': 1,
                        'credential_type': 'pin',
                        'credential_value': '',
                        'success': True,
                        'message': 'OK',
                        'timestamp': '2026-03-30T14:31:00Z',
                        'locker_state': 'occupied_pin',
                    },
                    {
                        'credential_type': 'nfc',
                        'credential_value': 'MISSING_LOCKER',
                        'success': False,
                        'message': 'Onbekend',
                        'timestamp': '2026-03-30T14:32:00Z',
                        'locker_state': 'unknown',
                    },
                ]
            },
            format='json',
            HTTP_X_PI_KEY=self.pi.api_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['synced_count'], 1)
        self.assertEqual(response.data['failed_count'], 1)
        self.assertEqual(response.data['failed_indices'], [1])
        self.assertEqual(AccessEvent.objects.count(), 1)

        self.locker.refresh_from_db()
        self.assertEqual(self.locker.status, Locker.Status.OCCUPIED_PIN)

    def test_sync_marks_locker_occupied_when_pi_reports_occupied(self):
        locker = Locker.objects.create(
            number='9',
            location=self.location,
            status=Locker.Status.AVAILABLE,
        )

        response = self.client.post(
            '/api/devices/pi-sync/sync/',
            data={
                'events': [
                    {
                        'locker_number': 9,
                        'credential_type': 'system',
                        'credential_value': '',
                        'success': True,
                        'message': 'status update',
                        'timestamp': '2026-03-30T14:31:00Z',
                        'locker_state': 'occupied_nfc',
                    },
                ]
            },
            format='json',
            HTTP_X_PI_KEY=self.pi.api_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        locker.refresh_from_db()
        self.assertEqual(locker.status, Locker.Status.OCCUPIED_NFC)

    def test_sync_marks_locker_available_when_pi_reports_release(self):
        self.locker.status = Locker.Status.OCCUPIED
        self.locker.save(update_fields=['status'])

        response = self.client.post(
            '/api/devices/pi-sync/sync/',
            data={
                'events': [
                    {
                        'locker_number': 1,
                        'credential_type': 'system',
                        'credential_value': '',
                        'success': True,
                        'message': 'status update',
                        'timestamp': '2026-03-30T14:33:00Z',
                        'locker_state': 'opened_and_released',
                    },
                ]
            },
            format='json',
            HTTP_X_PI_KEY=self.pi.api_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.locker.refresh_from_db()
        self.assertEqual(self.locker.status, Locker.Status.AVAILABLE)

    def test_sync_conflict_state_does_not_override_locker_status(self):
        self.locker.status = Locker.Status.OCCUPIED
        self.locker.save(update_fields=['status'])

        response = self.client.post(
            '/api/devices/pi-sync/sync/',
            data={
                'events': [
                    {
                        'locker_number': 1,
                        'credential_type': 'system',
                        'credential_value': '',
                        'success': False,
                        'message': 'Whitelist conflict',
                        'timestamp': '2026-03-30T14:34:00Z',
                        'locker_state': 'conflict',
                    },
                ]
            },
            format='json',
            HTTP_X_PI_KEY=self.pi.api_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.locker.refresh_from_db()
        self.assertEqual(self.locker.status, Locker.Status.OCCUPIED)

        event = AccessEvent.objects.latest('id')
        self.assertEqual(event.locker_state, AccessEvent.LockerState.CONFLICT)

    def test_whitelist_returns_company_filtered_records(self):
        other_company = Company.objects.create(name='OtherCo')
        other_user = User.objects.create_user(
            username='other-user',
            email='other@example.com',
            password='secret123',
            company=other_company,
            role=User.Role.COMPANY_USER,
        )
        other_location = LockerLocation.objects.create(name='Other HQ', company=other_company)
        other_locker = Locker.objects.create(
            number='2',
            location=other_location,
            status=Locker.Status.AVAILABLE,
        )
        other_locker_user = LockerUser.objects.create(
            website_user=other_user,
            first_name='Piet',
            last_name='Peters',
            is_active=True,
        )
        NFCTag.objects.create(
            uid='04D7A1BC92',
            locker_user=other_locker_user,
            status=NFCTag.Status.ACTIVE,
        )
        other_rental = Rental.objects.create(
            locker_user=other_locker_user,
            locker=other_locker,
            status=Rental.Status.ACTIVE,
            start_date='2026-03-31',
        )

        response = self.client.get(
            '/api/devices/pi-sync/whitelist/',
            HTTP_X_PI_KEY=self.pi.api_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['records'][0],
            {
                'locker_number': 1,
                'nfc_code': '04A1B2C301',
                'is_active': True,
            },
        )

    def test_lockers_returns_company_filtered_metadata(self):
        maintenance_locker = Locker.objects.create(
            number='3',
            location=self.location,
            status=Locker.Status.MAINTENANCE,
        )

        other_company = Company.objects.create(name='OtherCo')
        other_location = LockerLocation.objects.create(name='Other HQ', company=other_company)
        Locker.objects.create(
            number='99',
            location=other_location,
            status=Locker.Status.AVAILABLE,
        )

        response = self.client.get(
            '/api/devices/pi-sync/lockers/',
            HTTP_X_PI_KEY=self.pi.api_key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(
            response.data['records'],
            [
                {
                    'locker_number': 1,
                    'is_active': True,
                    'status': Locker.Status.AVAILABLE,
                },
                {
                    'locker_number': 3,
                    'is_active': False,
                    'status': Locker.Status.MAINTENANCE,
                },
            ],
        )


class AccessEventFilterTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ACME')
        self.superadmin = User.objects.create_user(
            username='superadmin',
            email='superadmin@example.com',
            password='secret123',
            role=User.Role.SUPERADMIN,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.superadmin)

        self.location = LockerLocation.objects.create(name='HQ', company=self.company)
        self.locker = Locker.objects.create(
            number='1',
            location=self.location,
            status=Locker.Status.AVAILABLE,
        )
        self.pi = RaspberryPi.objects.create(
            company=self.company,
            name='Pi 01',
            unique_code='pi-01-filter',
            location=self.location,
            is_active=True,
        )

    def test_access_events_support_locker_state_query_filter(self):
        AccessEvent.objects.create(
            raspberry_pi=self.pi,
            locker=self.locker,
            locker_number=1,
            credential_type=AccessEvent.CredentialType.SYSTEM,
            credential_value='',
            locker_state=AccessEvent.LockerState.CONFLICT,
            status=AccessEvent.EventStatus.FAILED,
            message='Conflict event',
            synced_at='2026-03-30T14:35:00Z',
            pi_timestamp='2026-03-30T14:35:00Z',
        )
        AccessEvent.objects.create(
            raspberry_pi=self.pi,
            locker=self.locker,
            locker_number=1,
            credential_type=AccessEvent.CredentialType.PIN,
            credential_value='1234',
            locker_state=AccessEvent.LockerState.OCCUPIED_PIN,
            status=AccessEvent.EventStatus.SUCCESS,
            message='Occupied event',
            synced_at='2026-03-30T14:36:00Z',
            pi_timestamp='2026-03-30T14:36:00Z',
        )

        response = self.client.get('/api/devices/access-events/?locker_state=conflict')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['locker_state'], AccessEvent.LockerState.CONFLICT)


class LockerSignalTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ACME')
        self.location = LockerLocation.objects.create(name='HQ', company=self.company)

    @patch('apps.devices.signals.broadcast_whitelist_changed')
    def test_locker_status_change_broadcasts_whitelist_changed(self, mock_broadcast):
        locker = Locker.objects.create(
            number='11',
            location=self.location,
            status=Locker.Status.AVAILABLE,
        )
        mock_broadcast.reset_mock()

        locker.status = Locker.Status.MAINTENANCE
        locker.save(update_fields=['status'])

        mock_broadcast.assert_called_once_with(self.company.id)

    @patch('apps.devices.signals.broadcast_whitelist_changed')
    def test_locker_delete_broadcasts_whitelist_changed(self, mock_broadcast):
        locker = Locker.objects.create(
            number='12',
            location=self.location,
            status=Locker.Status.AVAILABLE,
        )
        mock_broadcast.reset_mock()

        locker.delete()

        mock_broadcast.assert_called_once_with(self.company.id)


class WhitelistBroadcastTests(APITestCase):
    @patch('apps.devices.pi_signal.async_to_sync')
    @patch('apps.devices.pi_signal.get_channel_layer')
    def test_company_broadcast_failure_is_non_fatal(self, mock_get_channel_layer, mock_async_to_sync):
        mock_get_channel_layer.return_value = object()
        mock_async_to_sync.return_value.side_effect = RuntimeError('redis down')

        from apps.devices.pi_signal import broadcast_whitelist_changed

        result = broadcast_whitelist_changed(company_id=1)

        self.assertFalse(result)

    @patch('apps.devices.pi_signal.async_to_sync')
    @patch('apps.devices.pi_signal.get_channel_layer')
    def test_targeted_broadcast_failure_is_non_fatal(self, mock_get_channel_layer, mock_async_to_sync):
        company = Company.objects.create(name='ACME')
        location = LockerLocation.objects.create(name='HQ', company=company)
        RaspberryPi.objects.create(
            company=company,
            name='Pi 01',
            unique_code='pi-01',
            location=location,
            is_active=True,
        )
        mock_get_channel_layer.return_value = object()
        mock_async_to_sync.return_value.side_effect = RuntimeError('redis down')

        from apps.devices.pi_signal import broadcast_whitelist_changed

        result = broadcast_whitelist_changed(company_id=company.id, pi_unique_code='pi-01')

        self.assertFalse(result)

    @patch('apps.devices.pi_signal.async_to_sync')
    @patch('apps.devices.pi_signal.get_channel_layer')
    def test_lockers_refresh_broadcast_failure_is_non_fatal(self, mock_get_channel_layer, mock_async_to_sync):
        mock_get_channel_layer.return_value = object()
        mock_async_to_sync.return_value.side_effect = RuntimeError('redis down')

        from apps.devices.pi_signal import broadcast_lockers_refresh

        result = broadcast_lockers_refresh(company_id=1)

        self.assertFalse(result)
