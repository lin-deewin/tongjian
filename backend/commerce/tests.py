import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings, Client
from django.utils import timezone
from config.http import Problem
from payments.adapters import PaymentResult, RefundResult, ProviderError
from payments.models import FakeTransaction, FakeRefund
from testutils import ContentFixture
from .models import Order, Payment, AccessGrant, Refund
from .services import create_order, confirm_payment, confirm_refund, request_refund, reconcile_order, reconcile_refund

class CommerceTests(ContentFixture, TestCase):
    def setUp(self):
        self.create_fixture()

    def paid(self):
        order = self.new_order()
        return confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1'))

    def test_order_price_and_idempotency(self):
        key = uuid.uuid4().hex
        first = self.new_order(key=key)
        second = self.new_order(key=key)
        third = self.new_order()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.pk, third.pk)
        self.assertEqual(first.amount_fen, 100)
        with self.assertRaises(Problem):
            self.new_order(scene='h5', key=key)

    @override_settings(PAYMENT_PROVIDER='wechat', ALLOW_FAKE=True, LIVE_READY=False)
    def test_development_does_not_enable_real_test_product_charges(self):
        with self.assertRaises(Problem):
            create_order(self.user, 'truth', 1, 'native', uuid.uuid4().hex, '127.0.0.1')
        self.assertFalse(Order.objects.exists())

    def test_controlled_merchant_verification_only_approved_buyer_and_price(self):
        from pathlib import Path
        path = Path(self.directory.name) / 'gates.json'
        path.write_text(json.dumps({key: {'passed': True, 'evidence': 'test-only', 'verified_by': 'test'}
            for key in ['merchant_products', 'price_and_terms', 'email_delivery']}))
        self.product.terms_version = 'verification-v1'
        self.product.save()
        with override_settings(PAYMENT_PROVIDER='wechat', SALES_ENABLED=False, LIVE_READY=False,
            PAYMENT_VERIFICATION_ENABLED=True, PAYMENT_VERIFICATION_BUYERS=[self.user.email],
            PAYMENT_VERIFICATION_PRICE_FEN=100, LAUNCH_GATES_FILE=str(path)):
            order = create_order(self.user, 'truth', 1, 'native', uuid.uuid4().hex, '127.0.0.1')
            self.assertEqual(order.provider, 'wechat')
            with self.assertRaises(Problem):
                create_order(self.other, 'truth', 1, 'native', uuid.uuid4().hex, '127.0.0.1')
            with override_settings(PAYMENT_VERIFICATION_PRICE_FEN=1):
                with self.assertRaises(Problem):
                    create_order(self.user, 'truth', 1, 'native', uuid.uuid4().hex, '127.0.0.1')

    def test_stale_revision_and_bad_scene(self):
        for revision, scene in [(0, 'native'), (1, 'jsapi')]:
            with self.assertRaises(Problem):
                create_order(self.user, 'truth', revision, scene, uuid.uuid4().hex, '127.0.0.1')
        self.assertEqual(Order.objects.count(), 0)

    def test_stale_admin_form_still_increments_quote_revision(self):
        from django.contrib.admin import AdminSite
        from django.test import RequestFactory
        from .admin import ProductAdmin
        from .models import Product
        first = Product.objects.get(pk=self.product.pk)
        second = Product.objects.get(pk=self.product.pk)
        request = RequestFactory().get('/tongjian/admin/')
        request.user = self.staff
        editor = ProductAdmin(Product, AdminSite())
        first.price_fen = 200
        editor.save_model(request, first, None, True)
        second.price_fen = 300
        editor.save_model(request, second, None, True)
        self.product.refresh_from_db()
        self.assertEqual(self.product.revision, 3)
        with self.assertRaises(Problem) as context:
            create_order(self.user, 'truth', 2, 'native', uuid.uuid4().hex, '127.0.0.1')
        self.assertEqual(context.exception.code, 'price_changed')

    def test_verified_external_full_refund_before_payment_does_not_unlock(self):
        order = self.new_order()
        confirm_refund('fake', RefundResult('external-refund', order.merchant_number, 'succeeded', 100))
        confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1'))
        self.assertFalse(AccessGrant.objects.get(order=order).active)
        self.assertEqual(Refund.objects.get(order=order).status, 'succeeded')

    @override_settings(SALES_ENABLED=False)
    def test_sales_closed(self):
        with self.assertRaises(Problem):
            self.new_order()

    def test_missing_content_blocks_order(self):
        (self.product.current_version.relative_directory)
        from pathlib import Path
        Path(self.directory.name, 'truth/test/reader.pdf').unlink()
        with self.assertRaises(Problem):
            self.new_order()
        self.assertEqual(Order.objects.count(), 0)

    def test_duplicate_success_grants_once(self):
        order = self.paid()
        confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1'))
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AccessGrant.objects.count(), 1)
        with self.assertRaises(Problem):
            self.new_order()

    def test_amount_currency_identity_mismatch(self):
        order = self.new_order()
        for result in [PaymentResult(order.merchant_number, 'SUCCESS', 99, 'x'),
                       PaymentResult(order.merchant_number, 'SUCCESS', 100, 'x', 'USD'),
                       PaymentResult('unknown', 'SUCCESS', 100, 'x'),
                       PaymentResult(order.merchant_number, 'SUCCESS', True, 'x')]:
            with self.assertRaises(Problem):
                confirm_payment('fake', result)
        self.assertEqual(AccessGrant.objects.count(), 0)

    def test_frontend_success_does_not_unlock(self):
        order = self.new_order()
        self.client.force_login(self.user)
        self.client.get(f'/tongjian/api/v1/orders/{order.pk}/?success=true')
        self.assertFalse(AccessGrant.objects.exists())

    def test_expired_order_requires_channel_close(self):
        order = self.new_order()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        updated = reconcile_order(order, force=True)
        self.assertEqual(updated.status, 'CLOSED')

    def test_query_timeout_leaves_pending(self):
        order = self.new_order()
        with patch('payments.adapters.FakeAdapter.query_payment', side_effect=ProviderError('network')):
            updated = reconcile_order(order, force=True)
        self.assertEqual(updated.status, 'PENDING')
        self.assertGreater(updated.query_failures, 0)

    def test_order_creation_timeout_preserves_number(self):
        with patch('payments.adapters.FakeAdapter.create_payment', side_effect=ProviderError('timeout')):
            order = self.new_order()
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(order.status, 'PENDING')
        self.assertEqual(self.new_order().pk, order.pk)

    def test_query_cooldown(self):
        order = self.new_order()
        with patch('payments.adapters.FakeAdapter.query_payment', wraps=__import__('payments.adapters', fromlist=['FakeAdapter']).FakeAdapter().query_payment) as query:
            reconcile_order(order)
            reconcile_order(order)
            self.assertEqual(query.call_count, 1)

    def test_refund_processing_failure_success_and_late_payment(self):
        order = self.paid()
        refund = request_refund(order, self.staff, '用户申请退款')
        self.assertEqual(refund.status, 'processing')
        self.assertTrue(AccessGrant.objects.get(order=order).active)
        confirm_refund('fake', RefundResult(refund.merchant_number, order.merchant_number, 'failed', 100))
        self.assertTrue(AccessGrant.objects.get(order=order).active)
        confirm_refund('fake', RefundResult(refund.merchant_number, order.merchant_number, 'succeeded', 100))
        confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1'))
        confirm_refund('fake', RefundResult(refund.merchant_number, order.merchant_number, 'processing', 100))
        self.assertFalse(AccessGrant.objects.get(order=order).active)
        self.assertEqual(Refund.objects.get().status, 'succeeded')

    def test_refund_does_not_revoke_manual_grant(self):
        order = self.paid()
        manual = AccessGrant.objects.create(user=self.user, product=self.product, reason='人工补发')
        refund = request_refund(order, self.staff, '测试退款')
        confirm_refund('fake', RefundResult(refund.merchant_number, order.merchant_number, 'succeeded', 100))
        manual.refresh_from_db()
        self.assertTrue(manual.active)

    def test_refund_retry_reuses_number(self):
        order = self.paid()
        first = request_refund(order, self.staff, '测试退款')
        self.assertEqual(first.pk, request_refund(order, self.staff, '重试').pk)
        self.assertEqual(FakeRefund.objects.count(), 1)

    def test_refund_rejects_unpaid_wrong_amount_and_nonstaff(self):
        order = self.new_order()
        with self.assertRaises(Problem):
            request_refund(order, self.staff, '未付款')
        with self.assertRaises(Problem):
            request_refund(order, self.user, '非管理员')
        order = self.paid()
        refund = request_refund(order, self.staff, '测试')
        with self.assertRaises(Problem):
            confirm_refund('fake', RefundResult(refund.merchant_number, order.merchant_number, 'succeeded', 99))

    def test_anonymous_unowned_owned_download_article_and_cache(self):
        url = '/tongjian/api/v1/products/truth/download/'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get('/tongjian/article/truth/').status_code, 302)
        self.paid()
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        article = self.client.get('/tongjian/article/truth/')
        self.assertContains(article, 'private-paid-analysis-marker')
        self.assertEqual(article['Cache-Control'], 'private, no-store')

    def test_other_user_order_hidden(self):
        order = self.new_order()
        self.client.force_login(self.other)
        response = self.client.get(f'/tongjian/api/v1/orders/{order.pk}/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'not_found')

    def test_api_rejects_price_and_requires_terms(self):
        self.client.force_login(self.user)
        for extra in [{'amount_fen': 1, 'accept_terms': True}, {'accept_terms': False}]:
            response = self.client.post('/tongjian/api/v1/orders/', {'product': 'truth', 'revision': 1, 'scene': 'native', **extra},
                content_type='application/json', HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex)
            self.assertEqual(response.status_code, 400)

    def test_h5_in_wechat_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post('/tongjian/api/v1/orders/', {'product': 'truth', 'revision': 1, 'scene': 'h5', 'accept_terms': True},
            content_type='application/json', HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex, HTTP_USER_AGENT='MicroMessenger')
        self.assertEqual(response.status_code, 400)

    @override_settings(ALLOW_FAKE=False)
    def test_fake_endpoint_disabled(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(f'/tongjian/api/v1/orders/{uuid.uuid4()}/simulate/', {}, content_type='application/json').status_code, 404)

    def test_fake_endpoint_not_available_to_nonloopback_peer(self):
        order = self.new_order()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(f'/tongjian/api/v1/orders/{order.pk}/simulate/', {}, content_type='application/json', REMOTE_ADDR='203.0.113.2').status_code, 404)

    def test_admin_requires_password_reauthentication_for_refund(self):
        order = self.paid()
        self.client.force_login(self.staff)
        url = f'/tongjian/admin/commerce/order/{order.pk}/refund/'
        self.assertEqual(self.client.post(url, {'reason': '测试', 'password': 'wrong'}).status_code, 200)
        self.assertFalse(Refund.objects.exists())
        self.assertEqual(self.client.post(url, {'reason': '测试', 'password': 'test-strong-password'}).status_code, 302)
        self.assertTrue(Refund.objects.exists())

    def test_admin_network_and_forwarded_header(self):
        self.client.force_login(self.staff)
        response = self.client.get('/tongjian/admin/', REMOTE_ADDR='203.0.113.2', HTTP_X_REAL_IP='127.0.0.1')
        self.assertEqual(response.status_code, 403)

