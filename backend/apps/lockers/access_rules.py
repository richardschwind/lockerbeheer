from django.core.exceptions import ValidationError


def get_latest_reported_locker_state(locker):
    """Return the latest locker_state reported by a Pi for this locker, if any."""
    from apps.devices.models import AccessEvent

    return (
        AccessEvent.objects.filter(
            locker=locker,
            locker_state__in=[
                AccessEvent.LockerState.FREE,
                AccessEvent.LockerState.OCCUPIED_PIN,
                AccessEvent.LockerState.OCCUPIED_NFC,
                AccessEvent.LockerState.OPENED_AND_RELEASED,
            ],
        )
        .order_by('-pi_timestamp', '-id')
        .values_list('locker_state', flat=True)
        .first()
    )


def locker_has_active_nfc(locker, exclude_tag_id=None, exclude_rental_id=None):
    """Return True when locker is currently occupied via active NFC whitelist mapping."""
    from apps.rentals.models import Rental
    from apps.users.models import NFCTag

    active_rentals = Rental.objects.filter(
        locker=locker,
        status=Rental.Status.ACTIVE,
        locker_user__is_active=True,
    )
    if exclude_rental_id:
        active_rentals = active_rentals.exclude(pk=exclude_rental_id)

    locker_user_ids = list(active_rentals.values_list('locker_user_id', flat=True))
    if not locker_user_ids:
        return False

    active_tags = NFCTag.objects.filter(
        locker_user_id__in=locker_user_ids,
        status=NFCTag.Status.ACTIVE,
    )
    if exclude_tag_id:
        active_tags = active_tags.exclude(pk=exclude_tag_id)

    return active_tags.exists()


def get_locker_access_state(locker, exclude_tag_id=None, exclude_rental_id=None):
    """
    Derive active access state for a locker.

    State priority:
    1) nfc: active rental + active NFC tag mapping
    2) pin: locker status occupied and not nfc
    3) free
    """
    from apps.lockers.models import Locker

    if locker_has_active_nfc(locker, exclude_tag_id=exclude_tag_id, exclude_rental_id=exclude_rental_id):
        return 'nfc'

    latest_reported_state = get_latest_reported_locker_state(locker)
    if latest_reported_state == 'occupied_nfc':
        return 'nfc'

    if latest_reported_state == 'occupied_pin':
        return 'pin'

    if latest_reported_state in {'free', 'opened_and_released'}:
        return 'free'

    if locker.status == Locker.Status.OCCUPIED_NFC:
        return 'nfc'

    if locker.status in {Locker.Status.OCCUPIED, Locker.Status.OCCUPIED_PIN}:
        return 'pin'

    return 'free'


def ensure_can_assign_nfc(locker, exclude_tag_id=None, exclude_rental_id=None):
    state = get_locker_access_state(
        locker,
        exclude_tag_id=exclude_tag_id,
        exclude_rental_id=exclude_rental_id,
    )
    if state == 'pin':
        raise ValidationError(
            f"Locker {locker.number} is al bezet via PIN en kan niet ook aan een NFC-tag gekoppeld worden."
        )


def ensure_can_assign_pin(locker, exclude_tag_id=None, exclude_rental_id=None):
    state = get_locker_access_state(
        locker,
        exclude_tag_id=exclude_tag_id,
        exclude_rental_id=exclude_rental_id,
    )
    if state == 'nfc':
        raise ValidationError(f"Locker {locker.number} is al bezet via NFC en kan niet op PIN-status gezet worden.")
