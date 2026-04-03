from django.urls import re_path

from .consumers import AccessEventsConsumer, PiSyncConsumer

websocket_urlpatterns = [
    re_path(r'^ws/access-events/$', AccessEventsConsumer.as_asgi()),
    re_path(r'^ws/pi-sync/$', PiSyncConsumer.as_asgi()),
]
