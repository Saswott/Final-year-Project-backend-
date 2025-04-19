from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    PharmacyRegisterView,
    UserMeView,
    MedicineViewSet,
    CategoryViewSet,
    EmployeeRegisterView,
    EmployeeViewSet  # Import EmployeeViewSet
)

# Set up viewsets for routing
router = DefaultRouter()
router.register(r'medicines', MedicineViewSet, basename='medicine')
router.register(r'categories', CategoryViewSet)
router.register(r'employees', EmployeeViewSet, basename='employee')

urlpatterns = [
    # JWT authentication endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Custom endpoints
    path('register/pharmacy/', PharmacyRegisterView.as_view(), name='register_pharmacy'),
    path('register/employee/', EmployeeRegisterView.as_view(), name='register_employee'),  # Moved here correctly
    path('user/me/', UserMeView.as_view(), name='user_me'),
    
    # Router-based endpoints
    path('', include(router.urls)),
]
