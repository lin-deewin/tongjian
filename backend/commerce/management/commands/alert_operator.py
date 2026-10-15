import os
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--unit', required=True)

    def handle(self, *args, **options):
        recipient = os.getenv('OPERATOR_EMAIL')
        if not recipient:
            raise CommandError('Configure and verify OPERATOR_EMAIL before launch')
        send_mail('通鉴年鉴服务告警', '服务/任务失败：' + options['unit'] + '\n请检查受限后台和服务日志。', settings.DEFAULT_FROM_EMAIL, [recipient])
