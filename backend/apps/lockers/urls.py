from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import LockerViewSet, LockerLocationViewSet

router = SimpleRouter()
router.register(r'locations', LockerLocationViewSet, basename='locker-location')
router.register(r'', LockerViewSet, basename='locker')

urlpatterns = [
    path('', include(router.urls)),
]
