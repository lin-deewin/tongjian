import base64
import hashlib
import hmac
import json
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import DatabaseError
from django.test import TestCase, SimpleTestCase, override_settings
from config.http import Problem
from testutils import ContentFixture
from commerce.models import Order, Payment, AccessGrant, Refund
from commerce.services import request_refund
from .adapters import PaymentResult, RefundResult, InvalidNotification, FakeAdapter
from .models import PaymentEvent, FakeTransaction
from .wechat import WeChatAdapter, parse_bill

class CallbackTests(ContentFixture, TestCase):
    def setUp(self):
        self.create_fixture()

    def notify(self, result, refund=False, valid=True):
        raw = json.dumps(asdict(result)).encode()
        signature = hmac.new(settings.FAKE_PAYMENT_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        path = '/tongjian/api/v1/payments/fake/' + ('refund-notify/' if refund else 'notify/')
        return self.client.post(path, raw, content_type='application/json', HTTP_X_FAKE_SIGNATURE=signature if valid else 'invalid')

    def test_signed_notification_and_repeat(self):
        order = self.new_order()
        result = PaymentResult(order.merchant_number, 'SUCCESS', 100, 'transaction-1', event_id='event-1')
        self.assertEqual(self.notify(result).status_code, 200)
        self.assertEqual(self.notify(result).status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AccessGrant.objects.count(), 1)
        self.assertEqual(PaymentEvent.objects.count(), 1)

    def test_invalid_signature_and_amount(self):
        order = self.new_order()
        result = PaymentResult(order.merchant_number, 'SUCCESS', 100, 'transaction-1')
        self.assertEqual(self.notify(result, valid=False).status_code, 400)
        self.assertEqual(self.notify(PaymentResult(order.merchant_number, 'SUCCESS', 99, 'transaction-1')).status_code, 400)
        self.assertFalse(AccessGrant.objects.exists())

    def test_closed_late_success_requires_channel_confirmation(self):
        order = self.new_order()
        Order.objects.filter(pk=order.pk).update(status='CLOSED')
        result = PaymentResult(order.merchant_number, 'SUCCESS', 100, 'transaction-1')
        self.assertEqual(self.notify(result).status_code, 400)
        FakeTransaction.objects.filter(merchant_number=order.merchant_number).update(state='SUCCESS')
        self.assertEqual(self.notify(result).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'PAID')

    def test_db_failure_rolls_back_payment_and_grant(self):
        order = self.new_order()
        result = PaymentResult(order.merchant_number, 'SUCCESS', 100, 'transaction-1')
        with patch('commerce.services.AccessGrant.objects.get_or_create', side_effect=DatabaseError('temporary failure')):
            with self.assertRaises(DatabaseError):
                self.notify(result)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(AccessGrant.objects.exists())
        self.assertFalse(PaymentEvent.objects.exists())
        self.assertEqual(self.notify(result).status_code, 200)

    def test_refund_notifications_do_not_restore_revoked_grant(self):
        order = self.new_order()
        payment = PaymentResult(order.merchant_number, 'SUCCESS', 100, 'transaction-1', event_id='payment')
        self.notify(payment)
        refund = request_refund(order, self.staff, '测试退款')
        result = RefundResult(refund.merchant_number, order.merchant_number, 'succeeded', 100, event_id='refund')
        self.assertEqual(self.notify(result, refund=True).status_code, 200)
        self.assertEqual(self.notify(result, refund=True).status_code, 200)
        self.notify(PaymentResult(order.merchant_number, 'SUCCESS', 100, 'transaction-1', event_id='late-payment'))
        self.assertFalse(AccessGrant.objects.get().active)

class WeChatCryptographyTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name)
        self.platform_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        merchant = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        (path / 'merchant.pem').write_bytes(merchant.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        (path / 'platform.pem').write_bytes(self.platform_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        (path / 'keyring.json').write_text(json.dumps({'PUB_KEY_ID_test': str(path / 'platform.pem')}))
        config = {'MCH_ID': 'mch-test', 'APP_ID': 'app-test', 'MERCHANT_SERIAL': 'merchant-serial',
                  'PRIVATE_KEY_FILE': str(path / 'merchant.pem'), 'PUBLIC_KEYS_FILE': str(path / 'keyring.json'), 'API_V3_KEY': 'a' * 32}
        self.override = override_settings(WECHAT=config)
        self.override.enable(); self.addCleanup(self.override.disable)
        self.adapter = WeChatAdapter()
        self.payment = {'mchid': 'mch-test', 'appid': 'app-test', 'out_trade_no': 'order-test',
                        'trade_state': 'SUCCESS', 'transaction_id': 'wx-test', 'amount': {'total': 100, 'currency': 'CNY'}}

    def headers(self, raw, timestamp=None):
        timestamp = str(timestamp or int(time.time()))
        nonce = 'header-nonce'
        signature = self.platform_key.sign(timestamp.encode() + b'\n' + nonce.encode() + b'\n' + raw + b'\n', padding.PKCS1v15(), hashes.SHA256())
        return httpx.Headers({'Wechatpay-Serial': 'PUB_KEY_ID_test', 'Wechatpay-Timestamp': timestamp,
                              'Wechatpay-Nonce': nonce, 'Wechatpay-Signature': base64.b64encode(signature).decode()})

    def event(self, data=None, kind='TRANSACTION.SUCCESS'):
        nonce = b'resource1234'
        encrypted = AESGCM(b'a' * 32).encrypt(nonce, json.dumps(data or self.payment).encode(), b'transaction')
        raw = json.dumps({'id': 'event-test', 'event_type': kind, 'resource': {'algorithm': 'AEAD_AES_256_GCM',
            'nonce': nonce.decode(), 'associated_data': 'transaction', 'ciphertext': base64.b64encode(encrypted).decode()}}).encode()
        return raw, self.headers(raw)

    def test_rsa_verify_and_aes_gcm_decrypt(self):
        raw, headers = self.event()
        result = self.adapter.verify_payment_notification(raw, headers)
        self.assertEqual(result.amount_fen, 100)
        self.assertEqual(result.transaction_id, 'wx-test')
        self.assertEqual(result.event_id, 'event-test')

    def test_tampering_expired_unknown_key_wrong_merchant_and_app(self):
        raw, headers = self.event()
        with self.assertRaises(InvalidNotification):
            self.adapter.verify_payment_notification(raw + b' ', headers)
        for bad in [self.headers(raw, int(time.time()) - 600), {**headers, 'Wechatpay-Serial': 'untrusted'}]:
            with self.assertRaises(InvalidNotification):
                self.adapter.verify_payment_notification(raw, bad)
        for field in ['mchid', 'appid']:
            other = {**self.payment, field: 'wrong'}
            wrong_raw, wrong_headers = self.event(other)
            with self.assertRaises(InvalidNotification):
                self.adapter.verify_payment_notification(wrong_raw, wrong_headers)

    def test_wrong_aes_key_and_event_type(self):
        raw, headers = self.event()
        self.adapter.config = {**self.adapter.config, 'API_V3_KEY': 'b' * 32}
        with self.assertRaises(InvalidNotification):
            self.adapter.verify_payment_notification(raw, headers)
        raw, headers = self.event(kind='REFUND.SUCCESS')
        with self.assertRaises(InvalidNotification):
            self.adapter.verify_payment_notification(raw, headers)

    def test_request_signature_response_verification(self):
        payload = {'test': '正文'}
        response_body = b'{"code_url":"weixin://test"}'
        response = httpx.Response(200, content=response_body, headers=self.headers(response_body))
        with patch('payments.wechat.httpx.request', return_value=response) as send:
            result = self.adapter._request('POST', '/v3/test', payload)
        self.assertEqual(result['code_url'], 'weixin://test')
        arguments = send.call_args.kwargs
        auth = arguments['headers']['Authorization']
        import re
        values = dict(re.findall(r'(\w+)="([^"]+)"', auth))
        canonical = f'POST\n/v3/test\n{values["timestamp"]}\n{values["nonce_str"]}\n'.encode() + arguments['content'] + b'\n'
        self.adapter.private_key.public_key().verify(base64.b64decode(values['signature']), canonical, padding.PKCS1v15(), hashes.SHA256())
        with patch('payments.wechat.httpx.request', return_value=httpx.Response(200, json={'code_url': 'weixin://bad'})):
            with self.assertRaises(InvalidNotification):
                self.adapter._request('POST', '/v3/test', payload)

    def test_refund_notification(self):
        data = {'mchid': 'mch-test', 'out_refund_no': 'refund-test', 'out_trade_no': 'order-test',
                'refund_status': 'SUCCESS', 'refund_id': 'wx-refund', 'amount': {'refund': 100, 'total': 100}}
        raw, headers = self.event(data, 'REFUND.SUCCESS')
        result = self.adapter.verify_refund_notification(raw, headers)
        self.assertEqual(result.state, 'succeeded')
        self.assertEqual(result.amount_fen, 100)

    def test_bill_format(self):
        text = '商户订单号,微信支付订单号,交易状态,订单金额,商户退款单号,微信退款单号,申请退款金额\n`order,`wx,`REFUND,`1.00,`refund,`wxrefund,`1.00\n'
        rows = parse_bill(text)
        self.assertEqual([r['type'] for r in rows], ['payment', 'refund'])
        self.assertEqual(rows[1]['amount_fen'], 100)

    @override_settings(ALLOW_FAKE=False)
    def test_fake_adapter_refused(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            FakeAdapter()
