import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from django.core import mail
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.utils import timezone
from config.http import Problem, safe_next
from .models import EmailChallenge, User
from .services import send_code, verify_code, normalize_email


def request_registration_code(client, email):
    """Solve a deterministic test image through the real CSRF/form flow."""
    url = '/tongjian/account/register/'
    with patch('accounts.captcha.new_code', return_value='ABCD'):
        response = client.get(url)
        if response.context['captcha_verified']:
            response = client.post(url, {'action': 'refresh_captcha', 'email': email,
                'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        identifier = response.context['captcha_form'].initial['captcha_id']
        return client.post(url, {'action': 'send_code', 'email': email,
            'captcha_id': identifier, 'captcha': 'abcd',
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value})

class LoginTests(TestCase):
    def code(self, email='reader@example.com'):
        send_code(email, '127.0.0.1')
        return re.search(r'\d{6}', mail.outbox[-1].body).group()

    def test_mail_code_single_use_and_unusable_password(self):
        code = self.code()
        user = verify_code('reader@example.com', code, '127.0.0.1')
        self.assertFalse(user.has_usable_password())
        with self.assertRaises(Problem):
            verify_code('reader@example.com', code, '127.0.0.1')
        self.assertNotEqual(EmailChallenge.objects.get().digest, code)

    def test_five_failed_attempts_commit(self):
        self.code()
        for _ in range(5):
            with self.assertRaises(Problem):
                verify_code('reader@example.com', 'xxxxxx', '127.0.0.1')
        challenge = EmailChallenge.objects.get()
        self.assertEqual(challenge.attempts, 5)
        self.assertIsNotNone(challenge.consumed_at)

    def test_expired(self):
        code = self.code()
        EmailChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(Problem):
            verify_code('reader@example.com', code, '127.0.0.1')

    def test_resend_invalidates_previous_code(self):
        first = self.code()
        EmailChallenge.objects.update(created_at=timezone.now() - timedelta(seconds=61))
        with patch('accounts.services.secrets.randbelow', return_value=123456):
            second = self.code()
        if first != second:
            with self.assertRaises(Problem):
                verify_code('reader@example.com', first, '127.0.0.1')
        self.assertEqual(verify_code('reader@example.com', second, '127.0.0.1').email, 'reader@example.com')

    def test_resend_throttled(self):
        self.code()
        with self.assertRaises(Problem) as context:
            self.code()
        self.assertEqual(context.exception.status, 429)

    def test_staff_cannot_login_via_email_code(self):
        User.objects.create_superuser('owner@example.com', 'admin-strong-password')
        send_code('owner@example.com', '127.0.0.1')
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNotNone(EmailChallenge.objects.get().consumed_at)

    def test_email_delivery_failure_invalidates_code(self):
        with patch('accounts.services.send_mail', side_effect=RuntimeError('SMTP failure')):
            with self.assertRaises(Problem):
                send_code('reader@example.com', '127.0.0.1')
        self.assertIsNotNone(EmailChallenge.objects.get().consumed_at)

    def test_csrf_required_for_login_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/tongjian/api/v1/auth/email-code/', {'email': 'reader@example.com'}).status_code, 403)
        token = client.get('/tongjian/api/v1/session/').json()['csrf_token']
        response = client.post('/tongjian/api/v1/auth/email-code/', data='{"email":"reader@example.com"}',
                               content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        code = re.search(r'\d{6}', mail.outbox[-1].body).group()
        response = client.post('/tongjian/api/v1/auth/verify/', data={'email': 'reader@example.com', 'code': code, 'next': '//evil.example/'},
                               content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.json()['next'], '/tongjian/account/purchases/')
        self.assertEqual(client.post('/tongjian/api/v1/auth/logout/', {}).status_code, 403)
        token = client.get('/tongjian/api/v1/session/').json()['csrf_token']
        self.assertEqual(client.post('/tongjian/api/v1/auth/logout/', data='{}', content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertFalse(client.get('/tongjian/api/v1/session/').json()['authenticated'])

    def test_normalization_and_redirects(self):
        self.assertEqual(normalize_email(' Reader+one@Example.COM '), 'reader+one@example.com')
        for value in ['https://evil.example/', '//evil.example/', '/tongjian/\\evil', '/elsewhere', '/tongjian/\n']:
            self.assertEqual(safe_next(value), '/tongjian/account/purchases/')
        self.assertEqual(safe_next('/tongjian/truth.html#wugu'), '/tongjian/truth.html#wugu')

class ConcurrentLoginTests(TransactionTestCase):
    def test_parallel_code_consumption(self):
        send_code('reader@example.com', '127.0.0.1')
        code = re.search(r'\d{6}', mail.outbox[-1].body).group()
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            barrier.wait()
            try:
                verify_code('reader@example.com', code, '127.0.0.1')
                return True
            except Problem:
                return False
            finally:
                close_old_connections()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(sorted(results), [False, True])

class PasswordAccountTests(TestCase):
    password = 'Cedar-Cloud-2026!Book'
    login_url = '/tongjian/account/login/'
    register_url = '/tongjian/account/register/'

    def register(self, **overrides):
        data = {'email': ' Reader@Example.com ', 'password1': self.password,
                'password2': self.password, 'next': '/tongjian/truth.html#wugu'}
        data.update(overrides)
        return self.client.post(self.register_url, data)

    def test_register_password_hash_session_and_destination(self):
        request_registration_code(self.client, 'reader@example.com')
        code = re.search(r'\d{6}', mail.outbox[-1].body).group()
        response = self.register(code=code)
        self.assertRedirects(response, '/tongjian/truth.html#wugu', fetch_redirect_response=False)
        user = User.objects.get(email='reader@example.com')
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(self.client.session['_auth_user_id'], str(user.pk))

    def test_duplicate_registration_never_changes_existing_password(self):
        user = User.objects.create_user('reader@example.com', self.password)
        response = self.register(password1='Another-Strong-Password!', password2='Another-Strong-Password!')
        self.assertContains(response, '该邮箱已注册')
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_validation_mismatch_weak_password_invalid_email(self):
        for data in [{'password2': 'different'}, {'password1': '123', 'password2': '123'}, {'email': 'bad'}]:
            self.assertEqual(self.register(**data).status_code, 200)
            self.assertEqual(User.objects.count(), 0)

    def test_relaxed_password_rule_is_shared_by_registration_change_and_reset(self):
        from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
        from .forms import RegistrationForm
        user = User.objects.create_user('account@example.com', self.password)
        for password, valid in [('123456', True), ('12345', False)]:
            forms = {
                'register': RegistrationForm({'email': '123456@example.com', 'code': '123456',
                    'password1': password, 'password2': password}),
                'change': PasswordChangeForm(user, {'old_password': self.password,
                    'new_password1': password, 'new_password2': password}),
                'reset': SetPasswordForm(user, {'new_password1': password, 'new_password2': password}),
            }
            for name, form in forms.items():
                with self.subTest(flow=name, length=len(password)):
                    self.assertEqual(form.is_valid(), valid, form.errors.as_text())

    def test_login_wrong_password_never_creates_user(self):
        User.objects.create_user('reader@example.com', self.password)
        response = self.client.post(self.login_url, {'username': 'reader@example.com', 'password': 'wrong'})
        self.assertContains(response, '邮箱或密码不正确')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.post(self.login_url, {'username': 'missing@example.com', 'password': self.password})
        self.assertEqual(User.objects.count(), 1)

    def test_password_login_normalizes_email_rotates_session_and_rejects_external_next(self):
        user = User.objects.create_user('reader@example.com', self.password)
        session = self.client.session
        session['anonymous_marker'] = True
        session.save()
        old_key = session.session_key
        response = self.client.post(self.login_url, {'username': 'READER@EXAMPLE.COM',
            'password': self.password, 'next': '//evil.example/'})
        self.assertRedirects(response, '/tongjian/account/purchases/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['_auth_user_id'], str(user.pk))
        self.assertNotEqual(old_key, self.client.session.session_key)

    def test_inactive_and_staff_cannot_use_reader_password_login(self):
        for email, flags in [('inactive@example.com', {'is_active': False}), ('staff@example.com', {'is_staff': True})]:
            User.objects.create_user(email, self.password, **flags)
            self.client.post(self.login_url, {'username': email, 'password': self.password})
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_native_forms_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for url in [self.register_url, self.login_url, '/tongjian/account/password-reset/']:
            self.assertEqual(client.post(url, {}).status_code, 403)
        response = client.get(self.register_url)
        token = client.cookies['csrftoken'].value
        request_registration_code(client, 'csrf@example.com')
        code = re.search(r'\d{6}', mail.outbox[-1].body).group()
        response = client.post(self.register_url, {'email': 'csrf@example.com', 'code': code, 'password1': self.password,
            'password2': self.password, 'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 302)

    def test_failed_login_and_registration_limits(self):
        for _ in range(10):
            self.client.post(self.login_url, {'username': 'missing@example.com', 'password': 'wrong'})
        self.assertEqual(self.client.post(self.login_url, {'username': 'missing@example.com', 'password': 'wrong'}).status_code, 429)
        for _ in range(10):
            self.register(password2='mismatch')
        self.assertEqual(self.register(password2='mismatch').status_code, 429)

    def reset_link(self, email):
        response = self.client.post('/tongjian/account/password-reset/', {'email': email})
        self.assertEqual(response.status_code, 302)
        return re.search(r'https?://[^\s]+/tongjian/account/reset/[^\s]+', mail.outbox[-1].body).group()

    def test_reset_legacy_reader_preserves_user_and_invalidates_token(self):
        from urllib.parse import urlsplit
        user = User.objects.create_user('legacy@example.com')
        original_id = user.pk
        self.assertFalse(user.has_usable_password())
        link = urlsplit(self.reset_link(user.email)).path
        self.assertEqual(self.client.get(link).status_code, 302)
        response = self.client.post(self.client.get(link).url, {'new_password1': self.password, 'new_password2': self.password})
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.pk, original_id)
        self.assertTrue(user.check_password(self.password))
        self.assertContains(Client().get(link, follow=True), '链接已失效')
        self.client.post(self.login_url, {'username': user.email, 'password': self.password})
        self.assertEqual(self.client.session['_auth_user_id'], str(original_id))

    def test_reset_expired_token_and_unknown_or_staff_emails(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        from django.test import override_settings
        user = User.objects.create_user('reader@example.com', self.password)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertContains(self.client.get(f'/tongjian/account/reset/{uid}/{token}/', follow=True), '链接已失效')
        User.objects.create_superuser('owner@example.com', self.password)
        for email in ['owner@example.com', 'missing@example.com']:
            response = self.client.post('/tongjian/account/password-reset/', {'email': email})
            self.assertRedirects(response, '/tongjian/account/password-reset/sent/')
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_password_logs_out_old_sessions_and_keeps_order_owner(self):
        from urllib.parse import urlsplit
        user = User.objects.create_user('reader@example.com', self.password)
        old = Client()
        old.force_login(user)
        link = urlsplit(self.reset_link(user.email)).path
        response = self.client.get(link)
        self.client.post(response.url, {'new_password1': 'New-' + self.password, 'new_password2': 'New-' + self.password})
        self.assertFalse(old.get('/tongjian/api/v1/session/').json()['authenticated'])
        self.assertEqual(User.objects.get(email=user.email).pk, user.pk)


class VerifiedRegistrationTests(TestCase):
    url = '/tongjian/account/register/'
    password = 'Valley-River-2026!Safe'

    def send(self, email='new@example.com'):
        response = request_registration_code(self.client, email)
        self.assertContains(response, '验证码已发送')
        return re.search(r'\d{6}', mail.outbox[-1].body).group()

    def register(self, code, email='new@example.com', **extra):
        return self.client.post(self.url, {'email': email, 'code': code, 'password1': self.password,
            'password2': self.password, 'action': 'register', **extra})

    def test_request_never_creates_user_and_missing_code_cannot_register(self):
        self.send()
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(self.register('').status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_wrong_code_counts_attempts_and_cannot_register(self):
        with patch('accounts.services.secrets.randbelow', return_value=123456):
            self.send()
        for _ in range(5):
            self.assertContains(self.register('xxxxxx'), '6 位数字')
        # Shape errors do not touch the challenge; six-digit guesses do.
        for _ in range(5):
            self.assertContains(self.register('999999'), '验证码不正确或已失效')
        challenge = EmailChallenge.objects.get()
        self.assertEqual(challenge.attempts, 5)
        self.assertIsNotNone(challenge.consumed_at)
        self.assertEqual(User.objects.count(), 0)

    def test_email_binding_and_wrong_purpose(self):
        code = self.send()
        self.assertContains(self.register(code, email='other@example.com'), '修改邮箱后需要重新验证')
        with self.assertRaises(Problem):
            verify_code('new@example.com', code, '127.0.0.1')
        self.assertEqual(self.register(code).status_code, 302)
        self.assertIsNotNone(User.objects.get().email_verified_at)
        self.assertEqual(User.objects.count(), 1)

    def test_login_code_cannot_be_used_for_registration(self):
        send_code('new@example.com', '127.0.0.1')
        code = re.search(r'\d{6}', mail.outbox[-1].body).group()
        # Isolate OTP purpose checking after a successful graphical proof.
        from .captcha import PROOF_KEY
        session = self.client.session
        session[PROOF_KEY] = {'email': 'new@example.com', 'expires': timezone.now().timestamp() + 600}
        session.save()
        self.assertContains(self.register(code), '验证码不正确或已失效')
        self.assertEqual(User.objects.count(), 0)

    def test_expiry_and_resend_invalidate_old_code(self):
        first = self.send()
        EmailChallenge.objects.update(created_at=timezone.now()-timedelta(seconds=61))
        with patch('accounts.services.secrets.randbelow', return_value=123456 if first != '123456' else 654321):
            second = self.send()
        self.assertContains(self.register(first), '验证码不正确或已失效')
        EmailChallenge.objects.filter(consumed_at__isnull=True).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertContains(self.register(second), '验证码不正确或已失效')
        self.assertEqual(User.objects.count(), 0)

    def test_valid_code_not_consumed_on_password_error(self):
        code = self.send()
        self.assertEqual(self.register(code, password2='not-matching').status_code, 200)
        self.assertIsNone(EmailChallenge.objects.get().consumed_at)
        self.assertEqual(self.register(code).status_code, 302)
        self.client.logout()
        # A second registration cannot overwrite the verified account.
        self.assertContains(self.register(code), '该邮箱已注册')
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(User.objects.get().check_password(self.password))

    def test_send_throttling_and_failure_feedback(self):
        self.send()
        self.assertEqual(request_registration_code(self.client, 'new@example.com').status_code, 429)
        with patch('accounts.services.send_mail', side_effect=RuntimeError('SMTP failed')):
            response = request_registration_code(self.client, 'failed@example.com')
        self.assertContains(response, '发信服务暂不可用', status_code=503)
        self.assertIsNotNone(EmailChallenge.objects.get(identity__email='failed@example.com').consumed_at)
        self.assertEqual(User.objects.count(), 0)

    def test_registered_email_does_not_send_code(self):
        User.objects.create_user('existing@example.com', self.password)
        self.assertContains(request_registration_code(self.client, 'EXISTING@example.com'), '该邮箱已注册')
        self.assertEqual(len(mail.outbox), 0)


class ConcurrentRegistrationTests(TransactionTestCase):
    def test_one_code_only_creates_one_verified_account(self):
        from .services import register_with_code
        send_code('new@example.com', '127.0.0.1', purpose='register')
        code = re.search(r'\d{6}', mail.outbox[-1].body).group()
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            user = User(email='new@example.com')
            user.set_password('Valley-River-2026!Safe')
            barrier.wait()
            try:
                register_with_code(user, code, '127.0.0.1')
                return True
            except Problem:
                return False
            finally:
                close_old_connections()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(User.objects.count(), 1)
        self.assertIsNotNone(User.objects.get().email_verified_at)


class AccountManagementTests(TestCase):
    password = 'Reader-Safety-2026!Book'

    def setUp(self):
        self.user = User.objects.create_user('account@example.com', self.password,
                                             email_verified_at=timezone.now())

    def test_account_requires_login_and_contains_native_security_links(self):
        self.assertEqual(self.client.get('/tongjian/account/').status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get('/tongjian/account/')
        self.assertContains(response, 'account@example.com')
        self.assertContains(response, '已验证')
        self.assertContains(response, '/tongjian/account/password-change/')
        self.assertContains(response, 'action="/tongjian/account/logout/"')
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_login_defaults_to_account_and_preserves_reading_destination(self):
        response = self.client.post('/tongjian/account/login/', {
            'username': self.user.email, 'password': self.password,
        })
        self.assertRedirects(response, '/tongjian/account/', fetch_redirect_response=False)
        self.client.logout()
        destination = '/tongjian/reader.html#volume-1-year-403-para-1'
        response = self.client.post('/tongjian/account/login/', {
            'username': self.user.email, 'password': self.password, 'next': destination,
        })
        self.assertRedirects(response, destination, fetch_redirect_response=False)

    def test_native_logout_is_post_only_and_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.get('/tongjian/account/logout/').status_code, 405)
        self.assertTrue(client.get('/tongjian/api/v1/session/').json()['authenticated'])
        self.assertEqual(client.post('/tongjian/account/logout/').status_code, 403)
        client.get('/tongjian/account/')
        response = client.post('/tongjian/account/logout/', {
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        })
        self.assertRedirects(response, '/tongjian/research.html', fetch_redirect_response=False)
        self.assertFalse(client.get('/tongjian/api/v1/session/').json()['authenticated'])

    def test_password_change_rotates_current_session_and_revokes_other_devices(self):
        self.client.force_login(self.user)
        other = Client()
        other.force_login(self.user)
        old_key = self.client.session.session_key
        new_password = 'New-' + self.password
        response = self.client.post('/tongjian/account/password-change/', {
            'old_password': self.password,
            'new_password1': new_password, 'new_password2': new_password,
        })
        self.assertRedirects(response, '/tongjian/account/password-change/done/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertTrue(self.client.get('/tongjian/api/v1/session/').json()['authenticated'])
        self.assertNotEqual(old_key, self.client.session.session_key)
        self.assertFalse(other.get('/tongjian/api/v1/session/').json()['authenticated'])

    def test_password_change_requires_current_password_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/tongjian/account/password-change/', {}).status_code, 403)
        client.get('/tongjian/account/password-change/')
        response = client.post('/tongjian/account/password-change/', {
            'old_password': 'wrong', 'new_password1': 'New-' + self.password,
            'new_password2': 'New-' + self.password,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('old_password', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_password_change_is_rate_limited(self):
        self.client.force_login(self.user)
        for _ in range(10):
            self.client.post('/tongjian/account/password-change/', {'old_password': 'wrong'})
        self.assertEqual(self.client.post('/tongjian/account/password-change/', {}).status_code, 429)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_admin_cannot_bypass_admin_password_route(self):
        staff = User.objects.create_superuser('admin@example.com', self.password)
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/tongjian/account/password-change/').status_code, 403)

    @override_settings(LEGACY_EMAIL_LOGIN_ENABLED=False)
    def test_disabled_legacy_routes_do_not_send_or_create_accounts(self):
        for route in ['email-code', 'verify']:
            response = self.client.post('/tongjian/api/v1/auth/' + route + '/',
                data={'email': 'unregistered@example.com', 'code': '123456'}, content_type='application/json')
            self.assertEqual(response.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(User.objects.filter(email='unregistered@example.com').exists())
        self.assertFalse(EmailChallenge.objects.exists())

    def test_expired_csrf_displays_html_for_forms_and_json_for_api(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/tongjian/account/login/', {})
        self.assertContains(response, '页面验证已失效', status_code=403)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        response = client.post('/tongjian/api/v1/auth/logout/', data={}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error']['code'], 'csrf_failed')


class AccountMailBackendTests(TestCase):
    @override_settings(EMAIL_MESSAGE_ID_DOMAIN='deewins.top')
    def test_smtp_message_ids_use_public_domain_and_preserve_explicit_headers(self):
        from config.mail import EmailBackend
        first = mail.EmailMessage('Registration', 'Test', 'linqp@deewins.top', ['reader@example.com'])
        second = mail.EmailMessage('Recovery', 'Test', 'linqp@deewins.top', ['reader@example.com'],
                                   headers={'message-id': '<custom@deewins.top>'})
        with patch('config.mail.SMTPBackend.send_messages', return_value=2) as send:
            self.assertEqual(EmailBackend().send_messages([first, second]), 2)
        self.assertEqual(send.call_count, 1)
        self.assertTrue(first.message()['Message-ID'].endswith('@deewins.top>'))
        self.assertEqual(second.message().get_all('Message-ID'), ['<custom@deewins.top>'])

    @override_settings(EMAIL_MESSAGE_ID_DOMAIN='invalid\nexample.com')
    def test_invalid_message_id_domain_fails_before_smtp(self):
        from config.mail import EmailBackend
        from django.core.exceptions import ValidationError
        message = mail.EmailMessage('Test', 'Test', 'linqp@deewins.top', ['reader@example.com'])
        with patch('config.mail.SMTPBackend.send_messages') as send:
            with self.assertRaises(ValidationError):
                EmailBackend().send_messages([message])
            send.assert_not_called()
