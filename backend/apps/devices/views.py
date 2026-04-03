import logging

from rest_framework import viewsets, permissions, status, filters
from rest_framework.authentication import BaseAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import RaspberryPi, AccessEvent
from .serializers import RaspberryPiSerializer, AccessEventSerializer, PiSyncRequestSerializer, PiSyncEventSerializer


logger = logging.getLogger(__name__)


class PiBearerTokenAuthentication(BaseAuthentication):
    """Custom auth voor Pi API key."""

    @staticmethod
    def _mask_key(raw_key):
        if not raw_key:
            return '<missing>'
        if len(raw_key) <= 8:
            return '<redacted>'
        return f"{raw_key[:4]}...{raw_key[-4:]}"

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_X_PI_KEY', '')
        if not auth_header:
            logger.warning(
                'Pi auth failed: missing X-PI-KEY (path=%s, ip=%s)',
                request.path,
                request.META.get('REMOTE_ADDR'),
            )
            return None

        try:
            pi = RaspberryPi.objects.get(api_key=auth_header, is_active=True)
            return (None, pi)
        except RaspberryPi.DoesNotExist:
            logger.warning(
                'Pi auth failed: invalid/inactive X-PI-KEY=%s (path=%s, ip=%s)',
                self._mask_key(auth_header),
                request.path,
                request.META.get('REMOTE_ADDR'),
            )
            raise AuthenticationFailed('Ongeldige Pi API sleutel.')

    def authenticate_header(self, request):
        return 'X-PI-KEY'


