from django.contrib.auth import login, logout, update_session_auth_hash
from django.utils.crypto import constant_time_compare
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.middleware.csrf import get_token
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import views as auth_views
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.conf import settings
from .forms import RegistrationForm, PasswordLoginForm, ReaderPasswordResetForm, RegistrationEmailForm, GraphicCaptchaForm
from . import captcha
from .models import GraphicChallenge
from .services import rate, register_with_code
from config.http import Problem
from django.views.decorators.http import require_GET, require_POST
from config.http import endpoint, body, safe_next
from config.middleware import client_ip
from .services import normalize_email, send_code, verify_code
from commerce.services import verification_allowed

@require_GET
def session(request):
    return JsonResponse({'authenticated': request.user.is_authenticated,
        'email': request.user.email if request.user.is_authenticated else None,
        'verification_allowed': verification_allowed(request.user),
        'csrf_token': get_token(request)})

@require_POST
@endpoint
def email_code(request):
    if not settings.LEGACY_EMAIL_LOGIN_ENABLED:
        raise Problem('not_found', '不存在此接口。', 404)
    send_code(normalize_email(body(request).get('email')), client_ip(request))
    return JsonResponse({'message': '如果可以接收验证码，请检查邮箱。'})

@require_POST
@endpoint
def verify(request):
    if not settings.LEGACY_EMAIL_LOGIN_ENABLED:
        raise Problem('not_found', '不存在此接口。', 404)
    data = body(request)
    user = verify_code(normalize_email(data.get('email')), data.get('code'), client_ip(request))
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'next': safe_next(data.get('next')), 'csrf_token': get_token(request)})

@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({'next': '/tongjian/research.html'})


@login_required
@never_cache
@require_GET
def account_page(request):
    return render(request, 'account.html')


@never_cache
@require_POST
def logout_page(request):
    logout(request)
    return redirect('/tongjian/research.html')


