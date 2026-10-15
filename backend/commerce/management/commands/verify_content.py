from django.core.management.base import BaseCommand
from commerce.models import Product
from commerce.content import validate_content

class Command(BaseCommand):
    def handle(self, *args, **options):
        for product in Product.objects.filter(current_version__isnull=False):
            validate_content(product)
        self.stdout.write('Private content checksums verified')