class IsSuperAdminOrPi(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if getattr(user, 'is_authenticated', False) and (
            getattr(user, 'is_superuser', False) or getattr(user, 'role', None) == 'superadmin'
        ):
            return True
        if isinstance(getattr(request, 'auth', None), RaspberryPi):
            return True
        return False


class RaspberryPiViewSet(viewsets.ModelViewSet):
    serializer_class = RaspberryPiSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'unique_code', 'location__name']
    ordering_fields = ['name', 'last_sync', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = RaspberryPi.objects.select_related('company', 'location').all()
        if user.is_superuser or user.role == 'superadmin':
            return qs
        return qs.filter(company=user.company)

    def perform_create(self, serializer):
        serializer.save()


class AccessEventViewSet(viewsets.ModelViewSet):
    serializer_class = AccessEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['raspberry_pi__name', 'locker__number', 'credential_value', 'locker_state']
    ordering_fields = ['pi_timestamp', 'created_at', 'status', 'locker_state']
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs = AccessEvent.objects.select_related('raspberry_pi', 'locker').all()
        locker_state = self.request.query_params.get('locker_state')

        if locker_state:
            valid_states = {choice[0] for choice in AccessEvent.LockerState.choices}
            if locker_state in valid_states:
                qs = qs.filter(locker_state=locker_state)

        if user.is_superuser or user.role == 'superadmin':
            return qs
        return qs.filter(raspberry_pi__company=user.company)


class PiSyncView(viewsets.ViewSet):
    """Pi sync endpoint - batched event upload en credential updates."""

    permission_classes = []
    authentication_classes = [PiBearerTokenAuthentication]

    def get_permissions(self):
        return [IsSuperAdminOrPi()]

    @action(detail=False, methods=['post'], url_path='sync')
    def sync(self, request):
        """
        Pi upload batch van access events.

        Expected body:
        {
            "events": [
                {
                    "locker_number": 1,
                    "credential_type": "nfc",
                    "credential_value": "AABBCCDD",
                    "success": true/false,
                    "message": "...",
                    "timestamp": "2026-03-30T14:30:00Z",
                    "locker_state": "free|occupied_pin|occupied_nfc|opened_and_released|conflict|unknown"
                },
                ...
            ]
        }
        """
        pi = None
        if hasattr(request, 'auth') and isinstance(request.auth, RaspberryPi):
            pi = request.auth
        else:
            return Response(
                {'error': 'Pi authenticatie vereist. Stuur X-PI-KEY header.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = PiSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        events_data = serializer.validated_data['events']
        synced_count = 0
        errors = []
        failed_indices = []
        created_events = []

        for idx, raw_event_data in enumerate(events_data):
            try:
                event_serializer = PiSyncEventSerializer(data=raw_event_data)
                if not event_serializer.is_valid():
                    first_error = next(iter(event_serializer.errors.values()))
                    if isinstance(first_error, list) and first_error:
                        first_error = first_error[0]
                    errors.append(str(first_error))
                    failed_indices.append(idx)
                    continue

                event_data = event_serializer.validated_data

                locker_number = event_data.get('locker_number')
                if locker_number is None:
                    errors.append('locker_number is verplicht')
                    failed_indices.append(idx)
                    continue

                locker = None
                if locker_number != 0:
                    from apps.lockers.models import Locker

                    locker = Locker.objects.filter(
                        location__company=pi.company,
                        number=str(locker_number)
                    ).first()

                event_status = AccessEvent.EventStatus.SUCCESS if event_data['success'] else AccessEvent.EventStatus.FAILED

                created_event = AccessEvent.objects.create(
                    raspberry_pi=pi,
                    locker=locker,
                    locker_number=locker_number,
                    credential_type=event_data['credential_type'],
                    credential_value=event_data.get('credential_value', ''),
                    locker_state=event_data.get('locker_state', AccessEvent.LockerState.UNKNOWN),
                    status=event_status,
                    message=event_data.get('message', ''),
                    synced_at=timezone.now(),
                    pi_timestamp=event_data['timestamp']
                )
                self._apply_locker_status_from_event(locker, event_data)
                created_events.append(created_event)
                synced_count += 1

            except Exception as e:
                errors.append(f'Event-fout: {str(e)}')
                failed_indices.append(idx)

        self._mark_pi_seen(pi, request)

        if synced_count > 0:
            pi.status = RaspberryPi.Status.ONLINE
        else:
            if pi.last_sync and (timezone.now() - pi.last_sync).total_seconds() > 600:
                pi.status = RaspberryPi.Status.OFFLINE
        pi.save(update_fields=['status'])

        if created_events:
            self._broadcast_events(pi, created_events)

        failed_count = len(errors)
        response_data = {
            'success': synced_count > 0 or failed_count == 0,
            'synced_count': synced_count,
            'failed_count': failed_count,
            'message': f'{synced_count} events gesynchroniseerd.' + (f' Fouten: {failed_count}' if failed_count else ''),
            'errors': errors if errors else None,
        }

        if failed_indices:
            response_data['failed_indices'] = failed_indices

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='whitelist')
    def whitelist(self, request):
        pi = None
        if hasattr(request, 'auth') and isinstance(request.auth, RaspberryPi):
            pi = request.auth
        else:
            return Response(
                {'error': 'Pi authenticatie vereist. Stuur X-PI-KEY header.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        from apps.rentals.models import Rental
        from apps.users.models import NFCTag

        active_rentals = Rental.objects.filter(
            status=Rental.Status.ACTIVE,
            locker__location__company=pi.company,
            locker_user__is_active=True,
        ).select_related('locker', 'locker_user')

        locker_user_ids = [rental.locker_user_id for rental in active_rentals]
        active_tags = NFCTag.objects.filter(
            locker_user_id__in=locker_user_ids,
            status=NFCTag.Status.ACTIVE,
        ).values_list('locker_user_id', 'uid')

        tags_per_user = {}
        for locker_user_id, uid in active_tags:
            tags_per_user.setdefault(locker_user_id, []).append(uid)

        records = []
        for rental in active_rentals:
            nfc_codes = tags_per_user.get(rental.locker_user_id, [])
            locker = rental.locker
            for nfc_code in nfc_codes:
                try:
                    locker_number = int(locker.number)
                except (TypeError, ValueError):
                    continue

                records.append({
                    'locker_number': locker_number,
                    'nfc_code': nfc_code,
                    'is_active': True,
                })

        # Dedupe in case of duplicate rental/tag combinations.
        unique_records = []
        seen = set()
        for record in records:
            key = (record['locker_number'], record['nfc_code'])
            if key in seen:
                continue
            seen.add(key)
            unique_records.append(record)

        self._mark_pi_seen(pi, request)

        return Response({
            'success': True,
            'count': len(unique_records),
            'records': unique_records,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='lockers')
    def lockers(self, request):
        pi = None
        if hasattr(request, 'auth') and isinstance(request.auth, RaspberryPi):
            pi = request.auth
        else:
            return Response(
                {'error': 'Pi authenticatie vereist. Stuur X-PI-KEY header.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        from apps.lockers.models import Locker

        lockers_qs = Locker.objects.filter(
            location__company=pi.company,
        ).order_by('number')

        records = []
        for locker in lockers_qs:
            try:
                locker_number = int(locker.number)
            except (TypeError, ValueError):
                continue

            records.append({
                'locker_number': locker_number,
                'is_active': locker.status != Locker.Status.MAINTENANCE,
                'status': locker.status,
            })

        self._mark_pi_seen(pi, request)

        return Response({
            'success': True,
            'count': len(records),
            'records': records,
        }, status=status.HTTP_200_OK)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _mark_pi_seen(self, pi, request):
        pi.last_sync = timezone.now()
        pi.last_ip = self._get_client_ip(request)
        pi.save(update_fields=['last_sync', 'last_ip'])

    def _apply_locker_status_from_event(self, locker, event_data):
        if not locker:
            return

        locker_state = event_data.get('locker_state', AccessEvent.LockerState.UNKNOWN)

        if locker_state == AccessEvent.LockerState.OCCUPIED_PIN:
            self._set_locker_status(locker, 'occupied_pin')
            return

        if locker_state == AccessEvent.LockerState.OCCUPIED_NFC:
            self._set_locker_status(locker, 'occupied_nfc')
            return

        if locker_state in {AccessEvent.LockerState.FREE, AccessEvent.LockerState.OPENED_AND_RELEASED}:
            self._set_locker_status(locker, 'available')
            return

    def _set_locker_status(self, locker, target):
        from apps.lockers.models import Locker

        if locker.status == Locker.Status.MAINTENANCE:
            return

        if target == 'occupied_pin':
            new_status = Locker.Status.OCCUPIED_PIN
        elif target == 'occupied_nfc':
            new_status = Locker.Status.OCCUPIED_NFC
        else:
            new_status = Locker.Status.AVAILABLE

        if locker.status == new_status:
            return

        locker.status = new_status
        locker.save(update_fields=['status'])

    def _broadcast_events(self, pi, events):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        payload = AccessEventSerializer(events, many=True).data
        message = {
            'type': 'access.events.batch',
            'events': payload,
            'count': len(payload),
        }

        if pi.company_id:
            async_to_sync(channel_layer.group_send)(
                f'access_events_company_{pi.company_id}',
                message,
            )

        async_to_sync(channel_layer.group_send)('access_events_global', message)
