"""Real independent MySQL and normal password login; no dependency overrides."""
import os
import secrets
import unittest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy import delete, select
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from website_app.db import database_url, get_sessionmaker
from website_app.main import app
from website_app.auth import WebsiteUser, WebsiteSession, LoginAttempt, AuthAudit, hash_password, COOKIE
from website_app.news.models import NewsArticle, NewsRevision, NewsMediaLink, NewsAudit, NewsPackage, NewsMedia, NewsDispatch
from website_app.news import service
from helpers import make_bundle

class WebsiteAuthCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('WEBSITE_TEST_REQUIRED') != 'true' or not database_url().database.startswith('test_website_'):
            raise RuntimeError('必须显式使用官网可清理测试数据库')
        command.upgrade(Config('alembic.ini'), 'head')
        cls.factory = get_sessionmaker()

    def setUp(self):
        with self.factory() as db:
            for model in (NewsMediaLink, NewsRevision, NewsArticle, NewsAudit, NewsPackage, NewsMedia, WebsiteSession, WebsiteUser, LoginAttempt, AuthAudit):
                db.execute(delete(model))
            gate = db.get(NewsDispatch, 1); gate.next_slot = None
            self.password = secrets.token_urlsafe(20)
            for role in ('editor', 'publisher'):
                db.add(WebsiteUser(id=uuid4().hex, username=role, display_name='隔离测试编辑', role=role, active=True, password_hash=hash_password(self.password)))
            db.commit()
        self.client = TestClient(app)
        self.client.headers['Origin'] = os.environ['WEBSITE_ORIGIN']

    def tearDown(self):
        self.client.close()

    def login(self, role='publisher', client=None):
        client = client or self.client
        r = client.post('/api/auth/login', json={'username': role, 'password': self.password})
        self.assertEqual(r.status_code, 200, r.text)
        client.headers['X-Website-CSRF'] = r.json()['data']['csrfToken']
        return r

