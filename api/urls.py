from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import AnalyticsPDFView, CustomTokenObtainPairView
from .views import PrescriptionViewSet
from .views import InvoiceViewSet
from .views import InvoicePDFView
from .views import MessageViewSet  # Import the MessageViewSet
from .views import SalesByEmployeeLast7Days

from .views import (
    PharmacyRegisterView,
    UserMeView,
    MedicineViewSet,
    CategoryViewSet,
    EmployeeRegisterView,
    EmployeeViewSet,
    RecentActivityView,  # Import the RecentActivityView
    AnalyticsView  # Import the AnalyticsView
)

# Set up viewsets for routing
router = DefaultRouter()
router.register(r'medicines', MedicineViewSet, basename='medicine')
router.register(r'categories', CategoryViewSet)
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    # JWT authentication endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Custom endpoints
    path('register/pharmacy/', PharmacyRegisterView.as_view(), name='register_pharmacy'),
    path('register/employee/', EmployeeRegisterView.as_view(), name='register_employee'),
    path('user/me/', UserMeView.as_view(), name='user_me'),
    
    # MedicineViewSet
    path('medicines/stats/', MedicineViewSet.as_view({'get': 'stats'}), name='medicine-stats'),
    path('invoices/stats/', InvoiceViewSet.as_view({'get': 'stats'}), name='invoice-stats'),
    path('medicines/check-availability/', MedicineViewSet.as_view({'get': 'check_availability'}), name='medicine-check-availability'),
    path('invoices/<int:pk>/download/', InvoiceViewSet.as_view({'get': 'download'}), name='invoice-download'),
    path('invoices/<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice-pdf'),
    
    # Recent Activity endpoint
    path('recent-activity/', RecentActivityView.as_view(), name='recent-activity'),
    path('messages/mark_read/<int:pk>/', MessageViewSet.as_view({'patch': 'mark_read'}), name='message-mark-read'),
    path('messages/unread_count/', MessageViewSet.as_view({'get': 'unread_count'}), name='message-unread-count'),

    path('analytics/', AnalyticsView.as_view(), name='analytics'),
    path('analytics/download/', AnalyticsPDFView.as_view(), name='analytics-pdf'),
    path('analytics/employee-sales-last-7-days/', SalesByEmployeeLast7Days.as_view(), name='employee-sales-last-7-days'),
    path('invoices/employee-stats/<int:employee_id>/', InvoiceViewSet.as_view({'get': 'employee_stats'}), name='invoice-employee-stats'),

    # Router-based endpoints
    path('', include(router.urls)),
]