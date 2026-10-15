import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from commerce.models import Product, ContentVersion
from commerce.content import validate_content

class Command(BaseCommand):
    help = 'Import reviewed private content. New products are explicitly test-only.'

    def add_arguments(self, parser):
        parser.add_argument('--product', default='truth')

    def handle(self, *args, **options):
        slug = options['product']
        manifest = json.loads((settings.CONTENT_ROOT / slug / 'current.json').read_text())
        with transaction.atomic():
            product, _ = Product.objects.get_or_create(slug=slug, defaults={'title': manifest['title'],
                'price_fen': manifest['test_price_fen'], 'published': True, 'test_product': True})
            defaults = {key: manifest[key] for key in ['article_sha256', 'pdf_sha256', 'relative_directory']}
            version, _ = ContentVersion.objects.get_or_create(product=product, version=manifest['version'], defaults=defaults)
            if any(getattr(version, key) != value for key, value in defaults.items()):
                raise CommandError('Existing content version differs; use a new reviewed version')
            product.current_version = version
            product.save(update_fields=['current_version'])
            validate_content(product)
        self.stdout.write(f'{slug}: imported version {version.version}; test_product={product.test_product}')
