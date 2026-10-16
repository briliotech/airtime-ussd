"""
Django settings for quicktop project.

All secrets and environment-specific values come from environment variables
(Railway service variables in production, a local .env file in development).
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-*0k-b&7d6ez)4^lo1!gxvsk$^rjul@6eb5ift)!0lgkg_s0%-e',
)

DEBUG = env_bool('DJANGO_DEBUG', False)

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# Railway exposes the service's public domain in this variable.
RAILWAY_PUBLIC_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_PUBLIC_DOMAIN}')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'airtime',
    'payments',
    'ussd',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'quicktop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'quicktop.wsgi.application'


# Database
# Railway's Postgres service provides DATABASE_URL; fall back to SQLite locally.

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Nairobi'

USE_I18N = True

USE_TZ = True


# Static files (served by WhiteNoise)

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Behind Railway's proxy, trust the forwarded protocol header.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('LOG_LEVEL', 'INFO')},
}


# ---------------------------------------------------------------------------
# QuickTop integrations
# ---------------------------------------------------------------------------

# Public base URL used to build callback URLs, e.g. https://quicktop.up.railway.app
PUBLIC_BASE_URL = os.environ.get(
    'PUBLIC_BASE_URL',
    f'https://{RAILWAY_PUBLIC_DOMAIN}' if RAILWAY_PUBLIC_DOMAIN else 'http://localhost:8000',
).rstrip('/')

# Brilio USSD: secret sent in the "Authentication" header of every callback.
# Comma-separate two values while rotating secrets.
BRILIO_CALLBACK_SECRETS = env_list('BRILIO_CALLBACK_SECRETS')

# Safaricom Daraja (M-Pesa STK push)
MPESA_ENV = os.environ.get('MPESA_ENV', 'sandbox')  # sandbox | production
MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY', '')
MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', '')
MPESA_SHORTCODE = os.environ.get('MPESA_SHORTCODE', '174379')
MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY', '')
# CustomerPayBillOnline for paybills, CustomerBuyGoodsOnline for tills.
MPESA_TRANSACTION_TYPE = os.environ.get('MPESA_TRANSACTION_TYPE', 'CustomerPayBillOnline')
# For a till, PartyB is the till number; for a paybill it equals the shortcode.
MPESA_PARTY_B = os.environ.get('MPESA_PARTY_B', MPESA_SHORTCODE)

# Statum airtime disbursement
STATUM_CONSUMER_KEY = os.environ.get('STATUM_CONSUMER_KEY', '')
STATUM_CONSUMER_SECRET = os.environ.get('STATUM_CONSUMER_SECRET', '')
STATUM_AIRTIME_URL = os.environ.get('STATUM_AIRTIME_URL', 'https://api.statum.co.ke/api/v2/airtime')

AIRTIME_MIN_AMOUNT = int(os.environ.get('AIRTIME_MIN_AMOUNT', '10'))
AIRTIME_MAX_AMOUNT = int(os.environ.get('AIRTIME_MAX_AMOUNT', '10000'))

# Seconds to wait after the USSD session closes before sending the STK push,
# since a phone can't show the M-Pesa prompt over an open USSD screen.
STK_PUSH_DELAY_SECONDS = float(os.environ.get('STK_PUSH_DELAY_SECONDS', '3'))

# Run outbound API calls synchronously instead of in a thread (used by tests).
BACKGROUND_TASKS_INLINE = env_bool('BACKGROUND_TASKS_INLINE', False)
