import io
import uuid
from pathlib import Path

import qrcode
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.http import FileResponse, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST

from config.http import endpoint, body, user_required, Problem
from config.middleware import client_ip
from payments.adapters import get_adapter
from payments.models import FakeTransaction
from .models import Product, Order, AccessGrant, Refund
from .content import has_access, content_file, validate_content
from .services import create_order, ensure_payment, reconcile_order, verification_allowed

@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'healthy': True})
    except Exception:
        return JsonResponse({'healthy': False}, status=503)

@require_GET
@endpoint
def product_info(request, slug):
    product = get_object_or_404(Product, slug=slug, published=True)
    available = settings.SALES_ENABLED and settings.PAYMENT_PROVIDER != 'disabled' and ((settings.ALLOW_FAKE and settings.PAYMENT_PROVIDER == 'fake') or
                 (settings.LIVE_READY and not product.test_product and product.terms_version != 'unconfirmed'))
    try:
        validate_content(product)
    except Problem:
        available = False
    return JsonResponse({'slug': product.slug, 'title': product.title, 'price_fen': product.price_fen,
        'currency': product.currency, 'revision': product.revision, 'test_only': product.test_product,
        'price_label': ('本地测试价' if settings.PAYMENT_PROVIDER == 'fake' else '商户验收价（真实扣款）') if product.test_product else '',
        'price_confirmed': not product.test_product or settings.PAYMENT_PROVIDER == 'fake' or settings.PAYMENT_VERIFICATION_ENABLED,
        'sales_enabled': available, 'terms_version': product.terms_version,
        'scenes': [s for s in settings.PAYMENT_SCENES if s in {'native', 'h5'}],
        'includes': ['专题全文', '配套 PDF'], 'preview_url': '/truth.html',
        'terms_url': '/account/terms/'})

def order_data(order):
    return {'id': str(order.pk), 'number': order.merchant_number, 'status': order.status,
            'amount_fen': order.amount_fen, 'title': order.title,
            'checkout_url': f'/checkout/{order.pk}/',
            'article_url': f'/article/{order.product.slug}/',
            'refund_status': Refund.objects.filter(order=order).values_list('status', flat=True).first()}

@require_POST
@endpoint
def orders(request):
    user_required(request)
    data = body(request)
    if 'amount_fen' in data or 'price' in data:
        raise Problem('invalid_request', '价格由服务器确定。')
    scene = data.get('scene')
    if scene == 'h5' and 'micromessenger' in request.headers.get('User-Agent', '').lower():
        raise Problem('unsupported_scene', '请在系统浏览器中打开后购买。')
    if data.get('accept_terms') is not True:
        raise Problem('terms_required', '请先阅读并同意商品购买说明。')
    order = create_order(request.user, data.get('product'), data.get('revision'), scene,
                          request.headers.get('Idempotency-Key'), client_ip(request))
    order = ensure_payment(order)
    return JsonResponse(order_data(order), status=201)

@require_GET
@endpoint
def order_info(request, order_id):
    user_required(request)
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    order = reconcile_order(order)
    return JsonResponse(order_data(order))

@require_GET
@endpoint
def purchases(request):
    user_required(request)
    grants = AccessGrant.objects.filter(user=request.user, active=True).select_related('product').order_by('-created_at')
    page = Paginator(grants, 20).get_page(request.GET.get('page', 1))
    unique = {}
    for grant in page:
        product = grant.product
        unique[product.slug] = {'slug': product.slug, 'title': product.title,
            'article_url': f'/article/{product.slug}/',
            'download_url': f'/api/v1/products/{product.slug}/download/'}
    return JsonResponse({'items': list(unique.values()), 'pages': page.paginator.num_pages, 'page': page.number})

@require_GET
@login_required
def purchases_page(request):
    return render(request, 'purchases.html', {'grants': AccessGrant.objects.filter(user=request.user, active=True).select_related('product'),
        'orders': Order.objects.filter(user=request.user).select_related('product').order_by('-created_at')[:50]})

@require_GET
@login_required
@endpoint
def article(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if not has_access(request.user, product):
        return HttpResponseRedirect('/truth.html' + ('#' + request.GET['anchor'] if request.GET.get('anchor', '').isalnum() else ''))
    path = content_file(product.current_version, 'article.html')
    return render(request, 'article.html', {'product': product, 'article_body': mark_safe(path.read_text().replace('href="/tongjian/', 'href="/').replace("href='/tongjian/", "href='/"))})

@require_GET
@endpoint
def download(request, slug):
    user_required(request)
    product = get_object_or_404(Product, slug=slug)
    if not has_access(request.user, product):
        raise Problem('purchase_required', '请购买后下载。', 403)
    path = content_file(product.current_version, 'reader.pdf')
    return FileResponse(path.open('rb'), as_attachment=True, filename='tongjian-' + product.slug + '.pdf', content_type='application/pdf')

@require_GET
@login_required
def checkout(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    order = reconcile_order(order)
    return render(request, 'checkout.html', {'order': order, 'test_only': settings.ALLOW_FAKE and order.provider == 'fake',
        'merchant_verification': verification_allowed(request.user) and order.provider == 'wechat',
        'inside_wechat': 'micromessenger' in request.headers.get('User-Agent', '').lower()})

@require_GET
@login_required
@endpoint
def qr(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user, status='PENDING')
    code = order.payment_data.get('code_url')
    if not code or not code.startswith('weixin://'):
        raise Problem('unavailable', '支付二维码暂不可用。', 503)
    image = qrcode.make(code)
    output = io.BytesIO()
    image.save(output, format='PNG')
    return HttpResponse(output.getvalue(), content_type='image/png')

@require_POST
@endpoint
def simulate(request, order_id):
    # A dev-only adapter endpoint restricted to a real loopback peer, ownership, session and CSRF.
    if (not settings.ALLOW_FAKE or settings.PAYMENT_PROVIDER != 'fake' or request.META.get('REMOTE_ADDR') not in {'127.0.0.1', '::1'}
            or client_ip(request) not in {'127.0.0.1', '::1'}):
        raise Problem('not_found', '不存在此接口。', 404)
    user_required(request)
    order = get_object_or_404(Order, pk=order_id, user=request.user, provider='fake')
    state = body(request).get('state', 'SUCCESS')
    if state not in {'SUCCESS', 'PENDING', 'CLOSED'}:
        raise Problem('invalid_request', '测试状态无效。')
    ensure_payment(order)
    FakeTransaction.objects.filter(merchant_number=order.merchant_number).update(state=state)
    order = reconcile_order(order, force=True)
    return JsonResponse(order_data(order))

@require_GET
def terms(request):
    text = Path(settings.TERMS_FILE).read_text() if settings.TERMS_FILE else ''
    return render(request, 'terms.html', {'live_ready': settings.LIVE_READY, 'terms_text': text})
