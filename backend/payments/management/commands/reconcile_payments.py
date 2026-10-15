from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from commerce.models import Order, Refund
from commerce.services import reconcile_order, reconcile_refund

class Command(BaseCommand):
    help = 'Bounded reconciliation of pending orders and refunds. Run under flock.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        limit = max(1, min(200, options['limit']))
        count = 0
        for order in Order.objects.filter(status='PENDING').filter(Q(next_query_at__isnull=True) | Q(next_query_at__lte=timezone.now())).order_by('created_at')[:limit]:
            reconcile_order(order)
            count += 1
        for refund in Refund.objects.exclude(status='succeeded').filter(Q(next_query_at__isnull=True) | Q(next_query_at__lte=timezone.now())).select_related('order').order_by('created_at')[:limit]:
            reconcile_refund(refund)
            count += 1
        self.stdout.write(f'Reconciled {count} records')
