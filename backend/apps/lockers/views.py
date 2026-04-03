from rest_framework import viewsets, permissions, filters
from rest_framework.exceptions import PermissionDenied
from .models import Locker, LockerLocation
from .serializers import LockerSerializer, LockerLocationSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and (
            request.user.is_superuser or request.user.role in ['superadmin', 'company_admin']
        )


class LockerLocationViewSet(viewsets.ModelViewSet):
    serializer_class = LockerLocationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'address']

    def get_queryset(self):
        user = self.request.user
        qs = LockerLocation.objects.select_related('company').all()
        if user.is_superuser or user.role == 'superadmin':
            return qs
        return qs.filter(company=user.company)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser or user.role == 'superadmin':
            serializer.save()
            return

        serializer.save(company=user.company)

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_superuser or user.role == 'superadmin':
            serializer.save()
            return

        company = serializer.validated_data.get('company', serializer.instance.company)
        if not company or company.id != user.company_id:
            raise PermissionDenied('Je kunt alleen locaties beheren binnen je eigen bedrijf.')
        serializer.save()


class LockerViewSet(viewsets.ModelViewSet):
    serializer_class = LockerSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['number', 'location__name']
    ordering_fields = ['number', 'location', 'status', 'size']

    def get_queryset(self):
        user = self.request.user
        qs = Locker.objects.select_related('location', 'location__company').all()
        if user.is_superuser or user.role == 'superadmin':
            return qs
        return qs.filter(location__company=user.company)

    def perform_create(self, serializer):
        location = serializer.validated_data.get('location')
        user = self.request.user
        if user.is_superuser or user.role == 'superadmin':
            serializer.save()
            return
        if not location or location.company_id != user.company_id:
            raise PermissionDenied('Je kunt alleen lockers maken binnen locaties van je eigen bedrijf.')
        serializer.save()

    def perform_update(self, serializer):
        location = serializer.validated_data.get('location', serializer.instance.location)
        user = self.request.user
        if not (user.is_superuser or user.role == 'superadmin') and (
            not location or location.company_id != user.company_id
        ):
            raise PermissionDenied('Je kunt alleen lockers beheren binnen locaties van je eigen bedrijf.')
        serializer.save()
