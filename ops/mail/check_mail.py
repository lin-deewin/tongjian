#!/usr/bin/env python3
"""Check SMTP TLS/authentication and IMAP delivery using one's own mailbox.

Passwords are read from a terminal prompt or stdin, never command-line arguments.
No existing messages are opened or deleted. A labelled test message is retained.
"""
import argparse
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import getpass
import imaplib
import json
import smtplib
import socket
import ssl
import sys
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mailbox', default='linqp@deewins.top')
    parser.add_argument('--tls-name', default='mail.deewins.top')
    parser.add_argument('--connect-address', help='Optional direct address; TLS hostname verification remains enabled')
    args = parser.parse_args()
    password = getpass.getpass('Mailbox password: ') if sys.stdin.isatty() else sys.stdin.read().rstrip('\r\n')
    if not password:
        raise SystemExit('A mailbox password is required')
    context = ssl.create_default_context()
    resolver = socket.getaddrinfo

    def resolve(host, *pos, **kw):
        if args.connect_address and host == args.tls_name:
            host = args.connect_address
        return resolver(host, *pos, **kw)

    checks = {}
    with patch('socket.getaddrinfo', side_effect=resolve):
        message = EmailMessage()
        message['From'] = message['To'] = args.mailbox
        message['Subject'] = 'Deewins mailbox setup verification'
        message['Date'] = formatdate(localtime=False)
        message['Message-ID'] = make_msgid(domain='deewins.top')
        message.set_content('This message verifies authenticated SMTP delivery to your own IMAP mailbox. No action is needed.')
        with smtplib.SMTP(args.tls_name, 587, local_hostname='mail.deewins.top', timeout=15) as client:
            client.ehlo()
            if client.has_extn('auth'):
                raise RuntimeError('SMTP authentication must not be advertised before TLS')
            client.starttls(context=context)
            client.ehlo()
            client.login(args.mailbox, password)
            checks['smtp_587_tls_auth'] = True
            client.send_message(message)
            checks['smtp_accepted_test_message'] = True
        with smtplib.SMTP_SSL(args.tls_name, 465, local_hostname='mail.deewins.top', timeout=15, context=context) as client:
            client.login(args.mailbox, password)
            checks['smtp_465_tls_auth'] = True
        with imaplib.IMAP4_SSL(args.tls_name, 993, ssl_context=context, timeout=15) as client:
            client.login(args.mailbox, password)
            checks['imap_993_tls_auth'] = True
            found = []
            for _ in range(15):
                status, _data = client.select('INBOX', readonly=True)
                if status != 'OK':
                    raise RuntimeError('Cannot select INBOX')
                status, data = client.search(None, 'HEADER', 'Message-ID', '"' + message['Message-ID'] + '"')
                if status == 'OK' and data[0]:
                    found = data[0].split()
                    break
                time.sleep(1)
            if not found:
                raise RuntimeError('Test message was not delivered to INBOX within 15 seconds')
            status, data = client.fetch(found[-1], '(BODY.PEEK[HEADER.FIELDS (DKIM-SIGNATURE)])')
            headers = b''.join(item[1] for item in data if isinstance(item, tuple))
            if status != 'OK' or b'd=deewins.top' not in headers or b's=mail202610' not in headers:
                raise RuntimeError('Test message is missing the expected DKIM signature')
            checks['imap_delivered_test_message'] = True
            checks['dkim_signature_present'] = True
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
