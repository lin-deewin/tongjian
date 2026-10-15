import hashlib
import json
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from accounts.models import User
from config.http import Problem
from config.readiness import missing_gates
from payments.adapters import get_adapter, ProviderError, ProviderRejected, PaymentResult
from .content import has_access, validate_content
from .models import Product, Order, OrderKey, Payment, AccessGrant, Refund, AuditLog

logger = logging.getLogger(__name__)

def verification_allowed(user):
    return (user.is_authenticated and settings.PAYMENT_VERIFICATION_ENABLED and settings.PAYMENT_PROVIDER == 'wechat'
            and user.email in settings.PAYMENT_VERIFICATION_BUYERS and settings.PAYMENT_VERIFICATION_PRICE_FEN > 0
            and not {'merchant_products', 'price_and_terms', 'email_delivery'}.intersection(missing_gates(settings.LAUNCH_GATES_FILE)))

def create_order(user, slug, revision, scene, key, address):
    if not isinstance(slug, str) or not isinstance(scene, str):
        raise Problem('invalid_request', '商品与付款方式不正确。')
    if not isinstance(key, str) or not 8 <= len(key) <= 100:
        raise Problem('invalid_key', '需要有效的请求标识。')
    verification = verification_allowed(user)
    fake = settings.ALLOW_FAKE and settings.PAYMENT_PROVIDER == 'fake'
    if (not settings.SALES_ENABLED and not verification) or settings.PAYMENT_PROVIDER == 'disabled':
        raise Problem('sales_closed', '购买暂未开放。', 503)
    if scene not in settings.PAYMENT_SCENES or scene not in {'native', 'h5'}:
        raise Problem('unsupported_scene', '当前环境不支持此付款方式。')
    request_digest = hashlib.sha256(json.dumps([slug, revision, scene], ensure_ascii=False).encode()).hexdigest()
    with transaction.atomic():
        User.objects.select_for_update(no_key=True).get(pk=user.pk)
        prior = OrderKey.objects.filter(user=user, key=key).select_related('order').first()
        if prior:
            if prior.request_digest != request_digest:
                raise Problem('idempotency_conflict', '此请求标识已用于其他购买请求。', 409)
            return prior.order
        product = Product.objects.select_for_update(no_key=True).filter(slug=slug, published=True).first()
        if not product:
            raise Problem('not_found', '商品尚未上架。', 404)
        if type(revision) is not int or revision != product.revision:
            raise Problem('price_changed', '商品价格或说明已更新，请刷新后确认。', 409)
        if product.test_product and not fake and not verification:
            raise Problem('sales_closed', '此商品仍为测试商品。', 503)
        if (product.price_fen < 1 or product.currency != 'CNY'
                or (verification and product.price_fen != settings.PAYMENT_VERIFICATION_PRICE_FEN)
                or (not fake and (product.terms_version == 'unconfirmed' or (not settings.LIVE_READY and not verification)))):
            raise Problem('sales_closed', '商品售卖条件尚未确认。', 503)
        validate_content(product)
        if has_access(user, product):
            raise Problem('already_owned', '你已拥有此专题。', 409)
        order = Order.objects.filter(user=user, product=product, status='PENDING').first()
        if order and order.scene != scene:
            raise Problem('pending_order', '已有待确认订单，请先确认原订单。', 409)
        if not order:
            order = Order.objects.create(merchant_number=uuid.uuid4().hex, user=user, product=product,
                amount_fen=product.price_fen, title=product.title, currency=product.currency,
                content_version=product.current_version, terms_version=product.terms_version,
                provider=settings.PAYMENT_PROVIDER, scene=scene, client_ip=address,
                expires_at=timezone.now() + timedelta(minutes=30))
        OrderKey.objects.create(user=user, key=key, request_digest=request_digest, order=order)
    return order

