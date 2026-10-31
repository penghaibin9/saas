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
from website_app.news.models import NewsPackage, NewsArticle, NewsAudit, NewsDispatch, NewsMediaLink
from website_app.news import service as s
from website_app.news.package import parse_package
from helpers import make_bundle

URL=os.getenv('WEBSITE_DATABASE_URL') if os.getenv('WEBSITE_TEST_REQUIRED')=='true' else None
if os.getenv('WEBSITE_TEST_REQUIRED')=='true' and not URL:raise RuntimeError('MySQL test URL required; refusing a false green skip')

@unittest.skipUnless(URL,'Real MySQL not configured; no SQLite fallback')
class MySQLNews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url=make_url(URL)
        if url.get_backend_name()!='mysql' or not (url.database or '').startswith('test_website_'):raise RuntimeError('Only disposable test_ MySQL databases may run this suite')
        cls.engine=create_engine(URL,pool_pre_ping=True,pool_size=8)
        cls.Session=sessionmaker(cls.engine,expire_on_commit=False)
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config('alembic.ini'), 'head')
        cls.tables = ['t_website_news_media_link', 't_website_news_revision', 't_website_news_article', 't_website_news_audit', 't_website_news_package', 't_website_news_media']
    def setUp(self):
        with self.engine.begin() as c:
            for table in self.tables:
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

    def test_10001_articles_pagination_search_404_and_sitemap_shards(self):
        from fastapi.testclient import TestClient
        from website_app.main import app
        for index, size in enumerate((2000,2000,2000,2000,2000,1)):
            pid,_=self.import_(size,prefix=f'Volume{index}');self.approve_(pid)
        with self.Session() as db:
            at=datetime.utcnow()+timedelta(days=30);count=0
            while True:
                current=s.publish_due(db,at);db.commit();count+=current
                if not current: break
            self.assertEqual(count,10001)
        with TestClient(app) as client:
            self.assertEqual(client.get('/news?page=834').status_code,200)
            self.assertEqual(client.get('/news?page=835').status_code,404)
            self.assertEqual(client.get('/news?category=unknown').status_code,404)
            for query in ('','Volume'):
                self.assertIn('noindex,nofollow',client.get('/news?q='+query).text)
            index=client.get('/news/sitemap.xml').text;self.assertIn('sitemapindex',index)
            self.assertIn('/news/sitemap-part/11.xml',index)
            from xml.etree.ElementTree import fromstring
            self.assertEqual(len(fromstring(client.get('/news/sitemap-part/1.xml').text)),1001)
            self.assertEqual(len(fromstring(client.get('/news/sitemap-part/11.xml').text)),1)
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
