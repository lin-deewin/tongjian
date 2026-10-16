import ipaddress
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / 'backend/.env')

def flag(key, default=False):
    return os.getenv(key, str(default)).lower() in {'true', '1', 'yes'}

def items(key, default=''):
    return [s.strip() for s in os.getenv(key, default).split(',') if s.strip()]

def database(url):
    value = urlparse(url)
    if value.scheme not in {'postgres', 'postgresql'}:
        raise ValueError('Only PostgreSQL is supported')
    return {'ENGINE': 'django.db.backends.postgresql', 'NAME': value.path.lstrip('/'),
            'USER': unquote(value.username or ''), 'PASSWORD': unquote(value.password or ''),
            'HOST': value.hostname or '127.0.0.1', 'PORT': value.port or 5432,
            'CONN_MAX_AGE': 0, 'OPTIONS': {'connect_timeout': 5}}

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'unsafe-local-development-secret-not-for-production')
OTP_HMAC_KEY = os.getenv('OTP_HMAC_KEY', 'unsafe-local-development-otp-key')
DEBUG = False
ALLOWED_HOSTS = items('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver')
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
                  'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
                  'accounts', 'commerce', 'payments']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'config.middleware.RequestMiddleware',
              'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
              'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [ROOT / 'backend/templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request',
                         'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': database(os.getenv('DATABASE_URL',
    'postgresql://tongjian:local-development-only@127.0.0.1:55432/tongjian_commerce'))}
AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
]
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/admin-static/'
STATIC_ROOT = Path(os.getenv('STATIC_ROOT') or ROOT / 'tmp/commerce-static')
CONTENT_ROOT = Path(os.getenv('CONTENT_ROOT') or ROOT / 'private-content').resolve()
LAUNCH_GATES_FILE = os.getenv('LAUNCH_GATES_FILE', '')
TERMS_FILE = os.getenv('TERMS_FILE', '')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8010').rstrip('/')
SESSION_COOKIE_NAME = 'tongjian_session'
SESSION_COOKIE_PATH = CSRF_COOKIE_PATH = '/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
CSRF_TRUSTED_ORIGINS = items('CSRF_TRUSTED_ORIGINS')
CSRF_FAILURE_VIEW = 'config.http.csrf_failure'
LOGIN_URL = '/account/login/'
LOGIN_REDIRECT_URL = '/account/'
X_FRAME_OPTIONS = 'DENY'
EMAIL_BACKEND = 'config.mail.EmailBackend'
EMAIL_MESSAGE_ID_DOMAIN = os.getenv('EMAIL_MESSAGE_ID_DOMAIN', 'deewins.top')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = flag('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = flag('EMAIL_USE_SSL')
EMAIL_TIMEOUT = 8
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.invalid')
# The reader UI uses verified registration and password login. Old OTP routes
# are available only for an explicitly enabled compatibility deployment.
LEGACY_EMAIL_LOGIN_ENABLED = flag('LEGACY_EMAIL_LOGIN_ENABLED')
PAYMENT_PROVIDER = os.getenv('PAYMENT_PROVIDER', 'disabled')
PAYMENT_SCENES = items('PAYMENT_SCENES', 'native,h5')
SALES_ENABLED = flag('SALES_ENABLED')
LIVE_READY = flag('COMMERCE_LIVE_READY')
PAYMENT_VERIFICATION_ENABLED = flag('PAYMENT_VERIFICATION_ENABLED')
PAYMENT_VERIFICATION_BUYERS = items('PAYMENT_VERIFICATION_BUYERS')
PAYMENT_VERIFICATION_PRICE_FEN = int(os.getenv('PAYMENT_VERIFICATION_PRICE_FEN', '0'))
ADMIN_NETWORKS = [ipaddress.ip_network(s) for s in items('ADMIN_NETWORKS', '127.0.0.1/32,::1/128')]
TRUSTED_PROXY_NETWORKS = [ipaddress.ip_network(s) for s in items('TRUSTED_PROXY_NETWORKS')]
OTP_SUBNET_LIMIT = int(os.getenv('OTP_SUBNET_LIMIT', '100'))
FAKE_PAYMENT_SECRET = os.getenv('FAKE_PAYMENT_SECRET', 'local-fake-notification-secret')
ALLOW_FAKE = False
WECHAT = {key: os.getenv('WECHAT_' + key, '') for key in
          ['MCH_ID', 'APP_ID', 'MERCHANT_SERIAL', 'PRIVATE_KEY_FILE', 'API_V3_KEY', 'PUBLIC_KEYS_FILE']}
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'console': {'class': 'logging.StreamHandler'}},
           'root': {'handlers': ['console'], 'level': 'INFO'},
           'loggers': {'django.server': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}}}

# Password reset links expire after 24 hours and are invalidated by a password change.
PASSWORD_RESET_TIMEOUT = 86400
