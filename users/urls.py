from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, SelectOrganizationView, SignupView

urlpatterns = [
    path("auth/signup/", SignupView.as_view(), name="signup"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/select-organization/", SelectOrganizationView.as_view(), name="select_organization"),
]