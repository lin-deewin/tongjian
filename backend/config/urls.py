from pathlib import Path
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.urls import path, re_path
from django.views.static import serve
from accounts import views as accounts
from commerce import views as commerce
from payments import views as payments

prefix = 'tongjian/'
api = prefix + 'api/v1/'
urlpatterns = [
    path(api + 'healthz/', commerce.health),
    path(api + 'session/', accounts.session),
    path(api + 'auth/email-code/', accounts.email_code),
    path(api + 'auth/verify/', accounts.verify),
    path(api + 'auth/logout/', accounts.sign_out),
    path(api + 'products/<slug:slug>/', commerce.product_info),
    path(api + 'products/<slug:slug>/download/', commerce.download),
    path(api + 'me/purchases/', commerce.purchases),
    path(api + 'orders/', commerce.orders),
    path(api + 'orders/<uuid:order_id>/', commerce.order_info),
    path(api + 'payments/<slug:provider>/notify/', payments.notify),
    path(api + 'payments/<slug:provider>/refund-notify/', payments.notify, {'refund': True}),
    path(prefix + 'account/', accounts.account_page, name='account'),
    path(prefix + 'account/login/', accounts.login_page, name='login'),
    path(prefix + 'account/register/', accounts.register_page, name='register'),
    path(prefix + 'account/captcha/refresh/', accounts.graphic_captcha_refresh, name='graphic_captcha_refresh'),
    path(prefix + 'account/captcha/<uuid:challenge_id>/', accounts.graphic_captcha_image, name='graphic_captcha_image'),
    path(prefix + 'account/logout/', accounts.logout_page, name='logout'),
    path(prefix + 'account/password-change/', accounts.password_change, name='password_change'),
    path(prefix + 'account/password-change/done/', accounts.password_change_done, name='password_change_done'),
    path(prefix + 'account/password-reset/', accounts.ReaderPasswordResetView.as_view(), name='password_reset'),
    path(prefix + 'account/password-reset/sent/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path(prefix + 'account/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html', success_url=reverse_lazy('password_reset_complete')), name='password_reset_confirm'),
    path(prefix + 'account/password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path(prefix + 'account/purchases/', commerce.purchases_page),
    path(prefix + 'account/terms/', commerce.terms),
    path(prefix + 'article/<slug:slug>/', commerce.article),
    path(prefix + 'checkout/<uuid:order_id>/', commerce.checkout),
    path(prefix + 'checkout/<uuid:order_id>/qr/', commerce.qr),
    path(prefix + 'admin/', admin.site.urls),
]
if settings.ALLOW_FAKE:
    urlpatterns += [path(api + 'orders/<uuid:order_id>/simulate/', commerce.simulate)]
if settings.DEBUG:
    def public(request, resource='index.html'):
        resource = resource or 'index.html'
        return serve(request, resource, document_root=settings.ROOT / 'dist')
    urlpatterns += [path('', lambda request: HttpResponseRedirect('/tongjian/')),
                    path('tongjian', lambda request: HttpResponseRedirect('/tongjian/')),
                    re_path(r'^tongjian/(?P<resource>.*)$', public)]
