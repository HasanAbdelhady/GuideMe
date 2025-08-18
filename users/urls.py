from django.urls import path

from .views import (
    GoogleSignupPreferencesView,
    UserLoginView,
    UserProfileView,
    UserRegistrationView,
)

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("register/", UserRegistrationView.as_view(), name="register"),
    path(
        "register-preferences/",
        GoogleSignupPreferencesView.as_view(),
        name="google_preferences",
    ),
    path("profile/", UserProfileView.as_view(), name="profile"),
    path("settings/", UserProfileView.as_view(), name="settings"),
    # path('update_preferences/', UserProfileView.as_view(),
    #      name='update_preferences'),
    # path('api/interests/', views.InterestAPI.as_view(), name='interest-api'),
    # path('interests/', views.get_interests, name='get_interests'),
    # path('interests/create/', views.create_interest, name='create_interest'),
    # path('clear-interests/', clear_interests, name='clear_interests'),
]
