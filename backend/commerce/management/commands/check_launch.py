import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from commerce.models import Product
from commerce.content import validate_content
from payments.adapters import get_adapter, ProviderError
from config.readiness import missing_gates

class Command(BaseCommand):
    help = 'Fail closed until the real payment, mail, legal, device, cache and recovery evidence is recorded.'

    def handle(self, *args, **options):
        failures = missing_gates(settings.LAUNCH_GATES_FILE)
        if settings.PAYMENT_PROVIDER not in {'wechat'} or settings.ALLOW_FAKE or not settings.LIVE_READY:
            failures.append('real_provider_and_production_settings')
        for product in Product.objects.filter(published=True):
            if product.test_product or product.price_fen < 1 or product.terms_version == 'unconfirmed':
                failures.append('product:' + product.slug)
            validate_content(product)
        try:
            get_adapter()
        except ProviderError:
            failures.append('provider_credentials')
        if failures:
            raise CommandError('Launch not ready: ' + ', '.join(failures))
        self.stdout.write('Recorded launch gates and local configuration passed; keep the actual evidence with the release')
