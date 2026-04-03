import json
import logging
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncJsonWebsocketConsumer, AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from .models import RaspberryPi
from apps.users.models import User

logger = logging.getLogger(__name__)


@sync_to_async
def get_user_from_jwt(token_str):
    """Decode JWT and return User or None."""
    try:
        token = AccessToken(token_str)
        user_id = token.get('user_id')
        if user_id:
            return User.objects.get(id=user_id)
    except (TokenError, User.DoesNotExist):
        pass
    return None


class AccessEventsConsumer(AsyncJsonWebsocketConsumer):
    """Push access-events realtime naar de frontend."""

    async def connect(self):
        # Try to authenticate user from JWT in querystring
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        token_str = None
        if 'token' in query_params:
            token_str = query_params['token'][0] if query_params['token'] else None
        
        user = None
        if token_str:
            user = await get_user_from_jwt(token_str)
        
        if not user or (hasattr(user, 'is_anonymous') and user.is_anonymous):
            logger.warning(f"Frontend WebSocket auth failed: {token_str is None and 'no token' or 'invalid token'}")
            await self.close(code=4401)
            return

        self.user = user
        self.group_names = []

        if user.is_superuser or getattr(user, 'role', None) == 'superadmin':
            self.group_names.append('access_events_global')
        elif getattr(user, 'company_id', None):
            self.group_names.append(f'access_events_company_{user.company_id}')
        else:
            logger.warning(f"Frontend user {user.email} has no company/superadmin role")
            await self.close(code=4403)
            return

        for group_name in self.group_names:
            await self.channel_layer.group_add(group_name, self.channel_name)

        await self.accept()
        await self.send_json({'type': 'connection', 'status': 'connected'})

    async def disconnect(self, close_code):
        for group_name in getattr(self, 'group_names', []):
            await self.channel_layer.group_discard(group_name, self.channel_name)
        logger.debug(f"Frontend WebSocket disconnected: {close_code}")

    async def access_events_batch(self, event):
        await self.send_json(
            {
                'type': 'access_events_batch',
                'events': event.get('events', []),
                'count': event.get('count', 0),
            }
        )


class PiSyncConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer voor Pi registratie en whitelist-update signalen."""

    async def connect(self):
        """Handle Pi connection - require API key auth via query param."""
        try:
            # Extract token from query params using proper URL parsing
            query_string = self.scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            
            logger.info(f"Pi connection attempt. Query string: {query_string}")
            logger.info(f"Parsed query params: {query_params}")
            
            pi_key = None
            if 'token' in query_params:
                pi_key = query_params['token'][0] if query_params['token'] else None
            
            logger.info(f"Extracted PI key: {pi_key}")

            # Authenticate Pi
            pi = await sync_to_async(self._get_pi_by_key)(pi_key)
            
            logger.info(f"Pi lookup result: {pi}")

            if not pi:
                logger.warning(f"Pi authentication failed for key: {pi_key}")
                await self.close(code=4001, reason='Invalid PI_KEY')
                return

            self.pi = pi
            self.pi_unique_code = None

            # Store in cache for quick broadcast lookups
            cache_key = f'pi_ws_{pi.id}'
            cache.set(cache_key, self.channel_name, timeout=3600)

            # Add to group so we can broadcast to all Pis or specific ones
            await self.channel_layer.group_add(f'pi_sync_all', self.channel_name)
            await self.channel_layer.group_add(f'pi_sync_{pi.company_id}', self.channel_name)
            # Add Pi-specific group
            await self.channel_layer.group_add(f'pi_sync_pi_{self.pi.id}', self.channel_name)


            logger.info(f"Pi {pi.name} connected successfully")
            await self.accept()
        except Exception as e:
            logger.exception(f"Pi connect exception: {e}")
            await self.close(code=4000, reason=f'Error: {str(e)}')

    async def disconnect(self, close_code):
        """Clean up on disconnect."""
        if hasattr(self, 'pi'):
            cache_key = f'pi_ws_{self.pi.id}'
            cache.delete(cache_key)

            await self.channel_layer.group_discard(f'pi_sync_all', self.channel_name)
            await self.channel_layer.group_discard(
                f'pi_sync_{self.pi.company_id}', self.channel_name
            )
            await self.channel_layer.group_discard(f'pi_sync_pi_{self.pi.id}', self.channel_name)


    async def receive(self, text_data):
        """Receive message from Pi."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            logger.info("Pi websocket received message type=%s payload=%s", message_type, data)

            if message_type == 'register_pi':
                await self._handle_register_pi(data)
            else:
                logger.warning("Unknown Pi websocket message type=%s", message_type)
                await self.send(
                    text_data=json.dumps({
                        'type': 'error',
                        'message': f'Unknown message type: {message_type}',
                    })
                )
        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON',
                })
            )

    async def _handle_register_pi(self, data):
        """Handle Pi registration."""
        pi_unique_code = data.get('pi_unique_code')

        if not pi_unique_code:
            await self.send(
                text_data=json.dumps({
                    'type': 'error',
                    'message': 'pi_unique_code required',
                })
            )
            return

        self.pi_unique_code = pi_unique_code
        logger.info(
            "Pi registered for whitelist signals (pi_name=%s, pi_unique_code=%s, company_id=%s)",
            getattr(self.pi, 'name', 'unknown'),
            pi_unique_code,
            getattr(self.pi, 'company_id', None),
        )

        await self.send(
            text_data=json.dumps({
                'type': 'register_ack',
                'pi_unique_code': pi_unique_code,
                'message': 'Pi registered successfully',
            })
        )

    async def whitelist_changed(self, event):
        """Broadcast whitelist_changed message."""
        target_pi_code = event.get('pi_unique_code')

        if target_pi_code and self.pi_unique_code != target_pi_code:
            logger.debug(
                "Skipping whitelist_changed for pi_name=%s (registered=%s, target=%s)",
                getattr(self.pi, 'name', 'unknown'),
                self.pi_unique_code,
                target_pi_code,
            )
            return

        logger.info(
            "Delivering whitelist_changed to pi_name=%s (registered=%s, target=%s)",
            getattr(self.pi, 'name', 'unknown'),
            self.pi_unique_code,
            target_pi_code,
        )

        await self.send(
            text_data=json.dumps({
                'type': 'whitelist_changed',
                'pi_unique_code': target_pi_code,
                'timestamp': event.get('timestamp'),
            })
        )

    @staticmethod
    def _get_pi_by_key(pi_key):
        """Synchronous lookup of Pi by API key."""
        logger.debug(f"Looking up Pi with key: {pi_key}")
        try:
            pi = RaspberryPi.objects.get(api_key=pi_key, is_active=True)
            logger.info(f"Found Pi: {pi.name} (company: {pi.company.name})")
            return pi
        except RaspberryPi.DoesNotExist:
            logger.warning(f"No active Pi found with key: {pi_key}")
            return None
