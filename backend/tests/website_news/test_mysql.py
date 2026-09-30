"""Run with NEWS_TEST_DATABASE_URL pointing at a DISPOSABLE test_ MySQL8 database.
Unlike service tests this executes frozen migration DDL, transactions, locks and HTTP.
"""
import os, unittest, importlib.util, pathlib, concurrent.futures
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from app.models.website_news import NewsPackage, NewsArticle, NewsAudit, NewsDispatch, NewsMediaLink
from app.services.website_news import service as s
from app.services.website_news.package import parse_package
from helpers import make_bundle

URL=os.getenv('NEWS_TEST_DATABASE_URL')
if os.getenv('NEWS_TEST_REQUIRED')=='true' and not URL:raise RuntimeError('MySQL test URL required; refusing a false green skip')

@unittest.skipUnless(URL,'Real MySQL not configured; no SQLite fallback')
class MySQLNews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url=make_url(URL)
        if url.get_backend_name()!='mysql' or not (url.database or '').startswith('test_'):raise RuntimeError('Only disposable test_ MySQL databases may run this suite')
        cls.engine=create_engine(URL,pool_pre_ping=True,pool_size=8)
        cls.Session=sessionmaker(cls.engine,expire_on_commit=False)
        cls.migration_path=pathlib.Path(__file__).resolve().parents[2]/'alembic/versions/20260909_website_news_packages.py'
        # parents[2] is tests' backend parent.
        spec=importlib.util.spec_from_file_location('news_migration',cls.migration_path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);cls.m=m
        with cls.engine.begin() as c:
            for table in reversed(m.TABLES):c.execute(text('DROP TABLE IF EXISTS '+table))
            for ddl in m.DDL:c.execute(text(ddl))
            c.execute(text("INSERT INTO t_website_news_dispatch (id,last_error) VALUES (1,'')"))
    def setUp(self):
        with self.engine.begin() as c:
            for table in reversed(self.m.TABLES):
                if table!='t_website_news_dispatch':c.execute(text('DELETE FROM '+table))
            c.execute(text("UPDATE t_website_news_dispatch SET next_slot=NULL,heartbeat_at=NULL,last_error='' WHERE id=1"))
    @classmethod
    def tearDownClass(cls):cls.engine.dispose()
    def import_(self,n=3,prefix='A',**kw):
        data=make_bundle(n,prefix,**kw)
        with self.Session() as db:p,reused=s.import_package(db,parse_package(data),'news.zip','root');pid=p.id;db.commit()
        return pid,data
    def approve_(self,pid,excluded=(),interval=3):
        with self.Session() as db:
            p=s.package(db,pid);p,reused=s.approve(db,pid,'root',p.version,p.review_digest,list(excluded),interval);db.commit();return p
    def test_import_no_publication_without_confirmation(self):
        pid,_=self.import_(41)
        with self.Session() as db:
            self.assertEqual(s.summary(db,s.package(db,pid))['counts'],{'READY':41});self.assertEqual(s.publish_due(db,datetime.utcnow()+timedelta(days=100)),0);db.commit()
    def test_75_approved_published_in_chunks_without_daily_cap(self):
        pid,_=self.import_(75);p=self.approve_(pid)
        with self.Session() as db:
            first,last=db.execute(select(func.min(NewsArticle.scheduled_at),func.max(NewsArticle.scheduled_at))).one();self.assertEqual(last-first,timedelta(minutes=74*3))
            at=datetime.utcnow()+timedelta(days=5);self.assertEqual(s.publish_due(db,at),50);db.commit();self.assertEqual(s.publish_due(db,at),25);db.commit();self.assertEqual(s.publish_due(db,at),0);db.commit()
            self.assertEqual(s.package(db,pid).state,'COMPLETE');self.assertEqual(db.scalar(select(func.count()).select_from(NewsAudit).where(NewsAudit.action=='PUBLISH')),75)
    def test_repeated_upload_and_confirmation_do_not_duplicate(self):
        pid,data=self.import_(3)
        with self.Session() as db:p,reused=s.import_package(db,parse_package(data),'again.zip','root');self.assertTrue(reused);self.assertEqual(p.id,pid);db.commit()
        p=self.approve_(pid)
        with self.Session() as db:
            before=list(db.scalars(select(NewsArticle.scheduled_at).order_by(NewsArticle.id)));p,reused=s.approve(db,pid,'root',0,p.review_digest,[],3);self.assertTrue(reused);db.commit();self.assertEqual(list(db.scalars(select(NewsArticle.scheduled_at).order_by(NewsArticle.id))),before)
    def test_partial_errors_and_cross_package_duplicate(self):
        self.import_(2)
        def edit(a,e,i):
            if i==0:a['sources']=[]
        pid,_=self.import_(3,prefix='B',override=edit)
        with self.Session() as db:self.assertEqual(s.summary(db,s.package(db,pid))['counts'],{'INVALID':1,'READY':2})
        _,raw=self.import_(1,prefix='C')
        parsed=parse_package(raw);parsed['sha256']='d'*64
        with self.Session() as db:p,_=s.import_package(db,parsed,'duplicate.zip','root');self.assertEqual(s.summary(db,p)['counts'],{'DUPLICATE':1});db.commit()
    def test_exclusions_cover_all_pages_and_bad_version(self):
        pid,_=self.import_(105)
        with self.Session() as db:
            p=s.package(db,pid);exclude=db.scalar(select(NewsArticle.id).where(NewsArticle.ordinal==105))
            with self.assertRaises(s.NewsError):s.approve(db,pid,'root',22,p.review_digest,[],3)
            db.rollback()
        self.approve_(pid,[exclude])
        with self.Session() as db:self.assertEqual(s.summary(db,s.package(db,pid))['counts'],{'EXCLUDED':1,'SCHEDULED':104})
    def test_pause_resume_keeps_interval_cancel_no_republish(self):
        pid,_=self.import_(4);p=self.approve_(pid,interval=5)
        with self.Session() as db:
            p=s.control(db,pid,'root',p.version,'pause');db.commit();self.assertEqual(s.publish_due(db,datetime.utcnow()+timedelta(days=1)),0);db.commit()
            p=s.control(db,pid,'root',p.version,'resume');db.commit();dates=list(db.scalars(select(NewsArticle.scheduled_at).order_by(NewsArticle.ordinal)));self.assertEqual(dates[1]-dates[0],timedelta(minutes=5))
            p=s.control(db,pid,'root',p.version,'cancel');db.commit();self.assertEqual(s.publish_due(db,datetime.utcnow()+timedelta(days=1)),0);db.commit()
    def test_concurrent_workers_publish_exactly_once(self):
        pid,_=self.import_(75);self.approve_(pid);at=datetime.utcnow()+timedelta(days=1)
        def worker():
            with self.Session() as db:n=s.publish_due(db,at);db.commit();return n
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sum(pool.map(lambda _:worker(),range(2))),75)
        with self.Session() as db:self.assertEqual(db.scalar(select(func.count()).select_from(NewsAudit).where(NewsAudit.action=='PUBLISH')),75)
    def test_concurrent_imports_deduplicate_archive(self):
        data=make_bundle(5)
        def worker():
            with self.Session() as db:p,reused=s.import_package(db,parse_package(data),'same.zip','root');db.commit();return p.id
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(len(set(pool.map(lambda _:worker(),range(2)))),1)
    def test_rollback_does_not_consume_queue_or_create_publish_audit(self):
        pid,_=self.import_(2);self.approve_(pid)
        with self.Session() as db:s.publish_due(db,datetime.utcnow()+timedelta(days=1));db.rollback()
        with self.Session() as db:self.assertEqual(s.summary(db,s.package(db,pid))['counts'],{'SCHEDULED':2});self.assertEqual(db.scalar(select(func.count()).select_from(NewsAudit).where(NewsAudit.action=='PUBLISH')),0)
    def test_long_unicode_text_fits_actual_mysql_column(self):
        def edit(a,e,i):e[a['file']]=('不同段落'+''.join(chr(0x4e00+j%18000) for j in range(23000))).encode()
        pid,_=self.import_(1,override=edit,compression=0)
        with self.Session() as db:self.assertGreater(len(db.scalar(select(NewsArticle.body)).encode()),65535)
    def client(self,actor='root'):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1 import website_news as api
        from app.core.exceptions import register_exception_handlers
        from app.core.security import get_current_user
        app=FastAPI();register_exception_handlers(app);app.include_router(api.router,prefix='/api/v1');app.include_router(api.public_api,prefix='/api/v1');app.include_router(api.public_pages)
        if actor=='root':app.dependency_overrides[get_current_user]=lambda:{'userId':'platform-test','userType':'PLATFORM_SUPER_ADMIN'}
        elif actor=='school':app.dependency_overrides[get_current_user]=lambda:{'userType':'SCHOOL_ADMIN','permissions':['*','platform.*']}
        elif actor=='staff':app.dependency_overrides[get_current_user]=lambda:{'userType':'PLATFORM_VIEWER','permissions':['*']}
        return TestClient(app,raise_server_exceptions=False)
    def test_http_upload_confirm_public_and_root_boundaries(self):
        from app.api.v1 import website_news as api
        with patch.object(api,'get_sessionmaker',return_value=self.Session):
            for actor,status in [('none',401),('school',403),('staff',403)]:
                with self.client(actor) as c:self.assertEqual(c.get('/api/v1/platform/website-news/packages').status_code,status)
            with self.client() as c:
                r=c.post('/api/v1/platform/website-news/packages',files={'file':('today.zip',make_bundle(2),'application/zip')});self.assertEqual(r.status_code,200,r.text);p=r.json()['data']['package'];pid=p['id']
                self.assertNotIn('A 教务测试条目',c.get('/news').text)
                proof={'expectedVersion':p['version'],'reviewDigest':p['reviewDigest'],'confirmed':True}
                r=c.post(f'/api/v1/platform/website-news/packages/{pid}/confirm',json={**proof,'confirmed':'true'});self.assertEqual(r.status_code,400)
                r=c.post(f'/api/v1/platform/website-news/packages/{pid}/confirm',json=proof);self.assertEqual(r.status_code,200,r.text)
                with self.Session() as db:s.publish_due(db,datetime.utcnow()+timedelta(days=1));db.commit()
                index=c.get('/news');self.assertEqual(index.status_code,200);self.assertIn('A 教务测试条目',index.text)
                articles=c.get(f'/api/v1/platform/website-news/packages/{pid}').json()['data']['articles'];a=articles[0]
                html=c.get(a['url']);self.assertEqual(html.status_code,200);self.assertIn('BlogPosting',html.text);self.assertIn('信息来源',html.text)
                self.assertIn(a['url'],c.get('/news/sitemap.xml').text);self.assertIn(a['url'],c.get('/news/feed.xml').text)
                self.assertEqual(c.get(f'/api/v1/platform/website-news/packages/{pid}/ledger.xlsx').headers['content-type'],'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.assertEqual(c.post(f"/api/v1/platform/website-news/articles/{a['id']}/withdraw").status_code,200);self.assertEqual(c.get(a['url']).status_code,404);self.assertNotIn(a['url'],c.get('/news/sitemap.xml').text)
    def test_media_private_before_approval_public_after_publish(self):
        from PIL import Image
        from io import BytesIO
        from app.api.v1 import website_news as api
        out=BytesIO();Image.new('RGB',(20,20),(40,90,190)).save(out,format='PNG')
        def change(a,e,i):a['cover']='assets/test.png';e['assets/test.png']=out.getvalue()
        pid,_=self.import_(1,override=change)
        with self.Session() as db:mid=db.scalar(select(NewsArticle.cover_id))
        with patch.object(api,'get_sessionmaker',return_value=self.Session),self.client() as c:
            self.assertEqual(c.get('/news/media/'+mid).status_code,404);self.approve_(pid)
            with self.Session() as db:s.publish_due(db,datetime.utcnow()+timedelta(days=1));db.commit()
            self.assertEqual(c.get('/news/media/'+mid).status_code,200)
    def test_commit_error_returns_503_not_success(self):
        from app.api.v1 import website_news as api
        with patch.object(api,'get_sessionmaker',return_value=self.Session),patch('sqlalchemy.orm.Session.commit',side_effect=OperationalError('COMMIT',{},Exception('offline'))),self.client() as c:
            r=c.post('/api/v1/platform/website-news/packages',files={'file':('today.zip',make_bundle(),'application/zip')});self.assertEqual(r.status_code,503,r.text)
        with self.Session() as db:self.assertEqual(db.scalar(select(func.count()).select_from(NewsPackage)),0)
