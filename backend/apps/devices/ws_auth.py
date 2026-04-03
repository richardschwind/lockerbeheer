from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken, TokenError

from apps.users.models import User


@database_sync_to_async
def get_user_for_token(validated_token):
    user_id = validated_token.get('user_id')
    if not user_id:
        return AnonymousUser()

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class QueryStringJWTAuthMiddleware(BaseMiddleware):
    """Authenticate websocket gebruikers met JWT token in querystring."""

    async def __call__(self, scope, receive, send):
        scope['user'] = AnonymousUser()

        query_string = scope.get('query_string', b'').decode()
        token = parse_qs(query_string).get('token', [None])[0]

        if token:
            try:
                validated_token = AccessToken(token)
                scope['user'] = await get_user_for_token(validated_token)
            except TokenError:
                scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
