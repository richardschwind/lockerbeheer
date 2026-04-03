from rest_framework import generics, permissions, viewsets, filters
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .models import User, Company, LockerUser, NFCTag
from .serializers import UserSerializer, RegisterSerializer, CompanySerializer, LockerUserSerializer, NFCTagSerializer


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_superuser or request.user.role == 'superadmin')


class IsCompanyAdminOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or
            request.user.role in ['superadmin', 'company_admin']
        )


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsSuperAdmin]
    serializer_class = RegisterSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'superadmin':
            return User.objects.select_related('company').all()
        return User.objects.filter(company=user.company).select_related('company')


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'city', 'email']


class LockerUserViewSet(viewsets.ModelViewSet):
    serializer_class = LockerUserSerializer
    permission_classes = [IsCompanyAdminOrAbove]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'employee_number']
    ordering_fields = ['last_name', 'first_name', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = LockerUser.objects.select_related('website_user', 'website_user__company').prefetch_related('nfc_tags')
        if user.is_superuser or user.role == 'superadmin':
            return qs
        return qs.filter(website_user__company=user.company)

    def perform_create(self, serializer):
        website_user = serializer.validated_data['website_user']
        user = self.request.user

        if user.is_superuser or user.role == 'superadmin':
            serializer.save()
            return

        if website_user.company_id != user.company_id:
            raise PermissionDenied('Je kunt alleen lockergebruikers toevoegen onder je eigen bedrijf.')

        serializer.save()


class NFCTagViewSet(viewsets.ModelViewSet):
    serializer_class = NFCTagSerializer
    permission_classes = [IsCompanyAdminOrAbove]
    filter_backends = [filters.SearchFilter]
    search_fields = ['uid', 'locker_user__first_name', 'locker_user__last_name']

    def get_queryset(self):
        user = self.request.user
        qs = NFCTag.objects.select_related('locker_user', 'locker_user__website_user', 'locker_user__website_user__company')
        if user.is_superuser or user.role == 'superadmin':
            return qs
        return qs.filter(locker_user__website_user__company=user.company)
