from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import RegisterView, ProfileView, UserViewSet, CompanyViewSet, LockerUserViewSet, NFCTagViewSet

router = SimpleRouter()
router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'locker-users', LockerUserViewSet, basename='locker-user')
router.register(r'nfc-tags', NFCTagViewSet, basename='nfc-tag')
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='user-register'),
    path('me/', ProfileView.as_view(), name='user-profile'),
    path('', include(router.urls)),
]