@login_required
@never_cache
@sensitive_post_parameters('old_password', 'new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def password_change(request):
    if request.user.is_staff or request.user.is_superuser:
        raise PermissionDenied('管理员请使用管理后台修改密码。')
    form = PasswordChangeForm(request.user, request.POST if request.method == 'POST' else None)
    status = 200
    if request.method == 'POST':
        try:
            auth_limit(request, 'password-change', request.user.email)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                return redirect('password_change_done')
        except Problem as exc:
            form.add_error(None, exc.message)
            status = exc.status
    return render(request, 'password_change.html', {'form': form}, status=status)


@login_required
@never_cache
@require_GET
def password_change_done(request):
    return render(request, 'password_change_done.html')

def auth_limit(request, action, email=''):
    # Commit each attempt before authentication/validation, including failures.
    with transaction.atomic():
        rate(action + ':ip:' + client_ip(request), 600, 20, timezone.now())
        if email:
            import hashlib
            key = hashlib.sha256(email.strip().lower().encode()).hexdigest()
            rate(action + ':email:' + key, 600, 10, timezone.now())


@sensitive_post_parameters('password', 'password1', 'password2', 'code')
@never_cache
@require_http_methods(['GET', 'POST'])
def login_page(request):
    return password_page(request, registering=False)


def render_registration(request, form, destination, status=200, **extra):
    email = form.data.get('email', '') if form.is_bound else form.initial.get('email', '')
    context = {'form': form, 'next': destination,
        'test_mail': settings.EMAIL_BACKEND.endswith('filebased.EmailBackend'),
        'captcha_verified': captcha.verified(request, email), **extra}
    if not context['captcha_verified']:
        try:
            challenge = captcha.issue(request, client_ip(request), request.POST.get('captcha_id'))
            context['captcha_image_url'] = reverse('graphic_captcha_image', args=[challenge.pk])
            context['captcha_form'] = GraphicCaptchaForm(initial={'captcha_id': challenge.pk})
        except Problem as exc:
            context['captcha_error'] = exc.message
            status = exc.status
    return render(request, 'register.html', context, status=status)


@never_cache
@require_GET
def graphic_captcha_image(request, challenge_id):
    challenge = GraphicChallenge.objects.filter(pk=challenge_id, consumed_at__isnull=True,
                                                expires_at__gt=timezone.now()).first()
    if (not challenge or not request.session.session_key
            or not constant_time_compare(challenge.session_digest, captcha.digest('session', request.session.session_key))):
        raise Http404
    return HttpResponse(bytes(challenge.image), content_type='image/png')


@never_cache
@require_POST
@endpoint
def graphic_captcha_refresh(request):
    captcha.clear(request)
    challenge = captcha.issue(request, client_ip(request), request.POST.get('captcha_id'))
    return JsonResponse({'id': str(challenge.pk),
        'image_url': reverse('graphic_captcha_image', args=[challenge.pk])})


@sensitive_post_parameters('password', 'password1', 'password2', 'code', 'captcha')
@never_cache
@require_http_methods(['GET', 'POST'])
def register_page(request):
    destination = safe_next(request.POST.get('next') or reverse('account'))
    if request.method == 'POST' and request.POST.get('action') == 'refresh_captcha' and not request.user.is_authenticated:
        captcha.clear(request)
        return render_registration(request, RegistrationForm(initial={
            'email': request.POST.get('email', ''), 'code': request.POST.get('code', ''),
        }), destination)
    if request.method == 'POST' and request.POST.get('action') == 'send_code' and not request.user.is_authenticated:
        captcha.clear(request)
        email_form = RegistrationEmailForm(request.POST)
        graphic_form = GraphicCaptchaForm(request.POST)
        sent = False
        status = 200
        email_valid, graphic_valid = email_form.is_valid(), graphic_form.is_valid()
        if email_valid and graphic_valid:
            try:
                if not captcha.consume(request, graphic_form.cleaned_data['captcha_id'],
                                       graphic_form.cleaned_data['captcha'], client_ip(request)):
                    graphic_form.add_error('captcha', '图形验证码不正确或已过期，请重试。')
                else:
                    send_code(email_form.cleaned_data['email'], client_ip(request), purpose='register')
                    captcha.remember(request, email_form.cleaned_data['email'])
                    sent = True
            except Problem as exc:
                email_form.add_error(None, exc.message)
                status = exc.status
        return render_registration(request,
            RegistrationForm(initial={'email': request.POST.get('email', '')}), destination,
            status=status, send_errors=[*email_form.errors.values(), *graphic_form.errors.values()], code_sent=sent)
    return password_page(request, registering=True)


def password_page(request, registering):
    requested_next = request.POST.get('next') if request.method == 'POST' else request.GET.get('next')
    destination = safe_next(requested_next or reverse('account'))
    if request.user.is_authenticated:
        return redirect(destination)
    data = request.POST if request.method == 'POST' else None
    if registering:
        proof = request.session.get(captcha.PROOF_KEY, {})
        initial = {'email': proof.get('email', '')} if isinstance(proof, dict) else {}
        form = RegistrationForm(data, initial=initial)
    else:
        form = PasswordLoginForm(request, data=data)
    status = 200
    if request.method == 'POST':
        try:
            auth_limit(request, 'register' if registering else 'password-login', request.POST.get('email' if registering else 'username', ''))
            if form.is_valid():
                if registering:
                    if not captcha.verified(request, form.cleaned_data['email']):
                        form.add_error(None, '请先完成图形验证码并发送邮箱验证码；修改邮箱后需要重新验证。')
                    else:
                        try:
                            user = register_with_code(form.save(commit=False), form.cleaned_data['code'], client_ip(request))
                        except IntegrityError:
                            form.add_error('email', '该邮箱已注册，请直接登录。')
                        else:
                            captcha.clear(request)
                            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                            return redirect(destination)
                else:
                    login(request, form.get_user())
                    return redirect(destination)
        except Problem as exc:
            form.add_error('code' if registering and exc.code == 'invalid_code' else None, exc.message)
            status = 200 if exc.code == 'invalid_code' else exc.status
    if registering:
        return render_registration(request, form, destination, status=status)
    return render(request, 'login.html', {'form': form, 'next': destination}, status=status)


@method_decorator(sensitive_post_parameters('email'), name='dispatch')
class ReaderPasswordResetView(auth_views.PasswordResetView):
    form_class = ReaderPasswordResetForm
    template_name = 'password_reset.html'
    email_template_name = 'password_reset_email.txt'
    subject_template_name = 'password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        try:
            auth_limit(self.request, 'password-reset', form.cleaned_data['email'])
            # Build recovery URLs from the configured origin, never the request Host.
            from urllib.parse import urlsplit
            origin = urlsplit(settings.SITE_URL)
            form.save(use_https=origin.scheme == 'https', domain_override=origin.netloc,
                      from_email=settings.DEFAULT_FROM_EMAIL,
                      email_template_name=self.email_template_name,
                      subject_template_name=self.subject_template_name,
                      request=self.request)
        except Problem as exc:
            form.add_error(None, exc.message)
            return self.render_to_response(self.get_context_data(form=form), status=exc.status)
        except Exception:
            import logging
            logging.getLogger(__name__).error('password_reset_delivery_failed')
            form.add_error(None, '邮件发送暂不可用，请稍后再试。')
            return self.form_invalid(form)
        return redirect(self.success_url)
