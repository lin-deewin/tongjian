import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

def merchant_number():
    return uuid.uuid4().hex

class Product(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    price_fen = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default='CNY')
    published = models.BooleanField(default=False)
    test_product = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    terms_version = models.CharField(max_length=40, default='unconfirmed')
    current_version = models.ForeignKey('ContentVersion', on_delete=models.PROTECT, null=True, blank=True, related_name='+')

    def __str__(self):
        return self.title

class ContentVersion(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    version = models.CharField(max_length=40)
    article_sha256 = models.CharField(max_length=64)
    pdf_sha256 = models.CharField(max_length=64)
    relative_directory = models.CharField(max_length=200)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['product', 'version'], name='content_version_unique')]

class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_number = models.CharField(max_length=32, unique=True, default=merchant_number)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    amount_fen = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default='CNY')
    title = models.CharField(max_length=200)
    content_version = models.ForeignKey(ContentVersion, on_delete=models.PROTECT)
    terms_version = models.CharField(max_length=40)
    provider = models.CharField(max_length=20)
    scene = models.CharField(max_length=20)
    client_ip = models.GenericIPAddressField()
    status = models.CharField(max_length=12, default='PENDING', db_index=True)
    payment_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    next_query_at = models.DateTimeField(null=True, db_index=True)
    query_failures = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'product'], condition=Q(status='PENDING'), name='one_pending_order')]

class OrderKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    request_digest = models.CharField(max_length=64)
    order = models.ForeignKey(Order, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'key'], name='order_idempotency_unique')]

class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT)
    provider = models.CharField(max_length=20)
    transaction_id = models.CharField(max_length=100)
    amount_fen = models.PositiveIntegerField()
    confirmed_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'transaction_id'], name='payment_transaction_unique')]

class AccessGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    order = models.OneToOneField(Order, null=True, blank=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    reason = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_number = models.CharField(max_length=32, unique=True)
    order = models.OneToOneField(Order, on_delete=models.PROTECT)
    amount_fen = models.PositiveIntegerField()
    status = models.CharField(max_length=16, default='requested', db_index=True)
    channel_id = models.CharField(max_length=100, blank=True)
    reason = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    next_query_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    object_id = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
