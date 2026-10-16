"""Direct merchant APIv3. Trust configured platform public keys, never a key from a notification."""
import base64
import csv
import hashlib
import io
import json
import secrets
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode, urlsplit, quote

import httpx
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from .adapters import PaymentResult, RefundResult, ProviderError, ProviderRejected, InvalidNotification

class WeChatAdapter:
    base_url = 'https://api.mch.weixin.qq.com'

    def __init__(self):
        config = settings.WECHAT
        try:
            if not all(config.values()) or len(config['API_V3_KEY'].encode()) != 32:
                raise ValueError('Incomplete configuration')
            self.config = config
            self.private_key = serialization.load_pem_private_key(Path(config['PRIVATE_KEY_FILE']).read_bytes(), password=None)
            paths = json.loads(Path(config['PUBLIC_KEYS_FILE']).read_text())
            self.public_keys = {serial: serialization.load_pem_public_key(Path(path).read_bytes()) for serial, path in paths.items()}
            if not self.public_keys:
                raise ValueError('Empty keyring')
        except (OSError, ValueError, TypeError) as exc:
            raise ProviderRejected('WeChat credentials are not configured') from exc

    def _verify(self, raw, headers):
        try:
            serial = headers.get('Wechatpay-Serial', '')
            timestamp, nonce = headers['Wechatpay-Timestamp'], headers['Wechatpay-Nonce']
            if abs(time.time() - int(timestamp)) > 300 or serial not in self.public_keys:
                raise ValueError('Untrusted signature metadata')
            signature = base64.b64decode(headers['Wechatpay-Signature'], validate=True)
            self.public_keys[serial].verify(signature, timestamp.encode() + b'\n' + nonce.encode() + b'\n' + raw + b'\n',
                                            padding.PKCS1v15(), hashes.SHA256())
        except (KeyError, ValueError, InvalidSignature) as exc:
            raise InvalidNotification('Invalid platform signature') from exc

    def _request(self, method, path, payload=None, download=False):
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode() if payload is not None else b''
        timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
        canonical = f'{method}\n{path}\n{timestamp}\n{nonce}\n'.encode() + raw + b'\n'
        signature = base64.b64encode(self.private_key.sign(canonical, padding.PKCS1v15(), hashes.SHA256())).decode()
        auth = f'WECHATPAY2-SHA256-RSA2048 mchid="{self.config["MCH_ID"]}",nonce_str="{nonce}",timestamp="{timestamp}",serial_no="{self.config["MERCHANT_SERIAL"]}",signature="{signature}"'
        try:
            response = httpx.request(method, self.base_url + path, content=raw,
                headers={'Authorization': auth, 'Accept': 'application/json', 'Content-Type': 'application/json',
                         'User-Agent': 'TongjianCommerce/1.0'}, timeout=httpx.Timeout(5, connect=3), follow_redirects=False)
            if not download:
                self._verify(response.content, response.headers)
            if response.status_code >= 400:
                if response.status_code >= 500 or response.status_code == 429:
                    raise ProviderError('Channel temporarily unavailable')
                raise ProviderRejected('Channel rejected request', response.json().get('code', ''))
            return response.content if download else (response.json() if response.content else {})
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError('Channel result is unknown') from exc

    def create_payment(self, order):
        if order.scene not in {'native', 'h5'}:
            raise ProviderRejected('Unsupported scene')
        payload = {'appid': self.config['APP_ID'], 'mchid': self.config['MCH_ID'], 'description': order.title[:127],
                   'out_trade_no': order.merchant_number,
                   'time_expire': order.expires_at.isoformat(timespec='seconds'),
                   'notify_url': settings.SITE_URL + '/api/v1/payments/wechat/notify/',
                   'amount': {'total': order.amount_fen, 'currency': order.currency}}
        if order.scene == 'h5':
            payload['scene_info'] = {'payer_client_ip': order.client_ip, 'h5_info': {'type': 'Wap'}}
        data = self._request('POST', '/v3/pay/transactions/' + order.scene, payload)
        if order.scene == 'native':
            if not data.get('code_url', '').startswith('weixin://'):
                raise ProviderError('Missing payment code')
            return {'kind': 'native', 'code_url': data['code_url']}
        target = data.get('h5_url', '')
        if urlsplit(target).scheme != 'https' or urlsplit(target).hostname != 'wx.tenpay.com':
            raise ProviderError('Unexpected payment URL')
        return {'kind': 'h5', 'url': target + '&' + urlencode({'redirect_url': settings.SITE_URL + f'/checkout/{order.pk}/'})}

    def _payment(self, data, event_id=''):
        if data.get('mchid') != self.config['MCH_ID'] or data.get('appid') != self.config['APP_ID']:
            raise InvalidNotification('Unexpected merchant identity')
        states = {'SUCCESS': 'SUCCESS', 'NOTPAY': 'PENDING', 'USERPAYING': 'PENDING', 'CLOSED': 'CLOSED', 'REVOKED': 'CLOSED', 'PAYERROR': 'PENDING', 'REFUND': 'SUCCESS'}
        if data.get('trade_state') not in states:
            raise InvalidNotification('Unexpected trade state')
        amount = data.get('amount', {})
        return PaymentResult(data['out_trade_no'], states[data['trade_state']], amount.get('total'),
                             data.get('transaction_id', ''), amount.get('currency', ''), event_id, data.get('success_time', ''))

    def query_payment(self, order):
        path = '/v3/pay/transactions/out-trade-no/' + quote(order.merchant_number, safe='') + '?' + urlencode({'mchid': self.config['MCH_ID']})
        try:
            result = self._payment(self._request('GET', path))
            if result.state != 'SUCCESS' and result.amount_fen is None:
                result = replace(result, amount_fen=order.amount_fen, currency=order.currency)
            return result
        except ProviderRejected as exc:
            if exc.code == 'ORDER_NOT_EXIST':
                return PaymentResult(order.merchant_number, 'NOT_FOUND', order.amount_fen)
            raise

    def close_payment(self, order):
        self._request('POST', '/v3/pay/transactions/out-trade-no/' + quote(order.merchant_number, safe='') + '/close', {'mchid': self.config['MCH_ID']})
        return self.query_payment(order)

    def _notification(self, raw, headers, expected_type):
        self._verify(raw, headers)
        try:
            event = json.loads(raw)
            if event['event_type'] not in expected_type:
                raise ValueError('Wrong event type')
            resource = event['resource']
            if resource['algorithm'] != 'AEAD_AES_256_GCM':
                raise ValueError('Wrong encryption algorithm')
            plain = AESGCM(self.config['API_V3_KEY'].encode()).decrypt(resource['nonce'].encode(),
                base64.b64decode(resource['ciphertext'], validate=True), resource.get('associated_data', '').encode())
            return event['id'], json.loads(plain)
        except (KeyError, ValueError, InvalidTag, TypeError) as exc:
            raise InvalidNotification('Invalid encrypted notification') from exc

    def verify_payment_notification(self, raw, headers):
        event_id, data = self._notification(raw, headers, {'TRANSACTION.SUCCESS'})
        result = self._payment(data, event_id)
        if result.state != 'SUCCESS':
            raise InvalidNotification('Not a successful payment')
        return result

    def _refund(self, data, event_id=''):
        if 'mchid' in data and data['mchid'] != self.config['MCH_ID']:
            raise InvalidNotification('Wrong refund merchant')
        status = data.get('status', data.get('refund_status'))
        states = {'SUCCESS': 'succeeded', 'PROCESSING': 'processing', 'CLOSED': 'failed', 'ABNORMAL': 'failed'}
        if status not in states or data.get('amount', {}).get('currency', 'CNY') != 'CNY':
            raise InvalidNotification('Unexpected refund status')
        return RefundResult(data['out_refund_no'], data['out_trade_no'], states[status],
                            data['amount']['refund'], data.get('refund_id', ''), event_id, data.get('success_time', ''))

    def create_refund(self, refund):
        payload = {'out_trade_no': refund.order.merchant_number, 'out_refund_no': refund.merchant_number,
                   'reason': refund.reason[:80], 'notify_url': settings.SITE_URL + '/api/v1/payments/wechat/refund-notify/',
                   'amount': {'refund': refund.amount_fen, 'total': refund.order.amount_fen, 'currency': 'CNY'}}
        return self._refund(self._request('POST', '/v3/refund/domestic/refunds', payload))

    def query_refund(self, refund):
        return self._refund(self._request('GET', '/v3/refund/domestic/refunds/' + quote(refund.merchant_number, safe='')))

    def verify_refund_notification(self, raw, headers):
        event_id, data = self._notification(raw, headers, {'REFUND.SUCCESS', 'REFUND.CLOSED', 'REFUND.ABNORMAL'})
        if data.get('mchid') != self.config['MCH_ID']:
            raise InvalidNotification('Unexpected refund merchant identity')
        return self._refund(data, event_id)

    def fetch_bill(self, date):
        meta = self._request('GET', '/v3/bill/tradebill?' + urlencode({'bill_date': str(date), 'bill_type': 'ALL'}))
        parsed = urlsplit(meta['download_url'])
        if parsed.scheme != 'https' or parsed.hostname != 'api.mch.weixin.qq.com':
            raise ProviderError('Unexpected bill host')
        data = self._request('GET', parsed.path + ('?' + parsed.query if parsed.query else ''), download=True)
        algorithms = {'SHA1': hashlib.sha1, 'SHA256': hashlib.sha256}
        if meta.get('hash_type') not in algorithms or algorithms[meta['hash_type']](data).hexdigest() != meta.get('hash_value'):
            raise ProviderError('Bill checksum mismatch')
        return parse_bill(data.decode('utf-8-sig'))

