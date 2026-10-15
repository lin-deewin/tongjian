import hashlib
from dataclasses import replace
from django.db import transaction
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from config.http import Problem
from config.middleware import client_ip
from commerce.models import Order, AuditLog
from commerce.services import confirm_payment, confirm_refund
from .models import PaymentEvent
from .adapters import get_adapter, ProviderError, InvalidNotification

@csrf_exempt
@require_POST
def notify(request, provider, refund=False):
    if provider == 'fake' and (not settings.ALLOW_FAKE or request.META.get('REMOTE_ADDR') not in {'127.0.0.1', '::1'}
                              or client_ip(request) not in {'127.0.0.1', '::1'}):
        return JsonResponse({'code': 'FAIL', 'message': 'Not found'}, status=404)
    if len(request.body) > 65536:
        return JsonResponse({'code': 'FAIL', 'message': 'Notification too large'}, status=400)
    try:
        adapter = get_adapter(provider)
        result = (adapter.verify_refund_notification(request.body, request.headers) if refund else
                  adapter.verify_payment_notification(request.body, request.headers))
        number = result.order_number if refund else result.merchant_number
        # A closed local order needs a fresh channel query before a late success can reopen it.
        order = Order.objects.filter(merchant_number=number, provider=provider).first()
        if not refund and result.state != 'SUCCESS':
            raise InvalidNotification('Not a successful payment notification')
        if order and order.status == 'CLOSED' and not refund:
            result = replace(adapter.query_payment(order), event_id=result.event_id)
            if result.state != 'SUCCESS':
                raise InvalidNotification('Late success not confirmed')
        event_id = result.event_id or hashlib.sha256(request.body).hexdigest()
        with transaction.atomic():
            # Serialize event processing with every payment/refund transition on the order.
            if order:
                Order.objects.select_for_update().get(pk=order.pk)
            existing = PaymentEvent.objects.filter(provider=provider, event_id=event_id).first()
            if existing and (existing.merchant_number != number or existing.event_type != ('refund' if refund else 'payment')):
                raise InvalidNotification('Conflicting notification identity')
            if refund:
                confirm_refund(provider, result)
            else:
                confirm_payment(provider, result)
            if not existing:
                PaymentEvent.objects.create(provider=provider, event_id=event_id, event_type='refund' if refund else 'payment',
                    merchant_number=number, transaction_id=getattr(result, 'transaction_id', ''), result='confirmed')
        return JsonResponse({'code': 'SUCCESS', 'message': '成功'})
    except (ProviderError, Problem, ValueError, TypeError, KeyError):
        AuditLog.objects.create(action='notification_rejected', object_id=provider)
        return JsonResponse({'code': 'FAIL', 'message': 'Notification not verified'}, status=400)
