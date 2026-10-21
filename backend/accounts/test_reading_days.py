import json
from django.test import TestCase, Client
from .models import User, ReadingDay

class ReadingDayTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('reading@example.com','password')
        self.other=User.objects.create_user('other-reading@example.com','password')
        self.url='/api/v1/me/reading-days/'

    def post(self, days, owner=None):
        return self.client.post(self.url, json.dumps({'days':days,'user_id':str(owner or self.user.pk)}), content_type='application/json')

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code,401)
        self.assertEqual(self.post(['2026-10-21']).status_code,401)

    def test_merge_unique_and_other_device(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post(['2026-10-20','2026-10-21','2026-10-20']).status_code,200)
        self.post(['2026-10-21'])
        device=Client();device.force_login(self.user)
        self.assertEqual(device.get(self.url).json()['days'],['2026-10-20','2026-10-21'])
        self.assertEqual(ReadingDay.objects.count(),2)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).json()['days'],[])
        self.assertEqual(self.post(['2026-10-21']).status_code,409)

    def test_invalid_input_is_atomic(self):
        self.client.force_login(self.user)
        for values in [['2026-10-21','2026-02-30'],['20261021'],[None], '2026-10-21', ['2026-10-21']*1001]:
            self.assertEqual(self.post(values).status_code,400)
        self.assertEqual(ReadingDay.objects.count(),0)

    def test_csrf_required(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url,json.dumps({'days':[],'user_id':str(self.user.pk)}),content_type='application/json').status_code,403)
        state=client.get('/api/v1/session/').json()
        self.assertEqual(client.post(self.url,json.dumps({'days':['2026-10-21'],'user_id':str(self.user.pk)}),content_type='application/json',HTTP_X_CSRFTOKEN=state['csrf_token']).status_code,200)
