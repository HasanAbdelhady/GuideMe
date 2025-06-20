import json
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from .forms import CustomUserCreationForm, CustomUserChangeForm, PasswordChangeForm
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import update_session_auth_hash
# Removed DjangoLogoutView import - using allauth logout instead
from django.urls import reverse_lazy
from .models import Interest, CustomUser, UserInterest
from django.db import transaction

User = get_user_model()

SUBJECT_CHOICES = [
    "Machine Learning", "Deep Learning", "Natural Language Processing",
    "Computer Vision", "Artificial Intelligence", "Data Science",
    "Python Programming", "Data Structures & Algorithms", "Databases",
    "Web Development", "Cloud Computing", "Cybersecurity",
    "Robotics", "Data Engineering",
]


class UserRegistrationView(View):
    @method_decorator(csrf_protect)
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('chat')
        form = CustomUserCreationForm()
        return render(request, 'users/register.html', {'form': form, 'interests': SUBJECT_CHOICES})

    @method_decorator(csrf_protect)
    def post(self, request):
        if request.user.is_authenticated:
            return redirect('chat')

        form = CustomUserCreationForm(request.POST, request.FILES)
        print(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                print("Form is valid")

                # Update learning preferences from form data
                learning_styles = {
                    'visual': request.POST.get('learning_style_visual') == "1",
                    'auditory': request.POST.get('learning_style_auditory') == "1",
                    'kinesthetic': request.POST.get('learning_style_kinesthetic') == "1",
                    'reading': request.POST.get('learning_style_reading') == "1",
                }
                for style, value in learning_styles.items():
                    setattr(user, f'learning_style_{style}', value)

                # Update study time preference
                study_time = request.POST.get('preferred_study_time')
                if study_time in dict(CustomUser.STUDY_TIME_CHOICES):
                    user.preferred_study_time = study_time

                # Update quiz preference
                quiz_pref = request.POST.get('quiz_preference')
                if quiz_pref and quiz_pref.isdigit():
                    quiz_pref_int = int(quiz_pref)
                    if quiz_pref_int in dict(CustomUser.QUIZ_PREFERENCE_CHOICES):
                        user.quiz_preference = quiz_pref_int

                print("Updating user attributes")
                # Use update() to save the user attributes without causing a unique constraint issue
                user.save()
                # Now handle the interests
                interest_names = request.POST.getlist('interests')
                print(f"Interest names: {interest_names}")

                # Create user interests
                for interest_name in interest_names:
                    # Try to find existing interest or create new one
                    interest, created = Interest.objects.get_or_create(
                        name=interest_name)
                    # Create the user-interest relationship
                    UserInterest.objects.create(user=user, interest=interest)
                    print(f"Added interest: {interest}")

                # Now log in the user - specify backend for multiple auth backends
                from django.contrib.auth.backends import ModelBackend
                login(request, user,
                      backend='django.contrib.auth.backends.ModelBackend')

                messages.success(
                    request, 'Your account has been created! You can now start chatting.')
                return redirect('new_chat')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')

        interests = list(Interest.objects.values('id', 'name'))
        print(f"Available interests: {interests}")
        return render(request, 'users/register.html', {'form': form, 'interests': interests})


class UserLoginView(View):
    def get(self, request):
        return render(request, 'users/login.html')


class GoogleSignupPreferencesView(LoginRequiredMixin, View):
    """
    View to handle preferences setup for users who signed up with Google
    """

    def get(self, request):
        # Allow access if user came from Google signup OR if they don't have preferences set
        user = request.user
        has_preferences = (
            user.learning_style_visual or
            user.learning_style_auditory or
            user.learning_style_kinesthetic or
            user.learning_style_reading or
            user.interests.exists()
        )

        # If user has preferences already, redirect to chat
        if has_preferences and not request.session.get('google_signup', False):
            return redirect('chat')

        # Get available interests
        interests = Interest.objects.all()
        context = {
            'interests': interests,
            'study_time_choices': CustomUser.STUDY_TIME_CHOICES,
            'quiz_preference_choices': CustomUser.QUIZ_PREFERENCE_CHOICES,
            'is_google_signup': True,
        }
        return render(request, 'users/google_preferences.html', context)

    def post(self, request):
        # Check if user came from Google signup
        if not request.session.get('google_signup', False):
            return redirect('profile')

        user = request.user

        # Update learning styles
        learning_styles = {
            'visual': request.POST.get('learning_style_visual') == "1",
            'auditory': request.POST.get('learning_style_auditory') == "1",
            'kinesthetic': request.POST.get('learning_style_kinesthetic') == "1",
            'reading': request.POST.get('learning_style_reading') == "1",
        }
        for style, value in learning_styles.items():
            setattr(user, f'learning_style_{style}', value)

        # Update study time preference
        study_time = request.POST.get('preferred_study_time')
        if study_time in dict(CustomUser.STUDY_TIME_CHOICES):
            user.preferred_study_time = study_time

        # Update quiz preference
        quiz_pref = request.POST.get('quiz_preference')
        if quiz_pref and quiz_pref.isdigit():
            quiz_pref_int = int(quiz_pref)
            if quiz_pref_int in dict(CustomUser.QUIZ_PREFERENCE_CHOICES):
                user.quiz_preference = quiz_pref_int

        # Save user changes
        user.save()

        # Handle interests
        interest_names = request.POST.getlist('interests')
        for interest_name in interest_names:
            interest, created = Interest.objects.get_or_create(
                name=interest_name)
            UserInterest.objects.get_or_create(user=user, interest=interest)

        # Clear session flags
        request.session.pop('google_signup', None)
        request.session.pop('needs_preferences', None)

        messages.success(request, 'Welcome! Your preferences have been saved.')
        return redirect('chat')


class UserProfileView(LoginRequiredMixin, View):
    def get(self, request):
        user_form = CustomUserChangeForm(instance=request.user)
        password_form = PasswordChangeForm(user=request.user)
        interests = Interest.objects.all()
        user_interests = request.user.interests.all()
        context = {
            'user_form': user_form,
            'password_form': password_form,
            'interests': interests,
            'user_interests': user_interests,
            'study_time_choices': CustomUser.STUDY_TIME_CHOICES,
            'quiz_preference_choices': CustomUser.QUIZ_PREFERENCE_CHOICES,
            'learning_style_choices': CustomUser.LEARNING_STYLE_CHOICES,
        }
        return render(request, 'users/profile.html', context)

    def handle_password_change(self, request):
        password_form = PasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Password updated successfully!')
        else:
            for field, errors in password_form.errors.items():
                for error in errors:
                    messages.error(request, f'Password {field}: {error}')
        return redirect('profile')

    def post(self, request):
        action = request.POST.get('action')
        print(request.POST)
        if action == 'update_profile':
            user_form = CustomUserChangeForm(
                request.POST, request.FILES, instance=request.user
            )
            if user_form.is_valid():
                user = user_form.save(commit=False)

                # Update learning styles
                learning_styles = {
                    'visual': request.POST.get('learning_style_visual') == "1",
                    'auditory': request.POST.get('learning_style_auditory') == "1",
                    'kinesthetic': request.POST.get('learning_style_kinesthetic') == "1",
                    'reading': request.POST.get('learning_style_reading') == "1",
                }
                for style, value in learning_styles.items():
                    setattr(user, f'learning_style_{style}', value)

                # Update study time preference
                study_time = request.POST.get('preferred_study_time')
                if study_time in dict(CustomUser.STUDY_TIME_CHOICES):
                    user.preferred_study_time = study_time

                # Update quiz preference
                quiz_pref = request.POST.get('quiz_preference')
                if quiz_pref and quiz_pref.isdigit():
                    quiz_pref_int = int(quiz_pref)
                    if quiz_pref_int in dict(CustomUser.QUIZ_PREFERENCE_CHOICES):
                        user.quiz_preference = quiz_pref_int

                # Save user changes
                user.save()

                messages.success(request, 'Profile updated successfully!')
            else:
                for field, errors in user_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

        elif action == 'add_interest':
            interest_name = request.POST.get('interest_name')
            if interest_name and interest_name.strip():
                interest_name = interest_name.strip()
                # Try to find existing interest
                interest, created = Interest.objects.get_or_create(
                    name=interest_name)

                # Check if user already has this interest
                if not UserInterest.objects.filter(user=request.user, interest=interest).exists():
                    # Create the relationship
                    UserInterest.objects.create(
                        user=request.user, interest=interest)
                    messages.success(
                        request, f'Added interest: {interest.name}')
                else:
                    messages.info(
                        request, f'You already have "{interest.name}" in your interests')
            else:
                messages.error(request, 'Invalid interest name')

        elif action == 'remove_interest':
            interest_id = request.POST.get('interest_id')
            if interest_id and interest_id.isdigit():
                try:
                    interest = Interest.objects.get(id=int(interest_id))
                    # Find and delete the relationship
                    user_interest = UserInterest.objects.filter(
                        user=request.user,
                        interest=interest
                    ).first()

                    if user_interest:
                        user_interest.delete()
                        messages.success(
                            request, f'Removed interest: {interest.name}')
                    else:
                        messages.error(
                            request, 'You haven\'t added this interest')
                except Interest.DoesNotExist:
                    messages.error(request, 'Interest not found')
            else:
                messages.error(request, 'Invalid interest ID')

        elif action == 'add_multiple_interests':
            interest_ids = request.POST.getlist('interest_ids[]')
            added_count = 0
            for interest_id in interest_ids:
                if interest_id.isdigit():
                    try:
                        interest = Interest.objects.get(id=int(interest_id))
                        # Check if user already has this interest
                        if not UserInterest.objects.filter(user=request.user, interest=interest).exists():
                            # Create the relationship
                            UserInterest.objects.create(
                                user=request.user, interest=interest)
                            added_count += 1
                    except Interest.DoesNotExist:
                        continue

            if added_count > 0:
                messages.success(
                    request, f'Added {added_count} interests to your profile')
        elif action == "change_password":
            return self.handle_password_change(request)

        return redirect('profile')

# Other views remain unchanged unless they interact with interests


class TokenObtainPairView(APIView):
    def post(self, request):
        user = request.user
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })


class TokenRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh = request.data.get('refresh')
            token = RefreshToken(refresh)
            return Response({
                'access': str(token.access_token),
                'refresh': str(token),
            })
        except Exception as e:
            return Response({'error': 'Invalid refresh token'}, status=400)


class TokenObtainPairView(APIView):
    def post(self, request):
        user = request.user
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })


class TokenRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh = request.data.get('refresh')
            token = RefreshToken(refresh)
            return Response({
                'access': str(token.access_token),
                'refresh': str(token),
            })
        except Exception as e:
            return Response({'error': 'Invalid refresh token'}, status=400)


# LogoutView removed - using allauth's logout functionality instead


# @login_required
# def get_interests(request):
#     interests = list(Interest.objects.values('id', 'name'))
#     return JsonResponse(interests, safe=False)


# @login_required
# def create_interest(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             name = data.get('name', '').strip()
#             if not name:
#                 return JsonResponse({'error': 'Name is required'}, status=400)

#             interest, created = Interest.objects.get_or_create(
#                 name=name.lower())
#             return JsonResponse({
#                 'id': interest.id,
#                 'name': interest.name
#             })
#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=500)
#     return JsonResponse({'error': 'Method not allowed'}, status=405)


# @login_required
# @require_POST
# def clear_interests(request):
#     """Clear all interests for the currently logged in user."""
#     try:
#         user = request.user
#         # Clear all interests
#         user.interests.clear()
#         messages.success(
#             request, 'All interests have been successfully removed.')
#     except Exception as e:
#         messages.error(request, f'Error removing interests: {str(e)}')

#     return redirect('profile')


# @login_required
# def get_interests(request):
#     interests = list(Interest.objects.values('id', 'name'))
#     return JsonResponse(interests, safe=False)


# @login_required
# def create_interest(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             name = data.get('name', '').strip()
#             if not name:
#                 return JsonResponse({'error': 'Name is required'}, status=400)
#             interest, created = Interest.objects.get_or_create(
#                 name=name.lower())
#             return JsonResponse({'id': interest.id, 'name': interest.name})
#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=500)
#     return JsonResponse({'error': 'Method not allowed'}, status=405)


# @login_required
# @require_POST
# def clear_interests(request):
#     try:
#         user = request.user
#         user.interests.clear()  # Clears all interests via UserInterest
#         messages.success(
#             request, 'All interests have been successfully removed.')
#     except Exception as e:
#         messages.error(request, f'Error removing interests: {str(e)}')
#     return redirect('profile')
