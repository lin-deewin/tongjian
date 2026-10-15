import hashlib
from django.conf import settings
from config.http import Problem
from .models import AccessGrant

def has_access(user, product):
    return user.is_authenticated and AccessGrant.objects.filter(user=user, product=product, active=True).exists()

def content_file(version, filename):
    if filename not in {'article.html', 'reader.pdf'}:
        raise Problem('content_unavailable', '内容暂不可用。', 503)
    path = (settings.CONTENT_ROOT / version.relative_directory / filename).resolve()
    if not path.is_relative_to(settings.CONTENT_ROOT.resolve()):
        raise Problem('content_unavailable', '内容暂不可用。', 503)
    expected = version.article_sha256 if filename == 'article.html' else version.pdf_sha256
    try:
        data = path.read_bytes()
    except OSError:
        raise Problem('content_unavailable', '内容暂不可用，请联系站点。', 503)
    if hashlib.sha256(data).hexdigest() != expected:
        raise Problem('content_unavailable', '内容版本校验失败，请联系站点。', 503)
    return path

def validate_content(product):
    if not product.current_version or product.current_version.product_id != product.pk:
        raise Problem('content_unavailable', '商品内容暂不可用。', 503)
    content_file(product.current_version, 'article.html')
    content_file(product.current_version, 'reader.pdf')
