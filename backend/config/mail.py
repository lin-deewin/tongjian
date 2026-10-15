"""SMTP delivery with a stable public Message-ID domain for account emails."""
from email.utils import make_msgid

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.core.validators import validate_domain_name


class EmailBackend(SMTPBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        messages = list(email_messages)
        domain = settings.EMAIL_MESSAGE_ID_DOMAIN
        validate_domain_name(domain)
        for message in messages:
            if not any(name.lower() == 'message-id' for name in message.extra_headers):
                message.extra_headers['Message-ID'] = make_msgid(domain=domain)
        return super().send_messages(messages)