def ensure_payment(order):
    if order.status != 'PENDING' or order.payment_data:
        return order
    try:
        data = get_adapter(order.provider).create_payment(order)
        with transaction.atomic():
            current = Order.objects.select_for_update(no_key=True).get(pk=order.pk)
            if current.status == 'PENDING':
                current.payment_data = data
                current.save(update_fields=['payment_data'])
    except ProviderError:
        logger.warning('payment_creation_unconfirmed order_id=%s', order.pk)
        AuditLog.objects.create(action='payment_creation_unconfirmed', object_id=str(order.pk))
    return Order.objects.get(pk=order.pk)

def confirm_payment(provider, result):
    with transaction.atomic():
        order = Order.objects.select_for_update(no_key=True).filter(merchant_number=result.merchant_number, provider=provider).first()
        if not order:
            raise Problem('unknown_order', '未找到订单。', 409)
        if type(result.amount_fen) is not int or result.amount_fen != order.amount_fen or result.currency != order.currency:
            raise Problem('payment_mismatch', '交易金额或币种不符。', 409)
        if result.state == 'SUCCESS':
            if not result.transaction_id:
                raise Problem('payment_mismatch', '交易标识缺失。', 409)
            payment = Payment.objects.filter(order=order).first()
            if payment and payment.transaction_id != result.transaction_id:
                raise Problem('payment_mismatch', '订单出现不同交易标识。', 409)
            paid_at = parse_datetime(result.paid_at) if result.paid_at else timezone.now()
            if not paid_at or timezone.is_naive(paid_at):
                raise Problem('payment_mismatch', '交易时间格式不符。', 409)
            Payment.objects.get_or_create(order=order, defaults={'provider': provider,
                'transaction_id': result.transaction_id, 'amount_fen': result.amount_fen, 'paid_at': paid_at})
            if order.status == 'CLOSED':
                AuditLog.objects.create(action='late_payment_confirmed', object_id=str(order.pk))
            order.status = 'PAID'
            order.save(update_fields=['status'])
            refunded = Refund.objects.filter(order=order, status='succeeded').exists()
            AccessGrant.objects.get_or_create(order=order, defaults={'user': order.user, 'product': order.product,
                'active': not refunded, 'reason': 'payment'})
        elif result.state == 'CLOSED' and order.status == 'PENDING':
            order.status = 'CLOSED'
            order.save(update_fields=['status'])
        return order

def reconcile_order(order, force=False):
    now = timezone.now()
    with transaction.atomic():
        order = Order.objects.select_for_update(no_key=True).get(pk=order.pk)
        if order.status != 'PENDING' or (not force and order.next_query_at and order.next_query_at > now):
            return order
        order.next_query_at = now + timedelta(seconds=30)
        order.save(update_fields=['next_query_at'])
    try:
        adapter = get_adapter(order.provider)
        result = adapter.query_payment(order)
        if result.merchant_number != order.merchant_number:
            raise ProviderError('Channel returned a different order')
        if result.state == 'NOT_FOUND' and order.expires_at <= now:
            result = PaymentResult(order.merchant_number, 'CLOSED', order.amount_fen)
        elif result.state == 'NOT_FOUND' and not order.payment_data:
            data = adapter.create_payment(order)
            Order.objects.filter(pk=order.pk, status='PENDING').update(payment_data=data)
        elif result.state == 'PENDING' and order.expires_at <= now:
            result = adapter.close_payment(order)
        updated = confirm_payment(order.provider, result)
        Order.objects.filter(pk=order.pk).update(query_failures=0)
        return updated
    except ProviderError:
        with transaction.atomic():
            current = Order.objects.select_for_update(no_key=True).get(pk=order.pk)
            current.query_failures = min(current.query_failures + 1, 100)
            current.next_query_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(current.query_failures, 7)))
            current.save(update_fields=['query_failures', 'next_query_at'])
        logger.warning('payment_query_unconfirmed order_id=%s', order.pk)
        return current

