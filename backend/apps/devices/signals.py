import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.devices.pi_signal import broadcast_whitelist_changed
from apps.lockers.models import Locker
from apps.rentals.models import Rental
from apps.users.models import NFCTag

logger = logging.getLogger(__name__)


@receiver(post_save, sender=NFCTag)
def nfc_tag_saved(sender, instance, **kwargs):
    company = getattr(getattr(instance, 'locker_user', None), 'company', None)
    if not company:
        logger.debug('Skip whitelist_changed: NFCTag has no company (tag_id=%s)', instance.id)
        return

    logger.info('Whitelist change detected from NFCTag save (tag_id=%s, company_id=%s)', instance.id, company.id)
    broadcast_whitelist_changed(company.id)


@receiver(post_delete, sender=NFCTag)
def nfc_tag_deleted(sender, instance, **kwargs):
    company = getattr(getattr(instance, 'locker_user', None), 'company', None)
    if not company:
        logger.debug('Skip whitelist_changed: deleted NFCTag had no company (tag_id=%s)', instance.id)
        return

    logger.info('Whitelist change detected from NFCTag delete (tag_id=%s, company_id=%s)', instance.id, company.id)
    broadcast_whitelist_changed(company.id)


@receiver(post_save, sender=Rental)
def rental_saved(sender, instance, **kwargs):
    company = getattr(getattr(instance, 'locker_user', None), 'company', None)
    if not company:
        logger.debug('Skip whitelist_changed: Rental has no company (rental_id=%s)', instance.id)
        return

    logger.info('Whitelist change detected from Rental save (rental_id=%s, company_id=%s)', instance.id, company.id)
    broadcast_whitelist_changed(company.id)


@receiver(post_delete, sender=Rental)
def rental_deleted(sender, instance, **kwargs):
    company = getattr(getattr(instance, 'locker_user', None), 'company', None)
    if not company:
        logger.debug('Skip whitelist_changed: deleted Rental had no company (rental_id=%s)', instance.id)
        return

    logger.info('Whitelist change detected from Rental delete (rental_id=%s, company_id=%s)', instance.id, company.id)
    broadcast_whitelist_changed(company.id)


@receiver(post_save, sender=Locker)
def locker_saved(sender, instance, **kwargs):
    company_id = getattr(getattr(instance, 'location', None), 'company_id', None)
    if not company_id:
        logger.debug('Skip whitelist_changed: Locker has no company (locker_id=%s)', instance.id)
        return

    logger.info('Whitelist change detected from Locker save (locker_id=%s, company_id=%s)', instance.id, company_id)
    broadcast_whitelist_changed(company_id)


@receiver(post_delete, sender=Locker)
def locker_deleted(sender, instance, **kwargs):
    company_id = getattr(getattr(instance, 'location', None), 'company_id', None)
    if not company_id:
        logger.debug('Skip whitelist_changed: deleted Locker had no company (locker_id=%s)', instance.id)
        return

    logger.info('Whitelist change detected from Locker delete (locker_id=%s, company_id=%s)', instance.id, company_id)
    broadcast_whitelist_changed(company_id)
