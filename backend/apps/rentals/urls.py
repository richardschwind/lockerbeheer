from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import RentalViewSet

router = SimpleRouter()
router.register(r'', RentalViewSet, basename='rental')

urlpatterns = [
    path('', include(router.urls)),
]
