from .base import *

DATABASES = {'default': database(os.getenv('TEST_DATABASE_URL',
    'postgresql://tongjian:local-development-only@127.0.0.1:55432/tongjian_commerce_test'))}
if not DATABASES['default']['NAME'].endswith('_test'):
    raise ValueError('TEST_DATABASE_URL must refer to an isolated *_test database')
DATABASES['default']['TEST'] = {'NAME': 'test_' + DATABASES['default']['NAME']}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
ALLOW_FAKE = True
PAYMENT_PROVIDER = 'fake'
SALES_ENABLED = True
# Exercise the optional legacy API as well as native password forms.
LEGACY_EMAIL_LOGIN_ENABLED = True
