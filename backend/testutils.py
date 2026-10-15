import hashlib
import tempfile
import uuid
from pathlib import Path
from django.test import override_settings
from accounts.models import User
from commerce.models import Product, ContentVersion
from commerce.services import create_order, ensure_payment

class ContentFixture:
    def create_fixture(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.content_override = override_settings(CONTENT_ROOT=Path(self.directory.name))
        self.content_override.enable()
        self.addCleanup(self.content_override.disable)
        folder = Path(self.directory.name) / 'truth/test'
        folder.mkdir(parents=True)
        article = b'<section id="wugu"><p>private-paid-analysis-marker</p></section>'
        pdf = b'%PDF-1.7\nprivate-pdf-marker'
        (folder / 'article.html').write_bytes(article)
        (folder / 'reader.pdf').write_bytes(pdf)
        self.product = Product.objects.create(slug='truth', title='判断真伪', price_fen=100, published=True)
        version = ContentVersion.objects.create(product=self.product, version='test', relative_directory='truth/test',
            article_sha256=hashlib.sha256(article).hexdigest(), pdf_sha256=hashlib.sha256(pdf).hexdigest())
        self.product.current_version = version
        self.product.save()
        self.user = User.objects.create_user('reader@example.com')
        self.other = User.objects.create_user('other@example.com')
        self.staff = User.objects.create_superuser('admin@example.com', 'test-strong-password')

    def new_order(self, user=None, scene='native', key=None):
        order = create_order(user or self.user, 'truth', self.product.revision, scene, key or uuid.uuid4().hex, '127.0.0.1')
        return ensure_payment(order)
