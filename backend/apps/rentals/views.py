from rest_framework import viewsets, permissions, filters
from .models import Rental
from .serializers import RentalSerializer


class IsCompanyAdminOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or
            request.user.role in ['superadmin', 'company_admin']
        )


class RentalViewSet(viewsets.ModelViewSet):
    serializer_class = RentalSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['locker_user__first_name', 'locker_user__last_name', 'locker__number']
    ordering_fields = ['start_date', 'end_date', 'created_at', 'status']

    def get_queryset(self):
        user = self.request.user
        qs = Rental.objects.select_related(
            'locker', 'locker__location', 'locker__location__company',
            'locker_user', 'locker_user__website_user', 'locker_user__website_user__company',
            'created_by'
        )
        if user.is_superuser or user.role == 'superadmin':
            return qs
        return qs.filter(locker_user__website_user__company=user.company)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsCompanyAdminOrAbove()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
