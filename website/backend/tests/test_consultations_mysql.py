"""Normal website accounts and real isolated MySQL. Never contacts an SMS provider."""
import os
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch
from cryptography.fernet import Fernet
from sqlalchemy import select, delete, func
from test_auth_mysql import WebsiteAuthCase
from website_app import consultations as leads
from website_app.auth import WebsiteUser, hash_password
from website_app.integrations.routes import WebsiteLeadRequest, WebsiteRate

class ConsultationStory(WebsiteAuthCase):
    def setUp(self):
        super().setUp()
        self.env = patch.dict(os.environ, {'WEBSITE_CONSULTATION_ENABLED':'true',
            'WEBSITE_CONSULTATION_KEY':Fernet.generate_key().decode(), 'WEBSITE_LEAD_RATE_SALT':uuid4().hex+uuid4().hex,
            'WEBSITE_SMS_ENABLED':'false'})
        self.env.start();self.addCleanup(self.env.stop)
        with self.factory() as db:
            db.execute(delete(leads.Consultation));db.execute(delete(WebsiteRate))
            db.add(WebsiteUser(id=uuid4().hex,username='superadmin',display_name='隔离测试超级管理员',role='superadmin',active=True,password_hash=hash_password(self.password)))
            db.commit()
        self.form={'school_name':'虚构咨询验收单位','contact_name':'合成联系人','phone':'13800000000',
            'interest':'教务系统','message':'仅用于隔离验收，不联系任何真实客户',
            'consent':True,'request_id':uuid4().hex,'source_path':'/contact'}

    def submit(self, **changes):
        return self.client.post('/api/notification/website-lead',json={**self.form,**changes})

    def test_registration_encrypted_idempotent_and_transaction_failure(self):
        with patch('website_app.integrations.routes.send_lead') as sms:
            first=self.submit();self.assertEqual(first.status_code,200,first.text)
            result=first.json()['data'];self.assertEqual(result['mode'],'registered');self.assertEqual(result['retentionDays'],90)
            self.assertEqual(self.submit().json()['data']['receipt'],result['receipt'])
            self.assertEqual(self.submit(message='同一登记号发生变化').status_code,409);sms.assert_not_called()
        with self.factory() as db:
            row=db.get(leads.Consultation,result['receipt'])
            self.assertNotIn(self.form['phone'],row.private_data);self.assertNotIn(self.form['school_name'],row.private_data)
            self.assertTrue(row.private_data.startswith('w1:'));self.assertEqual(row.phone_mask,'138****0000')
            self.assertEqual(row.expires_at-row.created_at,timedelta(days=90))
            self.assertEqual(db.scalar(select(func.count()).select_from(leads.Consultation)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(leads.ConsultationAudit)),1)
        with patch.object(leads,'audit',side_effect=RuntimeError('isolated failure')):
            with self.assertRaises(RuntimeError):self.submit(request_id=uuid4().hex)
        with self.factory() as db:self.assertEqual(db.scalar(select(func.count()).select_from(leads.Consultation)),1)

    def test_superadmin_only_masked_list_detail_audit_csrf_and_note_conflict(self):
        result=self.submit().json()['data'];cid=result['receipt'];base='/api/manage/consultations'
        self.assertEqual(self.client.get(base).status_code,401)
        self.assertEqual(self.client.get(base,headers={'Authorization':'Bearer student-system-token'}).status_code,401)
        for role in ('editor','publisher'):
            self.login(role)
            for path in (base,base+'/'+cid):self.assertEqual(self.client.get(path).status_code,403)
            self.assertEqual(self.client.put(base+'/'+cid+'/note',json={'expectedVersion':0,'note':'越权'}).status_code,403)
            self.client.post('/api/auth/logout')
        self.login('superadmin')
        listing=self.client.get(base);self.assertEqual(listing.status_code,200,listing.text)
        self.assertEqual(listing.json()['data']['items'][0]['phone'],'138****0000')
        self.assertNotIn(self.form['phone'],listing.text);self.assertEqual(listing.headers['cache-control'],'no-store')
        row=self.client.get(base+'/'+cid).json()['data'];self.assertEqual(row['phone'],self.form['phone'])
        body={'expectedVersion':row['version'],'note':'合成跟进备注，无真实数据'}
        self.assertEqual(self.client.put(base+'/'+cid+'/note',json=body,headers={'X-Website-CSRF':'invalid'}).status_code,403)
        saved=self.client.put(base+'/'+cid+'/note',json=body);self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.client.put(base+'/'+cid+'/note',json={**body,'note':'旧版本改写'}).status_code,409)
        self.assertEqual(self.client.get(base+'/'+cid).json()['data']['note'],body['note'])
        with self.factory() as db:
            row=db.get(leads.Consultation,cid);self.assertNotIn(body['note'],row.private_data)
            events=list(db.scalars(select(leads.ConsultationAudit).where(leads.ConsultationAudit.consultation_id==cid)))
            self.assertTrue({'REGISTER','READ_LIST','READ_DETAIL','UPDATE_NOTE'}<=set(event.action for event in events))
        self.client.post('/api/auth/logout');self.assertEqual(self.client.get(base+'/'+cid).status_code,401)

    def test_expiry_blocks_access_then_bounded_cleanup_cascades(self):
        with self.factory() as db:
            past=leads.register(db,WebsiteLeadRequest(**self.form),datetime.utcnow()-timedelta(days=91));db.commit()
        fresh=self.submit(request_id=uuid4().hex).json()['data']
        self.login('superadmin');base='/api/manage/consultations'
        self.assertEqual(self.client.get(base+'/'+past['receipt']).status_code,404)
        self.assertEqual(self.client.put(base+'/'+past['receipt']+'/note',json={'expectedVersion':0,'note':'已到期'}).status_code,404)
        self.assertEqual(self.client.get(base).json()['data']['total'],1)
        with self.factory() as db:
            self.assertEqual(leads.purge_expired(db,limit=1),1);db.commit()
            self.assertIsNone(db.get(leads.Consultation,past['receipt']))
            self.assertIsNotNone(db.get(leads.Consultation,fresh['receipt']))
            self.assertEqual(db.scalar(select(func.count()).select_from(leads.ConsultationAudit).where(leads.ConsultationAudit.consultation_id==past['receipt'])),0)
            self.assertEqual(leads.purge_expired(db),0)

    def test_configuration_consent_source_origin_and_rate_fail_closed(self):
        self.assertEqual(self.submit(consent=False).status_code,400)
        self.assertEqual(self.submit(interest='未经公开的产品').status_code,400)
        self.assertEqual(self.submit(source_article=uuid4().hex).status_code,400)
        self.assertEqual(self.client.post('/api/notification/website-lead',json=self.form,headers={'Origin':'https://attacker.invalid'}).status_code,403)
        with patch.dict(os.environ,{'WEBSITE_CONSULTATION_KEY':''}):
            self.assertEqual(self.client.get('/api/notification/website-lead-capabilities').json()['data']['mode'],'unavailable')
            self.assertEqual(self.submit().status_code,503)
        with self.factory() as db:
            db.execute(delete(WebsiteRate));admin=db.scalar(select(WebsiteUser).where(WebsiteUser.username=='superadmin'));admin.active=False;db.commit()
        self.assertEqual(self.submit().status_code,503)
        with self.factory() as db:
            admin=db.scalar(select(WebsiteUser).where(WebsiteUser.username=='superadmin'));admin.active=True;db.execute(delete(WebsiteRate));db.commit()
        for _ in range(6):self.assertEqual(self.submit(request_id=uuid4().hex).status_code,200)
        self.assertEqual(self.submit(request_id=uuid4().hex).status_code,429)

    def test_wrong_key_never_returns_plaintext_and_disabled_purge_changes_nothing(self):
        cid=self.submit().json()['data']['receipt'];self.login('superadmin')
        with patch.dict(os.environ,{'WEBSITE_CONSULTATION_KEY':Fernet.generate_key().decode()}):
            response=self.client.get('/api/manage/consultations/'+cid);self.assertEqual(response.status_code,503)
            self.assertNotIn(self.form['phone'],response.text)
        with patch.dict(os.environ,{'WEBSITE_CONSULTATION_ENABLED':'false'}),self.factory() as db:
            self.assertEqual(leads.purge_expired(db,datetime.utcnow()+timedelta(days=100)),0)
            self.assertIsNotNone(db.get(leads.Consultation,cid))