def parse_bill(text):
    lines = text.splitlines()
    if not lines:
        raise ProviderError('Empty bill')
    reader = csv.DictReader(io.StringIO('\n'.join(lines)))
    required = {'商户订单号', '微信支付订单号', '交易状态'}
    reader.fieldnames = [name.strip('` \t') for name in (reader.fieldnames or [])]
    if not required.issubset(reader.fieldnames):
        raise ProviderError('Unsupported bill format')
    rows = []
    for raw in reader:
        row = {k: (v or '').strip('` \t') for k, v in raw.items() if k}
        if not row.get('商户订单号') or row.get('交易状态') not in {'SUCCESS', 'REFUND', '成功', '退款'}:
            continue
        amount = row.get('订单金额', row.get('总金额'))
        try:
            fen = Decimal(amount) * 100
            if fen != fen.to_integral_value():
                raise ValueError()
            rows.append({'order_number': row['商户订单号'], 'transaction_id': row['微信支付订单号'], 'amount_fen': int(fen), 'type': 'payment'})
            if row.get('商户退款单号'):
                refund_fen = Decimal(row.get('申请退款金额', row.get('退款金额'))) * 100
                if refund_fen != refund_fen.to_integral_value():
                    raise ValueError()
                rows.append({'order_number': row['商户订单号'], 'transaction_id': row.get('微信退款单号', ''),
                             'refund_number': row['商户退款单号'], 'amount_fen': int(refund_fen), 'type': 'refund'})
        except Exception as exc:
            raise ProviderError('Unsupported bill amount') from exc
    return rows