class WebsiteAuthAndNews(WebsiteAuthCase):
    def test_login_revocation_csrf_and_student_token_rejection(self):
        self.assertEqual(self.client.get('/api/manage/news/packages', headers={'Authorization': 'Bearer student-system-token'}).status_code, 401)
        r = self.login()
        self.assertIn('HttpOnly', r.headers['set-cookie'])
        self.assertIn('SameSite=strict', r.headers['set-cookie'])
        old = self.client.cookies.get(COOKIE)
        self.assertEqual(self.client.get('/api/auth/session').status_code, 200)
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-Website-CSRF': 'wrong'}).status_code, 403)
        self.assertEqual(self.client.post('/api/auth/logout', headers={'Origin': 'https://attacker.invalid'}).status_code, 403)
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/session', headers={'Cookie': f'{COOKIE}={old}'}).status_code, 401)

    def test_disabled_user_revokes_old_session(self):
        self.login()
        with self.factory() as db:
            user = db.scalar(select(WebsiteUser).where(WebsiteUser.username == 'publisher')); user.active = False; db.commit()
        self.assertEqual(self.client.get('/api/manage/news/packages').status_code, 401)

    def test_login_rate_limit_and_origin(self):
        self.assertEqual(self.client.post('/api/auth/login', json={'username': 'publisher', 'password': self.password}, headers={'Origin': 'https://attacker.invalid'}).status_code, 403)
        for _ in range(10):
            self.assertEqual(self.client.post('/api/auth/login', json={'username': 'publisher', 'password': 'invalid'}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'username': 'publisher', 'password': self.password}).status_code, 429)

    def test_import_review_publish_public_sitemap_withdraw(self):
        self.login('editor')
        r = self.client.post('/api/manage/news/packages', files={'file': ('news.zip', make_bundle(1, prefix='Independent'), 'application/zip')})
        self.assertEqual(r.status_code, 200, r.text)
        package = r.json()['data']['package']; pid = package['id']
        detail = self.client.get(f'/api/manage/news/packages/{pid}').json()['data']
        article = detail['articles'][0]
        self.assertEqual(self.client.get(article['url']).status_code, 404)
        preview_url = f"/api/manage/news/articles/{article['id']}/preview"
        preview = self.client.get(preview_url)
        self.assertEqual(preview.status_code, 200)
        self.assertIn(article['title'], preview.text)
        self.assertIn('noindex', preview.headers['x-robots-tag'])
        with TestClient(app) as anonymous:
            self.assertEqual(anonymous.get(preview_url).status_code, 401)
        body = {'expectedVersion': package['version'], 'reviewDigest': package['reviewDigest'], 'confirmed': True, 'excludedIds': [], 'intervalMinutes': 1}
        self.assertEqual(self.client.post(f'/api/manage/news/packages/{pid}/confirm', json=body).status_code, 403)
        self.client.post('/api/auth/logout')
        self.login('publisher')
        self.assertEqual(self.client.post(f'/api/manage/news/packages/{pid}/confirm', json={**body, 'expectedVersion': 99}).status_code, 409)
        self.assertEqual(self.client.post(f'/api/manage/news/packages/{pid}/confirm', json=body).status_code, 200)
        # Same durable command as the worker; no direct updates to article state.
        with self.factory() as db:
            self.assertEqual(service.publish_due(db, datetime.utcnow()+timedelta(minutes=2)), 1); db.commit()
        self.assertEqual(self.client.get(article['url']).status_code, 200)
        self.assertIn(article['title'], self.client.get(article['url']).text)
        self.assertEqual(len(self.client.get('/api/news/latest').json()['data']['items']), 1)
        sitemap = self.client.get('/news/sitemap-part/1.xml')
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn('https://www.hnyueke.com', sitemap.text)
        self.assertIn(article['url'], sitemap.text)
        self.assertEqual(self.client.get(f'/api/manage/news/packages/{pid}/ledger.xlsx').status_code, 200)
        version=self.client.get(f"/api/manage/news/articles/{article['id']}").json()['data']['packageVersion']
        self.assertEqual(self.client.post(f"/api/manage/news/articles/{article['id']}/withdraw", json={'expectedVersion':version,'reason':'隔离验收完成，撤下测试内容'}).status_code, 200)
        self.assertEqual(self.client.get(article['url']).status_code, 404)
        self.assertNotIn(article['title'], self.client.get(article['url']).text)
        self.assertEqual(self.client.get('/api/news/latest').json()['data']['items'], [])

    def test_student_database_rejected(self):
        from unittest.mock import patch
        from website_app.db import DBNotEnabledError
        with patch.dict(os.environ, {'WEBSITE_DATABASE_URL': 'mysql+pymysql://website:unused@127.0.0.1/student_lifecycle_runtime_20260902'}):
            with self.assertRaises(DBNotEnabledError): database_url()

    def test_manual_draft_preserves_incomplete_input_then_requires_fresh_review(self):
        self.login('editor')
        request_id = uuid4().hex
        initial = {'requestId':request_id, 'title':'官网新闻撰写测试', 'summary':'未完成摘要', 'body':'这是一段尚未完成的草稿。'}
        response = self.client.post('/api/manage/news/drafts', json=initial)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()['data']; article = saved['article']; package = saved['package']
        self.assertEqual(article['body'], initial['body'])
        self.assertEqual(article['state'], 'INVALID')
        self.assertEqual(self.client.get(article['url']).status_code, 404)
        retry = self.client.post('/api/manage/news/drafts', json=initial)
        self.assertEqual(retry.json()['data']['article']['id'], article['id'])
        self.assertEqual(self.client.post('/api/manage/news/drafts', json={**initial, 'body':'不同的内容'}).status_code, 409)
        updated = {'title':initial['title'], 'summary':'验证官网独立后台手工撰写、保存草稿及审核发布的完整流程。', 'body':'这是隔离测试新闻，说明手工撰写和正式审核之间的关系。'*8, 'category':'company', 'contentKind':'original', 'aiAssisted':False, 'sources':[{'title':'测试原始来源','url':'https://example.com/news/manual'}], 'expectedVersion':package['version'],'authorName':'隔离验收作者','editorName':'隔离验收编辑','rightsBasis':'本稿为仅用于隔离验收的原创文字','rightsScope':'正文及图片仅用于官网隔离验收'}
        result = self.client.put(f"/api/manage/news/articles/{article['id']}",json=updated)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['data']['article']['state'],'READY')
        self.assertEqual(self.client.put(f"/api/manage/news/articles/{article['id']}",json=updated).status_code,409)
        read = self.client.get(f"/api/manage/news/articles/{article['id']}").json()['data']
        self.assertEqual(read['body'],updated['body'])
        self.assertEqual(read['packageVersion'],1)
        self.client.post('/api/auth/logout'); self.login('publisher')
        old_approval = {'expectedVersion':package['version'],'reviewDigest':package['reviewDigest'],'confirmed':True}
        self.assertEqual(self.client.post(f"/api/manage/news/packages/{package['id']}/confirm",json=old_approval).status_code,409)
        current = result.json()['data']['package']
        approval = {'expectedVersion':current['version'],'reviewDigest':current['reviewDigest'],'confirmed':True}
        self.assertEqual(self.client.post(f"/api/manage/news/packages/{package['id']}/confirm",json=approval).status_code,400)
        aid=article['id']
        submitted=self.client.post(f'/api/manage/news/articles/{aid}/submit',json={'expectedVersion':1}).json()['data']
        approved=self.client.post(f'/api/manage/news/articles/{aid}/actions/approve',json={'expectedVersion':submitted['package']['version'],'reviewDigest':submitted['article']['contentDigest']})
        self.assertEqual(approved.status_code,200,approved.text)
        scheduled=self.client.post(f'/api/manage/news/articles/{aid}/actions/schedule',json={'expectedVersion':approved.json()['data']['package']['version'],'publishAt':service.iso(datetime.utcnow()+timedelta(seconds=30))})
        self.assertEqual(scheduled.status_code,200,scheduled.text)
        self.assertEqual(self.client.put(f"/api/manage/news/articles/{article['id']}",json={**updated,'expectedVersion':2}).status_code,409)
        with self.factory() as db:
            self.assertEqual(service.publish_due(db,datetime.utcnow()+timedelta(minutes=2)),1);db.commit()
        public = self.client.get(article['url'])
        self.assertEqual(public.status_code,200)
        self.assertIn(updated['summary'],public.text)

    def test_manual_draft_source_safety_and_edit_permissions(self):
        body = {'requestId':uuid4().hex,'title':'未授权草稿提交'}
        self.assertEqual(self.client.post('/api/manage/news/drafts',json=body).status_code,401)
        self.login('editor')
        unsafe = {**body,'sources':[{'title':'错误来源','url':'javascript:alert(1)'}]}
        self.assertEqual(self.client.post('/api/manage/news/drafts',json=unsafe).status_code,422)
        self.assertEqual(self.client.post('/api/manage/news/drafts',json={**body,'title':'   '}).status_code,422)

    def test_edit_invalid_import_does_not_link_or_publish_unstored_images(self):
        from io import BytesIO
        from PIL import Image
        picture = BytesIO(); Image.new('RGB', (32, 24), (44, 90, 160)).save(picture, format='PNG')
        first, missing = list(set(('assets/first.png', 'assets/second.png')))
        def metadata(article, entries, index):
            entries[first] = picture.getvalue()
            entries[article['file']] += f'\n\n![配图]({first})\n\n![缺图]({missing})'.encode()
        self.login('editor')
        imported = self.client.post('/api/manage/news/packages', files={'file':('partial.zip',make_bundle(1,'缺图编辑',override=metadata),'application/zip')})
        self.assertEqual(imported.status_code,200,imported.text)
        package = imported.json()['data']['package']
        article = self.client.get(f"/api/manage/news/packages/{package['id']}").json()['data']['articles'][0]
        self.assertEqual(article['state'],'INVALID')
        with self.factory() as db:
            self.assertTrue(db.get(NewsArticle,article['id']).media_map)
            self.assertEqual(list(db.scalars(select(NewsMedia.id))),[])
        body = {'title':'缺图新闻编辑验证', 'summary':'本稿用于验证失败导入的新闻不能引用尚未保存的图片。', 'body':'本稿只用于官网隔离环境验证编辑、校验和发布边界。'*9 + f'\n\n![配图]({first})', 'sources':[{'title':'隔离测试来源','url':'https://example.com/missing-image'}], 'expectedVersion':package['version']}
        updated = self.client.put(f"/api/manage/news/articles/{article['id']}",json=body)
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()['data']['article']['state'],'INVALID')
        self.assertEqual(self.client.get(article['url']).status_code,404)
        with self.factory() as db: self.assertEqual(list(db.scalars(select(NewsMediaLink.article_id))),[])
        body['expectedVersion'] = updated.json()['data']['package']['version']
        body['body'] = '本稿已移除缺失配图引用，只在隔离环境验证正文与审核流程。'*9
        recovered = self.client.put(f"/api/manage/news/articles/{article['id']}",json=body)
        self.assertEqual(recovered.status_code,200,recovered.text)
        self.assertEqual(recovered.json()['data']['article']['state'],'READY')
