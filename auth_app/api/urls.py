"""Contains all necessary URLs for the auth_app API"""
from django.urls import path
from auth_app.api.views import RegisterView, LoginView, LogoutView, TokenRefreshView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='api-login'),
    path('logout/', LogoutView.as_view(), name='api-logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='api-token-refresh'),
]
