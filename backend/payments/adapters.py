import hashlib
import hmac
import json
from dataclasses import dataclass
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

@dataclass(frozen=True)
class PaymentResult:
    merchant_number: str
    state: str
    amount_fen: int
    transaction_id: str = ''
    currency: str = 'CNY'
    event_id: str = ''
    paid_at: str = ''

@dataclass(frozen=True)
class RefundResult:
    merchant_number: str
    order_number: str
    state: str
    amount_fen: int
    channel_id: str = ''
    event_id: str = ''
    completed_at: str = ''

class ProviderError(Exception):
    pass

class ProviderRejected(ProviderError):
    def __init__(self, message, code=''):
        super().__init__(message)
        self.code = code

class InvalidNotification(ProviderError):
    pass

class FakeAdapter:
    def __init__(self):
        if not settings.ALLOW_FAKE:
            raise ImproperlyConfigured('Fake payments are not allowed')

    def create_payment(self, order):
        from .models import FakeTransaction
        FakeTransaction.objects.get_or_create(merchant_number=order.merchant_number,
            defaults={'amount_fen': order.amount_fen, 'transaction_id': 'fake-' + order.merchant_number})
        return {'kind': 'fake', 'test_only': True}

    def query_payment(self, order):
        from .models import FakeTransaction
        row = FakeTransaction.objects.filter(merchant_number=order.merchant_number).first()
        if not row:
            return PaymentResult(order.merchant_number, 'NOT_FOUND', order.amount_fen)
        return PaymentResult(row.merchant_number, row.state, row.amount_fen, row.transaction_id)

    def close_payment(self, order):
        from .models import FakeTransaction
        FakeTransaction.objects.filter(merchant_number=order.merchant_number, state='PENDING').update(state='CLOSED')
        return self.query_payment(order)

    def verify_payment_notification(self, raw, headers):
        data = self._verify(raw, headers)
        return PaymentResult(**data)

    def verify_refund_notification(self, raw, headers):
        return RefundResult(**self._verify(raw, headers))

    def _verify(self, raw, headers):
        expected = hmac.new(settings.FAKE_PAYMENT_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, headers.get('X-Fake-Signature', '')):
            raise InvalidNotification('Invalid fake signature')
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise InvalidNotification('Invalid body') from exc

    def create_refund(self, refund):
        from .models import FakeRefund
        FakeRefund.objects.get_or_create(merchant_number=refund.merchant_number,
            defaults={'amount_fen': refund.amount_fen, 'order_number': refund.order.merchant_number})
        return self.query_refund(refund)

    def query_refund(self, refund):
        from .models import FakeRefund
        row = FakeRefund.objects.get(merchant_number=refund.merchant_number)
        return RefundResult(row.merchant_number, row.order_number, row.state, row.amount_fen, 'fake-' + row.merchant_number)

    def fetch_bill(self, date):
        from .models import FakeTransaction, FakeRefund
        return ([{'order_number': r.merchant_number, 'transaction_id': r.transaction_id, 'amount_fen': r.amount_fen, 'type': 'payment'}
                 for r in FakeTransaction.objects.filter(state='SUCCESS')] +
                [{'order_number': r.order_number, 'transaction_id': 'fake-' + r.merchant_number, 'amount_fen': r.amount_fen,
                  'refund_number': r.merchant_number, 'type': 'refund'} for r in FakeRefund.objects.filter(state='succeeded')])

def get_adapter(provider=None):
    provider = provider or settings.PAYMENT_PROVIDER
    if provider != settings.PAYMENT_PROVIDER:
        raise ProviderRejected('Inactive payment provider')
    if provider == 'fake':
        return FakeAdapter()
    if provider == 'wechat':
        from .wechat import WeChatAdapter
        return WeChatAdapter()
    raise ProviderRejected('Payment provider is not configured')
