from django.db import models

class PaymentEvent(models.Model):
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=160)
    event_type = models.CharField(max_length=20)
    transaction_id = models.CharField(max_length=100, blank=True)
    merchant_number = models.CharField(max_length=32)
    result = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'event_id'], name='payment_event_unique')]

class FakeTransaction(models.Model):
    merchant_number = models.CharField(max_length=32, unique=True)
    amount_fen = models.PositiveIntegerField()
    state = models.CharField(max_length=16, default='PENDING')
    transaction_id = models.CharField(max_length=100, unique=True)

class FakeRefund(models.Model):
    merchant_number = models.CharField(max_length=32, unique=True)
    amount_fen = models.PositiveIntegerField()
    order_number = models.CharField(max_length=32)
    state = models.CharField(max_length=16, default='processing')
