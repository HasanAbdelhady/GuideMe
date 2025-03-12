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
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.urls import reverse_lazy
from django.http import JsonResponse
from chat.views import get_system_prompt
from django.http import JsonResponse
from .models import Interest, CustomUser
from django.contrib.auth.decorators import login_required

User = get_user_model()


class UserRegistrationView(View):
    @method_decorator(csrf_protect)
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('chat')
        form = CustomUserCreationForm()
        return render(request, 'users/register.html', {'form': form})

    @method_decorator(csrf_protect)
    def post(self, request):
        if request.user.is_authenticated:
            return redirect('chat')
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            messages.success(
                request, 'Registration successful! Please login to continue.')
            return redirect('login')
        else:
            # Add specific error messages for each field
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return render(request, 'users/register.html', {'form': form})


class UserLoginView(View):
    def get(self, request):
        return render(request, 'users/login.html')


class UserProfileView(LoginRequiredMixin, View):
    def get(self, request):
        user_form = CustomUserChangeForm(instance=request.user)
        password_form = PasswordChangeForm()

        # Get all interests and user's current interests
        interests = Interest.objects.all()
        user_interests = request.user.interests.all()

        context = {
            'user_form': user_form,
            'password_form': password_form,
            'subject_choices': CustomUser.SUBJECT_CHOICES,
            'interests': interests,
            'user_interests': user_interests,
            'study_time_choices': CustomUser.STUDY_TIME_CHOICES,
            'quiz_preference_choices': CustomUser.QUIZ_PREFERENCE_CHOICES,
            'learning_style_choices': CustomUser.LEARNING_STYLE_CHOICES,
        }
        return render(request, 'users/profile.html', context)

    def post(self, request):
        action = request.POST.get('action')

        if action == 'update_profile':
            user_form = CustomUserChangeForm(
                request.POST,
                request.FILES,
                instance=request.user
            )
            if user_form.is_valid():
                user_form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect("profile")
            messages.error(request, 'Please correct the errors below.')

        elif action == 'change_password':
            password_form = PasswordChangeForm(request.POST)
            if password_form.is_valid():
                if request.user.check_password(password_form.cleaned_data['old_password']):
                    request.user.set_password(
                        password_form.cleaned_data['new_password1'])
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    messages.success(request, 'Password changed successfully!')
                    return redirect("profile")
                else:
                    messages.error(request, 'Current password is incorrect.')
            else:
                messages.error(request, 'Please correct the errors below.')

        elif action == 'update_preferences':
            try:
                # Update learning styles
                learning_styles = {
                    'visual': request.POST.get('learning_style_visual'),
                    'auditory': request.POST.get('learning_style_auditory'),
                    'kinesthetic': request.POST.get('learning_style_kinesthetic'),
                    'reading': request.POST.get('learning_style_reading'),
                }

                for style, value in learning_styles.items():
                    setattr(request.user, f'learning_style_{style}', int(
                        value == 'true'))

                # Update study time preference
                study_time = request.POST.get('preferred_study_time')
                if study_time in dict(CustomUser.STUDY_TIME_CHOICES):
                    request.user.preferred_study_time = study_time

                # Update quiz preference
                quiz_pref = request.POST.get('quiz_preference')
                if quiz_pref and quiz_pref.isdigit():
                    quiz_pref_int = int(quiz_pref)
                    if quiz_pref_int in dict(CustomUser.QUIZ_PREFERENCE_CHOICES):
                        request.user.quiz_preference = quiz_pref_int

                # Update interests
                interest_ids = request.POST.getlist('interests[]')
                if interest_ids:
                    # Clear existing interests and add new ones
                    request.user.interests.clear()
                    interests_to_add = Interest.objects.filter(
                        id__in=interest_ids)
                    request.user.interests.add(*interests_to_add)

                # Save custom interests if any
                custom_interests = request.POST.get(
                    'custom_interests', '').strip()
                if custom_interests:
                    request.user.custom_interests = custom_interests

                request.user.save()

                # Update system prompt in session
                new_prompt = get_system_prompt(request.user)
                request.session['system_prompt'] = new_prompt

                messages.success(request, 'Preferences updated successfully!')
                return redirect('profile')
            except Exception as e:
                messages.error(
                    request, f'Error updating preferences: {str(e)}')
                return redirect('profile')

        return redirect("profile")


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


class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('login')

    def post(self, request, *args, **kwargs):
        logout(request)
        return redirect(self.next_page)


@login_required
def get_interests(request):
    interests = list(Interest.objects.values('id', 'name'))
    return JsonResponse(interests, safe=False)


@login_required
def create_interest(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            interest, created = Interest.objects.get_or_create(
                name=name.lower())
            return JsonResponse({
                'id': interest.id,
                'name': interest.name
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