def confirm_refund(provider, result):
    with transaction.atomic():
        order = Order.objects.select_for_update(no_key=True).filter(merchant_number=result.order_number, provider=provider).first()
        if not order:
            raise Problem('unknown_order', '未找到退款订单。', 409)
        refund = Refund.objects.select_for_update(no_key=True).filter(order=order, merchant_number=result.merchant_number).first()
        if (not refund and not Refund.objects.filter(order=order).exists() and result.state == 'succeeded'
                and type(result.amount_fen) is int and result.amount_fen == order.amount_fen):
            # A verified full refund initiated in the merchant console may arrive before the payment notification.
            # The known order binds its owner; never infer an owner for an unknown order.
            refund = Refund.objects.create(order=order, merchant_number=result.merchant_number, amount_fen=result.amount_fen,
                                            reason='Verified channel-initiated full refund')
            AuditLog.objects.create(action='external_refund_recorded', object_id=str(refund.pk))
        if not refund or type(result.amount_fen) is not int or result.amount_fen != refund.amount_fen:
            raise Problem('refund_mismatch', '退款标识或金额不符。', 409)
        if refund.status == 'succeeded':
            return refund
        if result.state not in {'processing', 'succeeded', 'failed'}:
            raise Problem('refund_mismatch', '退款状态不正确。', 409)
        refund.status, refund.channel_id = result.state, result.channel_id
        if refund.status == 'succeeded':
            refund.completed_at = parse_datetime(result.completed_at) if result.completed_at else timezone.now()
            if not refund.completed_at or timezone.is_naive(refund.completed_at):
                raise Problem('refund_mismatch', '退款时间格式不符。', 409)
        refund.save(update_fields=['status', 'channel_id', 'completed_at'])
        if refund.status == 'succeeded':
            AccessGrant.objects.filter(order=order).update(active=False)
            AuditLog.objects.create(action='refund_confirmed', object_id=str(refund.pk))
        return refund

def request_refund(order, actor, reason):
    if not actor.is_staff or not reason.strip():
        raise Problem('forbidden', '需要管理员和退款原因。', 403)
    with transaction.atomic():
        order = Order.objects.select_for_update(no_key=True).get(pk=order.pk)
        if order.status != 'PAID' or not Payment.objects.filter(order=order).exists():
            raise Problem('not_paid', '仅已确认付款的订单可以退款。', 409)
        refund, created = Refund.objects.get_or_create(order=order,
            defaults={'merchant_number': uuid.uuid4().hex, 'amount_fen': order.amount_fen, 'reason': reason[:300]})
        if created:
            AuditLog.objects.create(actor=actor, action='refund_requested', object_id=str(refund.pk), detail={'reason': reason[:300]})
    if refund.status in {'requested', 'failed'}:
        try:
            result = get_adapter(order.provider).create_refund(refund)
            if result.merchant_number != refund.merchant_number or result.order_number != order.merchant_number:
                raise ProviderError('Channel returned a different refund')
            return confirm_refund(order.provider, result)
        except ProviderError:
            logger.warning('refund_request_unconfirmed refund_id=%s', refund.pk)
    return refund

def reconcile_refund(refund):
    if refund.status == 'succeeded':
        return refund
    with transaction.atomic():
        Order.objects.select_for_update(no_key=True).get(pk=refund.order_id)
        refund = Refund.objects.select_for_update(no_key=True).get(pk=refund.pk)
        if refund.status == 'succeeded' or (refund.next_query_at and refund.next_query_at > timezone.now()):
            return refund
        refund.next_query_at = timezone.now() + timedelta(minutes=5)
        refund.save(update_fields=['next_query_at'])
    try:
        adapter = get_adapter(refund.order.provider)
        result = adapter.create_refund(refund) if refund.status == 'requested' else adapter.query_refund(refund)
        if result.merchant_number != refund.merchant_number or result.order_number != refund.order.merchant_number:
            raise ProviderError('Channel returned a different refund')
        return confirm_refund(refund.order.provider, result)
    except ProviderError:
        AuditLog.objects.create(action='refund_unconfirmed', object_id=str(refund.pk))
        return refund
