from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase
from django.utils import timezone
from PIL import Image

from . import captcha
from .models import GraphicChallenge


class GraphicCaptchaTests(TestCase):
    url = '/tongjian/account/register/'
    refresh = '/tongjian/account/captcha/refresh/'

    def challenge(self, client=None):
        client = client or self.client
        with patch('accounts.captcha.new_code', return_value='ABCD'):
            response = client.get(self.url)
        return response.context['captcha_form'].initial['captcha_id'], response

    def send(self, identifier, answer='abcd', client=None):
        return (client or self.client).post(self.url, {'action': 'send_code',
            'email': 'reader@example.com', 'captcha_id': str(identifier), 'captcha': answer})

    def test_image_is_private_png_without_plaintext_answer(self):
        identifier, page = self.challenge()
        self.assertNotContains(page, 'ABCD')
        row = GraphicChallenge.objects.get(pk=identifier)
        self.assertNotEqual(row.answer_digest, 'ABCD')
        response = self.client.get(page.context['captcha_image_url'])
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(Image.open(BytesIO(response.content)).size, (176, 56))
        self.assertEqual(Client().get(page.context['captcha_image_url']).status_code, 404)

    def test_wrong_answer_consumes_challenge_and_cannot_send_email(self):
        identifier, _ = self.challenge()
        self.assertContains(self.send(identifier, 'ZZZZ'), '图形验证码不正确或已过期')
        self.send(identifier)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNotNone(GraphicChallenge.objects.get(pk=identifier).consumed_at)

    def test_success_is_case_insensitive_and_cannot_be_replayed(self):
        identifier, _ = self.challenge()
        self.assertContains(self.send(identifier), 'registration-sent')
        self.assertEqual(len(mail.outbox), 1)
        self.send(identifier)
        self.assertEqual(len(mail.outbox), 1)

    def test_expired_image_cannot_send(self):
        identifier, _ = self.challenge()
        GraphicChallenge.objects.filter(pk=identifier).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.send(identifier)
        self.assertEqual(len(mail.outbox), 0)

    def test_stolen_challenge_cannot_be_used_or_invalidated_by_another_session(self):
        identifier, _ = self.challenge()
        other = Client()
        self.challenge(other)
        self.send(identifier, client=other)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(GraphicChallenge.objects.get(pk=identifier).consumed_at)
        self.send(identifier)
        self.assertEqual(len(mail.outbox), 1)

    def test_refresh_requires_csrf_and_post_and_invalidates_previous(self):
        client = Client(enforce_csrf_checks=True)
        identifier, page = self.challenge(client)
        self.assertEqual(client.get(self.refresh).status_code, 405)
        self.assertEqual(client.post(self.refresh, {}).status_code, 403)
        response = client.post(self.refresh, {'captcha_id': str(identifier)},
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()['id'], str(identifier))
        self.assertEqual(client.get(page.context['captcha_image_url']).status_code, 404)
        self.assertEqual(client.get(response.json()['image_url']).status_code, 200)

    def test_missing_graphic_prevents_mail_and_proof_is_bound_to_email_and_expiry(self):
        self.client.post(self.url, {'action': 'send_code', 'email': 'reader@example.com'})
        self.assertEqual(len(mail.outbox), 0)
        request = type('Request', (), {'session': {}})()
        captcha.remember(request, 'reader@example.com')
        self.assertTrue(captcha.verified(request, 'reader@example.com'))
        self.assertFalse(captcha.verified(request, 'other@example.com'))
        request.session[captcha.PROOF_KEY]['expires'] = 0
        self.assertFalse(captcha.verified(request, 'reader@example.com'))
