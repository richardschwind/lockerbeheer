import logging
from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.devices.models import RaspberryPi

logger = logging.getLogger(__name__)


def broadcast_whitelist_changed(company_id, pi_unique_code=None):
    """
    Stuur whitelist_changed events naar:
    - specifieke Pi (via eigen group)
    - of alle Pi's van een company
    """

    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("No channel layer available")
        return False

    message = {
        'type': 'whitelist_changed',
        'pi_unique_code': pi_unique_code,
        'timestamp': datetime.utcnow().isoformat(),
    }

    # 🎯 1. Targeted Pi → stuur naar eigen group
    if pi_unique_code:
        try:
            pi = RaspberryPi.objects.get(unique_code=pi_unique_code)
            async_to_sync(channel_layer.group_send)(
                f'pi_sync_pi_{pi.id}',
                message,
            )
            logger.info("Sent whitelist_changed to specific Pi %s", pi_unique_code)
            return True
        except RaspberryPi.DoesNotExist:
            logger.warning("No Pi found with unique_code=%s", pi_unique_code)
            return False
        except Exception:
            logger.exception(
                "Failed to send whitelist_changed to specific Pi %s",
                pi_unique_code,
            )
            return False

    # 🎯 2. Broadcast → stuur naar alle Pi's van de company
    try:
        async_to_sync(channel_layer.group_send)(
            f'pi_sync_{company_id}',
            message,
        )
        logger.info("Broadcast whitelist_changed to company %s", company_id)
        return True
    except Exception:
        logger.exception("Failed to broadcast whitelist_changed to company %s", company_id)
        return False


def broadcast_lockers_refresh(company_id):
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("No channel layer available")
        return False

    message = {
        'type': 'lockers.refresh',
        'timestamp': datetime.utcnow().isoformat(),
    }

    try:
        async_to_sync(channel_layer.group_send)(
            f'access_events_company_{company_id}',
            message,
        )
        async_to_sync(channel_layer.group_send)('access_events_global', message)
        logger.info("Broadcast lockers_refresh to company %s", company_id)
        return True
    except Exception:
        logger.exception("Failed to broadcast lockers_refresh to company %s", company_id)
        return False
