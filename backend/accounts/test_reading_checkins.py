import json
from uuid import uuid4
from django.test import TestCase, Client
from .models import User, ReadingCheckin

class ReadingCheckinTests(TestCase):
    def setUp(self):
        self.a=User.objects.create_user('a-years@example.com','password')
        self.b=User.objects.create_user('b-years@example.com','password')
        self.url='/api/v1/me/reading-checkins/'

    def entry(self, year=403, volume=1):
        return {'id':str(uuid4()),'year':year,'volume':volume,'day':'2026-10-21'}

    def post(self, entries, user=None):
        return self.client.post(self.url,json.dumps({'user_id':str((user or self.a).pk),'entries':entries}),content_type='application/json')

    def test_repeated_year_and_retry_and_cross_volume(self):
        self.client.force_login(self.a)
        first=self.entry()
        self.post([first]);self.post([first])
        result=self.post([self.entry(),self.entry(403,2),self.entry(402)]).json()
        self.assertEqual(len(result['entries']),4)
        self.assertEqual(result['unique_years'],2)
        self.assertEqual(result['rank'],1)
        self.assertEqual(result['participants'],1)
        device=Client();device.force_login(self.a)
        self.assertEqual(device.get(self.url).json()['unique_years'],2)

    def test_rank_ties_and_isolation(self):
        self.client.force_login(self.a);self.post([self.entry(),self.entry(402)])
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(self.url).json()['entries'],[])
        self.assertEqual(self.post([self.entry()]).status_code,409)
        result=self.post([self.entry()],self.b).json()
        self.assertEqual((result['rank'],result['participants']),(2,2))
        result=self.post([self.entry(402)],self.b).json()
        self.assertEqual(result['rank'],1)
        self.assertNotIn('email',str(result))

    def test_validation_atomic_auth_and_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code,401)
        self.client.force_login(self.a)
        for invalid in [self.entry(0),self.entry(-960),self.entry(404),self.entry(True),self.entry(403,295),dict(self.entry(),day='2026-02-30'),dict(self.entry(),id='invalid')]:
            self.assertEqual(self.post([self.entry(),invalid]).status_code,400)
        self.assertEqual(ReadingCheckin.objects.count(),0)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.a)
        self.assertEqual(csrf.post(self.url,json.dumps({'entries':[],'user_id':str(self.a.pk)}),content_type='application/json').status_code,403)
