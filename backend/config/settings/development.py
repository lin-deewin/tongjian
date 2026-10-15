from .base import *

DEBUG = True
ALLOW_FAKE = True
PAYMENT_PROVIDER = os.getenv('PAYMENT_PROVIDER', 'fake')
SALES_ENABLED = flag('SALES_ENABLED', True)
# Local development uses real SMTP when configured; otherwise clearly marked test mail.
EMAIL_BACKEND = ('config.mail.EmailBackend' if EMAIL_HOST else
                 'django.core.mail.backends.filebased.EmailBackend')
EMAIL_FILE_PATH = ROOT / 'backend/test-mail'
