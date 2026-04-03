from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/users/', include('apps.users.urls')),
    path('api/lockers/', include('apps.lockers.urls')),
    path('api/rentals/', include('apps.rentals.urls')),
    path('api/devices/', include('apps.devices.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
