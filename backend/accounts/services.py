import hashlib
import hmac
import ipaddress
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string

from config.http import Problem
from .models import EmailIdentity, EmailChallenge, RateLimitBucket, User

logger = logging.getLogger(__name__)

def normalize_email(value):
    if not isinstance(value, str):
        raise Problem('invalid_email', '请输入有效邮箱。')
    value = value.strip().lower()
    try:
        validate_email(value)
    except ValidationError:
        raise Problem('invalid_email', '请输入有效邮箱。')
    return value

def digest(email, code, purpose='login'):
    payload = f'{email}:{code}' if purpose == 'login' else f'{purpose}:{email}:{code}'
    return hmac.new(settings.OTP_HMAC_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()

def rate(key, period, maximum, now):
    window = int(now.timestamp()) // period
    bucket, _ = RateLimitBucket.objects.get_or_create(key=key, window=window,
        defaults={'expires_at': now + timedelta(seconds=period * 2)})
    bucket = RateLimitBucket.objects.select_for_update().get(pk=bucket.pk)
    if bucket.count >= maximum:
        raise Problem('rate_limited', '请求较多，请稍后再试。', 429)
    bucket.count += 1
    bucket.save(update_fields=['count'])

def send_code(email, address, purpose='login'):
    if purpose not in {'login', 'register'}:
        raise ValueError('Unsupported verification purpose')
    now = timezone.now()
    subnet = str(ipaddress.ip_network(f'{address}/{64 if ":" in address else 24}', strict=False))
    identity, _ = EmailIdentity.objects.get_or_create(email=email)
    code = f'{secrets.randbelow(1000000):06d}'
    with transaction.atomic():
        identity = EmailIdentity.objects.select_for_update().get(pk=identity.pk)
        recent = EmailChallenge.objects.filter(identity=identity, created_at__gt=now - timedelta(seconds=60)).exists()
        if recent:
            raise Problem('rate_limited', '请等待一分钟后再发送。', 429)
        for key, period, limit in [('email:' + email, 3600, 5), ('ip:' + address, 3600, 30),
                                   ('subnet:' + subnet, 3600, settings.OTP_SUBNET_LIMIT),
                                   ('global-hour', 3600, 200), ('global-day', 86400, 1000)]:
            rate(key, period, limit, now)
        EmailChallenge.objects.filter(identity=identity, purpose=purpose, consumed_at__isnull=True).update(consumed_at=now)
        challenge = EmailChallenge.objects.create(identity=identity, purpose=purpose, digest=digest(email, code, purpose), expires_at=now + timedelta(minutes=10))
        blocked = User.objects.filter(email=email).filter(is_staff=True).exists() or User.objects.filter(email=email, is_active=False).exists()
    if blocked:
        EmailChallenge.objects.filter(pk=challenge.pk).update(consumed_at=now)
        return
    try:
        label = '注册' if purpose == 'register' else '登录'
        message = render_to_string('account_code_email.txt', {
            'label': label, 'code': code, 'email': email,
            'site_url': settings.SITE_URL + '/tongjian/',
        })
        delivered = send_mail(f'通鉴年鉴{label}验证码', message,
                              settings.DEFAULT_FROM_EMAIL, [email])
        if delivered != 1:
            raise RuntimeError('mail not delivered')
    except Exception:
        EmailChallenge.objects.filter(pk=challenge.pk).update(consumed_at=timezone.now())
        logger.error('email_delivery_failed challenge_id=%s', challenge.pk)
        raise Problem('email_unavailable', '发信服务暂不可用，请稍后重试。', 503)
    EmailChallenge.objects.filter(pk=challenge.pk).update(sent=True)

def consume_code(email, code, now, purpose):
    # Caller owns the transaction. Lock the mailbox to serialize resend/consumption.
    identity = EmailIdentity.objects.select_for_update().filter(email=email).first()
    challenge = (EmailChallenge.objects.filter(identity=identity, purpose=purpose, consumed_at__isnull=True,
                 sent=True, expires_at__gt=now).order_by('-id').first()) if identity else None
    if not challenge:
        return False
    challenge.attempts += 1
    valid = isinstance(code, str) and len(code) == 6 and hmac.compare_digest(challenge.digest, digest(email, code, purpose))
    if valid or challenge.attempts >= 5:
        challenge.consumed_at = now
    challenge.save(update_fields=['attempts', 'consumed_at'])
    return valid


def verify_code(email, code, address):
    now = timezone.now()
    user = None
    with transaction.atomic():
        rate('verify:' + address, 600, 40, now)
        if consume_code(email, code, now, 'login'):
            user, _ = User.objects.get_or_create(email=email)
            if not user.password:
                user.set_unusable_password()
                user.save(update_fields=['password'])
            if not user.is_active or user.is_staff or user.is_superuser:
                user = None
    if not user:
        # Raise after committing the failed-attempt count and rate limit.
        raise Problem('invalid_code', '验证码不正确或已失效。')
    return user


def register_with_code(user, code, address):
    now = timezone.now()
    error = None
    with transaction.atomic():
        rate('register-verify:' + address, 600, 40, now)
        if not consume_code(user.email, code, now, 'register'):
            error = Problem('invalid_code', '验证码不正确或已失效，请检查邮箱或重新发送。')
        elif User.objects.filter(email__iexact=user.email).exists():
            error = Problem('email_exists', '该邮箱已注册，请直接登录。')
        else:
            user.email_verified_at = now
            user.save()
    if error:
        raise error
    return user
