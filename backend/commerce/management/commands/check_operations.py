import os
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import RateLimitBucket
from commerce.models import Order, Refund, AuditLog, Product
from commerce.content import validate_content
from config.http import Problem

class Command(BaseCommand):
    help = 'Detect current operational issues and send a throttled operator alert.'

    def handle(self, *args, **options):
        now = timezone.now()
        issues = []
        if Order.objects.filter(status='PENDING', query_failures__gte=3).exists():
            issues.append('支付连续查单失败')
        if Refund.objects.filter(status='failed').exists():
            issues.append('退款异常待处理')
        if AuditLog.objects.filter(action='bill_mismatch', created_at__gte=now - timedelta(days=1)).exists():
            issues.append('账单差异待核查')
        if RateLimitBucket.objects.filter(key='global-hour', window=int(now.timestamp()) // 3600, count__gte=200).exists():
            issues.append('验证码全局发信限额触顶')
        if RateLimitBucket.objects.filter(key='global-day', window=int(now.timestamp()) // 86400, count__gte=1000).exists():
            issues.append('验证码每日发信限额触顶')
        for product in Product.objects.filter(published=True):
            try:
                validate_content(product)
            except Problem:
                issues.append('内容文件缺失或校验失败')
        if not issues:
            self.stdout.write('Current operational checks passed')
            return
        if AuditLog.objects.filter(action='operator_alert_sent', created_at__gte=now - timedelta(hours=1)).exists():
            self.stdout.write('Issues already reported within the hour')
            return
        recipient = os.getenv('OPERATOR_EMAIL')
        if not recipient:
            raise CommandError('Issues detected; configure OPERATOR_EMAIL: ' + ', '.join(issues))
        send_mail('通鉴年鉴交易运行告警', '\n'.join(issues) + '\n请到受限后台核查。', settings.DEFAULT_FROM_EMAIL, [recipient])
        AuditLog.objects.create(action='operator_alert_sent', object_id='operations', detail={'issues': issues})
        self.stdout.write('Operator alert sent')
