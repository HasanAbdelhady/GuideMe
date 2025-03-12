from django.urls import path
from .views import (
    UserRegistrationView,
    UserProfileView,
    TokenObtainPairView,
    TokenRefreshView,
    LogoutView,
    UserProfileView
)
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from . import views

urlpatterns = [
    path('login/', LoginView.as_view(
        template_name='users/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    
    # JWT Token endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('settings/', UserProfileView.as_view(), name='settings'),
    path('update_preferences/', UserProfileView.as_view(), name='update_preferences'),
    path('interests/', views.get_interests, name='get_interests'),
    path('interests/create/', views.create_interest, name='create_interest'),
]