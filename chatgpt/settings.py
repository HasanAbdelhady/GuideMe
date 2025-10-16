import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# Build paths inside the project like this: BASE_DIR / 'subdir'.


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
# Security: Restrict allowed hosts
ALLOWED_HOSTS = (
    [
        "localhost",
        "127.0.0.1",
        "guideme-eg.duckdns.org",
        "*.railway.app",
        "*.up.railway.app",
    ]
    if DEBUG
    else [
        "guideme-eg.duckdns.org",
        "*.railway.app",
        "*.up.railway.app",
    ]
)

# CSRF and Security Settings for Railway
CSRF_TRUSTED_ORIGINS = [
    "https://guideme-eg.duckdns.org",
    "https://*.railway.app",
    "https://*.up.railway.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True  # Force HTTPS
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000  # Enable HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    USE_TZ = True


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # Required for allauth
    # Third party apps
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Local apps
    "chat",
    "users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Must be after SecurityMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # Required for allauth
]

ROOT_URLCONF = "chatgpt.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",  # Add this line
            BASE_DIR / "chat",
            BASE_DIR / "flashcard_app" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "chat.context_processors.media_context",  # Add our custom processor
            ],
        },
    },
]

# WSGI_APPLICATION = 'chatgpt.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# Database configuration with proper error handling
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Use dj-database-url to properly parse DATABASE_URL (handles query params)
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=0,
            conn_health_checks=True,
        )
    }
else:
    # Fallback to SQLite for local development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.postgresql',
#        'NAME': 'guideme',
#        'USER': 'postgres',
#        'PASSWORD': 'postgres',
#        'HOST': 'localhost',
#       'PORT': 5432,
#       'CONN_MAX_AGE': 0,  # Close connection after each request
#       'OPTIONS': {
#           'connect_timeout': 10,
#       }
#   }
# }
# If you want to go back to sqlite3
# DATABASES = {
#      'default': {
#          'ENGINE': 'django.db.backends.sqlite3',
#          'NAME': BASE_DIR / 'db.sqlite3',
#      }
#  }


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
AUTH_USER_MODEL = "users.CustomUser"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Additional static files directories (for app-specific static files)
STATICFILES_DIRS = [
    BASE_DIR / "chat" / "static",
    BASE_DIR / "users" / "static",
]

# WhiteNoise configuration (Django 4.2+ format)
# Use CompressedStaticFilesStorage instead of Manifest version to avoid missing manifest errors
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# WhiteNoise settings for production
WHITENOISE_AUTOREFRESH = DEBUG  # Auto-refresh in development only


# Session Security Settings - ChatGPT-like UX with 1-year sessions
SESSION_COOKIE_AGE = 31536000  # 1 year (365 days * 24 hours * 60 minutes * 60 seconds)
SESSION_COOKIE_SECURE = not DEBUG  # HTTPS only in production
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access (XSS protection)
SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection while allowing normal navigation
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Stay logged in after browser close
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session expiry on every request

# Additional Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Add these settings for authentication
LOGIN_URL = "login"  # Name of our login URL pattern
LOGIN_REDIRECT_URL = "chat"  # Where to redirect after successful login
LOGOUT_REDIRECT_URL = "login"  # Where to redirect after logout

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django Allauth Configuration
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by email
    "allauth.account.auth_backends.AuthenticationBackend",
    # Custom backend to allow login with email or username
    "users.backends.EmailOrUsernameModelBackend",
]

# Allauth settings (updated to new format)
# Change to 'mandatory' if you want email verification
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "username*",
    "password1*",
    "password2*",
]  # Required signup fields
ACCOUNT_LOGIN_METHODS = {"email"}  # Allow login with email
# Redirect to preferences after Google signup
ACCOUNT_SIGNUP_REDIRECT_URL = "/users/register-preferences/"
ACCOUNT_LOGOUT_ON_GET = True  # Allow logout via GET request (no confirmation)
LOGIN_REDIRECT_URL = "/chat/new/"
LOGOUT_REDIRECT_URL = "/users/login/"

# Custom adapters
ACCOUNT_ADAPTER = "users.adapters.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "users.adapters.CustomSocialAccountAdapter"

# Social account settings
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "OAUTH_PKCE_ENABLED": True,
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "key": "",
        },
    }
}
