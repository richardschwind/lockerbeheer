from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import RaspberryPiViewSet, AccessEventViewSet, PiSyncView

router = SimpleRouter()
router.register(r'raspberry-pis', RaspberryPiViewSet, basename='raspberry-pi')
router.register(r'access-events', AccessEventViewSet, basename='access-event')
router.register(r'pi-sync', PiSyncView, basename='pi-sync')

urlpatterns = [
    path('', include(router.urls)),
]
