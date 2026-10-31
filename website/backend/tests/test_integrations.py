import hashlib
import os
import secrets
import unittest
from unittest.mock import patch
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, func
from website_app.main import app
from website_app.db import database_url, get_sessionmaker
from website_app.integrations import routes, wechat

class WebsiteIntegrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('WEBSITE_TEST_REQUIRED') != 'true' or not database_url().database.startswith('test_website_'): raise RuntimeError('仅限官网隔离测试库')
        command.upgrade(Config('alembic.ini'),'head')

    def setUp(self):
        with get_sessionmaker()() as db: db.execute(delete(routes.WebsiteRate));db.commit()
        self.client=TestClient(app);self.client.headers['Origin']=os.environ['WEBSITE_ORIGIN']
        self.form={'school_name':'虚构咨询测试学校','contact_name':'测试联系人','phone':'13800000000','interest':'学生管理','message':'仅用于隔离测试，不发送真实短信'}
        wechat._reset_local_cache_for_tests()

    def tearDown(self): self.client.close()

    def test_disabled_or_failed_sms_never_reports_sent(self):
        with patch.dict(os.environ,{'WEBSITE_SMS_ENABLED':'false'}), patch.object(routes,'send_lead') as sender:
            r=self.client.post('/api/notification/website-lead',json=self.form)
            self.assertEqual(r.status_code,503);self.assertIsNone(r.json()['data']);sender.assert_not_called()
        with patch.dict(os.environ,{'WEBSITE_SMS_ENABLED':'true','WEBSITE_LEAD_RATE_SALT':secrets.token_hex(32)}), patch.object(routes,'send_lead',return_value=False):
            self.assertEqual(self.client.post('/api/notification/website-lead',json=self.form).status_code,503)

    def test_lead_shared_rate_limit_source_and_minimal_storage(self):
        with patch.dict(os.environ,{'WEBSITE_SMS_ENABLED':'true','WEBSITE_LEAD_RATE_SALT':secrets.token_hex(32)}), patch.object(routes,'send_lead',return_value=True) as sender:
            bad=self.client.post('/api/notification/website-lead',json=self.form,headers={'Origin':'https://attacker.invalid'})
            self.assertEqual(bad.status_code,403);sender.assert_not_called()
            for _ in range(6):
                response=self.client.post('/api/notification/website-lead',json=self.form)
                self.assertEqual(response.status_code,200,response.text)
                self.assertTrue(response.json()['data']['accepted'])
            self.assertEqual(self.client.post('/api/notification/website-lead',json=self.form).status_code,429)
            self.assertEqual(sender.call_count,6)
        with get_sessionmaker()() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(routes.WebsiteRate)),1)
            row=db.scalar(select(routes.WebsiteRate));self.assertEqual(row.attempts,6);self.assertEqual(len(row.key),64)
            self.assertNotIn('13800000000',row.key)

    def test_wechat_disabled_independently_of_student_configuration(self):
        with patch.dict(os.environ,{'WEBSITE_WECHAT_OFFICIAL_JS_SDK_ENABLED':'false','WECHAT_OFFICIAL_JS_SDK_ENABLED':'true'}):
            r=self.client.get('/api/notification/website-wechat-signature',params={'url':'https://www.hnyueke.com/'})
            self.assertEqual(r.json()['data'],{'enabled':False})

    def test_wechat_signature_scope_and_algorithm(self):
        with patch.dict(os.environ,{'WEBSITE_WECHAT_OFFICIAL_APP_ID':'isolated-test-app','WEBSITE_WECHAT_OFFICIAL_APP_SECRET':secrets.token_hex(20)}), patch.object(wechat,'get_jsapi_ticket',return_value='test-ticket'):
            r=wechat.build_js_sdk_signature('https://www.hnyueke.com/products/internship#screens',timestamp=1787358000,nonce_str='test-nonce')
            expected='jsapi_ticket=test-ticket&noncestr=test-nonce&timestamp=1787358000&url=https://www.hnyueke.com/products/internship'
            self.assertEqual(r['signature'],hashlib.sha1(expected.encode()).hexdigest())
            for address in ['http://www.hnyueke.com/','https://attacker.example/','https://user:password@www.hnyueke.com/']:
                with self.assertRaises(ValueError): wechat.normalize_signable_url(address)
            self.assertNotIn('secret',str(r))
