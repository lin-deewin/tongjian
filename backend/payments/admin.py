from django.contrib import admin
from commerce.admin import ReadOnlyAdmin
from .models import PaymentEvent
admin.site.register(PaymentEvent, ReadOnlyAdmin)
