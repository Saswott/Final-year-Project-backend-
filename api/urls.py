from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import PharmacyRegisterView, UserMeView

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/pharmacy/', PharmacyRegisterView.as_view(), name='register_pharmacy'),
    path('user/me/', UserMeView.as_view(), name='user_me'),  # Notice the path change here
]