class ConcurrentCommerceTests(ContentFixture, TransactionTestCase):
    def setUp(self):
        self.create_fixture()

    def parallel(self, action):
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            barrier.wait()
            try:
                return action()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(2) as pool:
            return list(pool.map(lambda _: worker(), range(2)))

    def test_parallel_orders_one_pending(self):
        results = self.parallel(lambda: self.new_order().pk)
        self.assertEqual(results[0], results[1])
        self.assertEqual(Order.objects.count(), 1)

    def test_parallel_payment_confirmation_one_grant(self):
        order = self.new_order()
        self.parallel(lambda: confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1')).pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AccessGrant.objects.count(), 1)

    def test_pending_order_retry_races_confirmation_without_fk_deadlock(self):
        order = self.new_order()
        barrier = Barrier(2)
        def retry():
            close_old_connections(); barrier.wait()
            try:
                return create_order(self.user, 'truth', 1, 'native', uuid.uuid4().hex, '127.0.0.1').pk
            except Problem as exc:
                self.assertEqual(exc.code, 'already_owned')
            finally:
                close_old_connections()
        def payment():
            close_old_connections(); barrier.wait()
            try: return confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1')).pk
            finally: close_old_connections()
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(retry), pool.submit(payment)]
            for future in futures: future.result(timeout=15)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(AccessGrant.objects.count(), 1)

    def test_refund_success_races_payment_confirmation(self):
        order = self.new_order()
        confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1'))
        refund = request_refund(order, self.staff, '测试')
        barrier = Barrier(2)
        def refund_worker():
            close_old_connections(); barrier.wait()
            try: confirm_refund('fake', RefundResult(refund.merchant_number, order.merchant_number, 'succeeded', 100))
            finally: close_old_connections()
        def payment_worker():
            close_old_connections(); barrier.wait()
            try: confirm_payment('fake', PaymentResult(order.merchant_number, 'SUCCESS', 100, 'payment-1'))
            finally: close_old_connections()
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(refund_worker), pool.submit(payment_worker)]
            for future in futures: future.result()
        self.assertFalse(AccessGrant.objects.get(order=order).active)
