from django.contrib import admin, messages
from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.db import transaction
from config.http import Problem
from .models import Product, ContentVersion, Order, Payment, AccessGrant, Refund, AuditLog
from .services import request_refund

class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'price_fen', 'published', 'test_product', 'revision')
    readonly_fields = ('revision', 'current_version')

    def save_model(self, request, obj, form, change):
        if change:
            current = Product.objects.select_for_update(no_key=True).get(pk=obj.pk)
            obj.revision = current.revision + 1
        super().save_model(request, obj, form, change)
        AuditLog.objects.create(actor=request.user, action='product_changed', object_id=str(obj.pk), detail={'revision': obj.revision})

class RefundForm(forms.Form):
    reason = forms.CharField(label='退款原因', max_length=300, widget=forms.Textarea)
    password = forms.CharField(label='再次输入管理员密码', widget=forms.PasswordInput)

@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    list_display = ('merchant_number', 'user', 'title', 'amount_fen', 'status', 'refund_link')
    list_filter = ('status', 'provider')
    search_fields = ('merchant_number', 'user__email')

    def get_urls(self):
        return [path('<uuid:order_id>/refund/', self.admin_site.admin_view(self.refund_view), name='commerce_order_refund')] + super().get_urls()

    def refund_link(self, obj):
        if obj.status == 'PAID':
            return format_html('<a href="{}">全额退款</a>', reverse('admin:commerce_order_refund', args=[obj.pk]))
        return '—'

    def refund_view(self, request, order_id):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        order = get_object_or_404(Order, pk=order_id)
        form = RefundForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            if not request.user.check_password(form.cleaned_data['password']):
                form.add_error('password', '密码不正确。')
            else:
                try:
                    refund = request_refund(order, request.user, form.cleaned_data['reason'])
                    messages.info(request, '退款状态：' + refund.status + '。最终成功后撤销此订单权益。')
                    return redirect('admin:commerce_order_changelist')
                except Problem as exc:
                    form.add_error(None, exc.message)
        return render(request, 'admin/refund.html', {**self.admin_site.each_context(request), 'form': form, 'order': order, 'title': '全额退款'})

@admin.register(AccessGrant)
class GrantAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'active', 'order', 'created_at')
    search_fields = ('user__email', 'reason')
    readonly_fields = ('order', 'created_at')
    autocomplete_fields = ('user',)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.order_id:
            return [field.name for field in self.model._meta.fields]
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not obj.reason.strip():
            raise forms.ValidationError('权益操作必须记录原因。')
        super().save_model(request, obj, form, change)
        AuditLog.objects.create(actor=request.user, action='grant_changed', object_id=str(obj.pk),
                               detail={'active': obj.active, 'reason': obj.reason})

    def has_delete_permission(self, request, obj=None):
        return False

for model in [ContentVersion, Payment, Refund, AuditLog]:
    admin.site.register(model, ReadOnlyAdmin)
