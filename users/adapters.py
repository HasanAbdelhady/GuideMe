from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse
from django.shortcuts import redirect

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter to handle regular account operations
    """
    def get_login_redirect_url(self, request):
        """
        Redirect to chat after login
        """
        return '/chat/new/'

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter to handle Google OAuth flow
    """
    def save_user(self, request, sociallogin, form=None):
        """
        Save the user and mark them as needing to complete preferences
        """
        user = super().save_user(request, sociallogin, form)
        
        # Mark user as needing to complete preferences
        # We'll use a session variable to track this
        request.session['needs_preferences'] = True
        request.session['google_signup'] = True
        
        return user
    
    def get_signup_redirect_url(self, request):
        """
        Redirect to preferences page after Google signup
        """
        return '/users/register-preferences/'
    
    def get_login_redirect_url(self, request):
        """
        Check if user came from signup flow and redirect accordingly
        """
        # If user came from register page (has next parameter with preferences)
        next_url = request.GET.get('next', '')
        if 'register-preferences' in next_url:
            # Check if user has completed preferences
            user = request.user
            if user.is_authenticated:
                # Check if user has any learning preferences set
                has_preferences = (
                    user.learning_style_visual or 
                    user.learning_style_auditory or 
                    user.learning_style_kinesthetic or 
                    user.learning_style_reading or
                    user.interests.exists()
                )
                
                if not has_preferences:
                    # User needs to complete preferences
                    request.session['google_signup'] = True
                    request.session['needs_preferences'] = True
                    return '/users/register-preferences/'
        
        # Default redirect to chat
        return '/chat/new/'
    
    def populate_user(self, request, sociallogin, data):
        """
        Populate user data from Google OAuth
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Extract additional data from Google
        if sociallogin.account.provider == 'google':
            extra_data = sociallogin.account.extra_data
            
            # Set username from email if not provided
            if not user.username and user.email:
                # Create username from email (before @ symbol)
                base_username = user.email.split('@')[0]
                # Ensure username is unique
                from django.contrib.auth import get_user_model
                User = get_user_model()
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                user.username = username
        
        return user 