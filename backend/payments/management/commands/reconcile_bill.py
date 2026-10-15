from datetime import date, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from commerce.models import Order, Payment, Refund, AuditLog
from payments.adapters import get_adapter, ProviderError

class Command(BaseCommand):
    help = 'Compare channel trade/refund bill to local records; never guess orphan ownership.'

    def add_arguments(self, parser):
        parser.add_argument('--date', default=str(date.today() - timedelta(days=1)))

    def handle(self, *args, **options):
        day = date.fromisoformat(options['date'])
        try:
            rows = get_adapter().fetch_bill(day)
        except ProviderError as exc:
            AuditLog.objects.create(action='bill_unavailable', object_id=str(day))
            raise CommandError('Channel bill unavailable; retry and inspect channel permissions') from exc
        issues = 0
        seen = set()
        bill_payments = set()
        bill_refunds = set()
        for row in rows:
            key = (row['type'], row.get('refund_number', row['transaction_id']))
            if key in seen:
                continue
            seen.add(key)
            (bill_refunds if row['type'] == 'refund' else bill_payments).add(key[1])
            order = Order.objects.filter(merchant_number=row['order_number'], provider=settings.PAYMENT_PROVIDER).first()
            local = (Refund.objects.filter(order=order, merchant_number=row.get('refund_number'), status='succeeded').first() if row['type'] == 'refund'
                     else Payment.objects.filter(order=order, transaction_id=row['transaction_id']).first())
            if not local or local.amount_fen != row['amount_fen']:
                issues += 1
                AuditLog.objects.create(action='bill_mismatch', object_id=row['order_number'], detail={'date': str(day), 'type': row['type']})
        for payment in Payment.objects.filter(provider=settings.PAYMENT_PROVIDER, paid_at__date=day):
            if payment.transaction_id not in bill_payments:
                issues += 1
                AuditLog.objects.create(action='bill_mismatch', object_id=payment.order.merchant_number, detail={'date': str(day), 'type': 'missing_payment'})
        for refund in Refund.objects.filter(order__provider=settings.PAYMENT_PROVIDER, status='succeeded', completed_at__date=day):
            if refund.merchant_number not in bill_refunds:
                issues += 1
                AuditLog.objects.create(action='bill_mismatch', object_id=refund.order.merchant_number, detail={'date': str(day), 'type': 'missing_refund'})
        self.stdout.write(f'Bill {day}: {len(rows)} rows, {issues} discrepancies')
        if issues:
            raise CommandError('Bill discrepancies require manual review')
