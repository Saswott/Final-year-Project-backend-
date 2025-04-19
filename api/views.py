from rest_framework import generics, status, permissions, viewsets, filters
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import action, api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta, datetime
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .models import User, Medicine, Category, Pharmacy
from .serializers import (
    PharmacyRegistrationSerializer,
    UserSerializer,
    MedicineSerializer,
    CategorySerializer,
    EmployeeRegistrationSerializer
)

# ------------------ CONSTANTS ------------------

ERROR_NOT_AN_EMPLOYEE = "This user is not an employee"

# ------------------ PHARMACY REGISTRATION ------------------

class PharmacyRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = PharmacyRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

# ------------------ USER DETAILS ------------------

class UserMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            'email': user.email,
            'role': user.role,
            'pharmacy': user.pharmacy.pharmacy_name if user.pharmacy else None,
        }
        return Response(data, status=status.HTTP_200_OK)

# ------------------ CATEGORY VIEWSET ------------------

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

# ------------------ MEDICINE VIEWSET ------------------

class MedicineViewSet(viewsets.ModelViewSet):
    serializer_class = MedicineSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status']
    search_fields = ['name', 'manufacturer']
    ordering_fields = ['name', 'price', 'stock', 'expiry_date']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Medicine.objects.all()
        elif user.role == 'pharmacy':
            try:
                pharmacy = Pharmacy.objects.get(user=user)
                return Medicine.objects.filter(pharmacy=pharmacy)
            except Pharmacy.DoesNotExist:
                return Medicine.objects.none()
        return Medicine.objects.none()

    def get_serializer_context(self):
        return super().get_serializer_context()

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        try:
            if 'stock' in data:
                data['stock'] = int(data['stock'])
            if 'price' in data:
                data['price'] = float(data['price'])
            if 'expiry_date' in data:
                datetime.strptime(data['expiry_date'], '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        if self.request.user.role == 'pharmacy':
            try:
                pharmacy = Pharmacy.objects.get(user=self.request.user)
                serializer.save(pharmacy=pharmacy)
            except Pharmacy.DoesNotExist:
                raise ValueError("No pharmacy associated with this user")
        else:
            serializer.save()

    def update(self, request, *args, **kwargs):
        data = request.data.copy()
        if 'stock' in data and isinstance(data['stock'], str):
            try:
                data['stock'] = int(data['stock'])
            except ValueError:
                return Response({"stock": ["Must be a valid integer"]}, status=status.HTTP_400_BAD_REQUEST)
        if 'price' in data and isinstance(data['price'], str):
            try:
                data['price'] = float(data['price'])
            except ValueError:
                return Response({"price": ["Must be a valid decimal number"]}, status=status.HTTP_400_BAD_REQUEST)

        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        queryset = self.get_queryset().filter(stock__lte=200)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        queryset = self.get_queryset().filter(stock=0)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        three_months_later = timezone.now().date() + timedelta(days=90)
        queryset = self.get_queryset().filter(expiry_date__lte=three_months_later)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        return Response({
            'total_items': queryset.count(),
            'low_stock': queryset.filter(stock__lte=200).count(),
            'out_of_stock': queryset.filter(stock=0).count(),
            'expiring_soon': queryset.filter(expiry_date__lte=timezone.now().date() + timedelta(days=90)).count(),
        })

# ------------------ EMPLOYEE REGISTRATION ------------------

class EmployeeRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = EmployeeRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_employee(request):
    serializer = EmployeeRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'user': UserSerializer(user).data,
            'message': 'Employee registered successfully!'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ------------------ EMPLOYEE MANAGEMENT VIEWSET ------------------

class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'pharmacy':
            try:
                pharmacy = user.pharmacy_profile
                return User.objects.filter(pharmacy=pharmacy, role='employee')
            except AttributeError:
                return User.objects.none()
        elif user.role == 'admin':
            return User.objects.filter(role='employee')
        return User.objects.none()

    @action(detail=True, methods=['patch'])
    def verify(self, request, pk=None):
        employee = self.get_object()
        is_verified = request.data.get('is_verified', False)

        if employee.role != 'employee':
            return Response({"error": ERROR_NOT_AN_EMPLOYEE}, status=status.HTTP_400_BAD_REQUEST)

        employee.is_active = is_verified
        employee.save()

        return Response({
            "message": f"Employee {employee.email} verification status updated",
            "is_verified": is_verified
        })

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        employee = self.get_object()
        if employee.role != 'employee':
            return Response({"error": ERROR_NOT_AN_EMPLOYEE}, status=status.HTTP_400_BAD_REQUEST)

        document = request.FILES.get('document')
        if not document:
            return Response({"error": "No document provided"}, status=status.HTTP_400_BAD_REQUEST)

        document_type = request.data.get('document_type', 'citizenship')

        if document_type == 'citizenship':
            employee.citizenship_document = document
            employee.save()
            return Response({"message": "Citizenship document uploaded successfully"})
        else:
            return Response({"error": "Invalid document type"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def upload_profile_picture(self, request, pk=None):
        employee = self.get_object()
        if employee.role != 'employee':
            return Response({"error": ERROR_NOT_AN_EMPLOYEE}, status=status.HTTP_400_BAD_REQUEST)

        profile_picture = request.FILES.get('profile_picture')
        if not profile_picture:
            return Response({"error": "No profile picture provided"}, status=status.HTTP_400_BAD_REQUEST)

        employee.profile_picture = profile_picture
        employee.save()
        return Response({"message": "Profile picture uploaded successfully"})

    @action(detail=False, methods=['get'])
    def pending(self, request):
        queryset = self.get_queryset().filter(is_active=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
