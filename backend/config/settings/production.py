from django.core.exceptions import ImproperlyConfigured
from config.readiness import missing_gates
from .base import *

if len(SECRET_KEY) < 40 or SECRET_KEY.startswith(('unsafe-', 'replace-')) or len(OTP_HMAC_KEY) < 32 or OTP_HMAC_KEY.startswith(('unsafe-', 'replace-')):
    raise ImproperlyConfigured('Production requires independent strong Django and OTP secrets')
if PAYMENT_PROVIDER == 'fake' or not EMAIL_HOST or DEFAULT_FROM_EMAIL.endswith('.invalid'):
    raise ImproperlyConfigured('Configure production email and a real or disabled payment provider')
if PAYMENT_PROVIDER not in {'disabled', 'wechat'}:
    raise ImproperlyConfigured('This release implements WeChat Native/H5; other providers are not enabled')
if not os.getenv('ADMIN_NETWORKS'):
    raise ImproperlyConfigured('Explicit administrator networks are required')
if not SITE_URL.startswith('https://'):
    raise ImproperlyConfigured('Production SITE_URL must use HTTPS')
if SALES_ENABLED and (not LIVE_READY or PAYMENT_PROVIDER == 'disabled'):
    raise ImproperlyConfigured('Live sales require verified launch gates and a configured provider')
if SALES_ENABLED and missing_gates(LAUNCH_GATES_FILE):
    raise ImproperlyConfigured('Live sales require completed, attributed launch evidence')
if LIVE_READY and (not TERMS_FILE or not Path(TERMS_FILE).is_file()):
    raise ImproperlyConfigured('Reviewed production terms file is required')
if PAYMENT_VERIFICATION_ENABLED:
    prerequisites = {'merchant_products', 'price_and_terms', 'email_delivery'}
    if (PAYMENT_PROVIDER != 'wechat' or not PAYMENT_VERIFICATION_BUYERS or PAYMENT_VERIFICATION_PRICE_FEN < 1
            or prerequisites.intersection(missing_gates(LAUNCH_GATES_FILE)) or not TERMS_FILE or not Path(TERMS_FILE).is_file()):
        raise ImproperlyConfigured('Controlled merchant verification requires approved prerequisites, terms, price and specific buyer emails')
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# This app does not control every subdomain or authorize a domain-wide preload commitment.
# All other deployment warnings remain fatal in the service's ExecStartPre.
SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']
if flag('TRUST_HTTPS_PROXY'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
