import os
import sys
import subprocess
import unittest
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from sqlalchemy import create_engine, delete, select, event, insert, inspect
from sqlalchemy.orm import sessionmaker
from website_app.db import database_url, get_engine, get_sessionmaker
from website_app.news.models import NewsArticle, NewsRevision, NewsMediaLink, NewsAudit, NewsPackage, NewsMedia, NewsDispatch
from website_app.news.package import parse_package
from website_app.news.transfer import transfer, fingerprint, TABLES, source_tables
from website_app.news import service
from helpers import make_bundle
from fastapi import FastAPI
from fastapi.testclient import TestClient
from website_app.news.routes import public_pages, news_db

class WebsiteTransfer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_url = database_url()
        if os.getenv('WEBSITE_TEST_REQUIRED') != 'true' or source_url.database != 'test_website_acceptance':
            raise RuntimeError('迁移验收只能使用明确的官网隔离测试库')
        cls.target_url = source_url.set(database='test_website_transfer')
        env = {**os.environ, 'WEBSITE_DATABASE_URL':cls.target_url.render_as_string(hide_password=False)}
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
        cls.target = create_engine(cls.target_url,hide_parameters=True)
        cls.source = get_engine()

    @classmethod
    def tearDownClass(cls): cls.target.dispose()

    def setUp(self):
        for engine in (self.source,self.target):
            with sessionmaker(engine)() as db:
                for model in (NewsMediaLink,NewsRevision,NewsArticle,NewsAudit,NewsPackage,NewsMedia): db.execute(delete(model))
                db.get(NewsDispatch,1).next_slot = None
                db.commit()
        picture=BytesIO();Image.new('RGB',(100,60),(42,92,170)).save(picture,format='PNG')
        def metadata(article,entries,index):
            entries['assets/test.png']=picture.getvalue()
            entries[article['file']]+=b'\n\n![test](assets/test.png)\n'
            article['cover']='assets/test.png'
        with get_sessionmaker()() as db:
            package,_=service.import_package(db,parse_package(make_bundle(2,prefix='Transfer',override=metadata)),'migration-test.zip','test-editor')
            self.pid=package.id
            service.approve(db,package.id,'test-publisher',package.version,package.review_digest,[],3)
            db.commit()

    def snapshot(self, engine):
        with engine.connect() as connection: return {table.name:fingerprint(connection,table) for table in TABLES}

    def test_copy_verifies_binary_and_identity_then_pauses_without_source_changes(self):
        source_before=self.snapshot(self.source)
        dry=transfer(self.source,self.target)
        self.assertTrue(dry['targetEmpty']);self.assertFalse(dry['applied'])
        self.assertEqual(self.snapshot(self.source),source_before)
        result=transfer(self.source,self.target,apply=True)
        self.assertTrue(result['applied']);self.assertEqual(result['verifiedCopy'],source_before)
        self.assertEqual(result['pausedPackages'],1)
        self.assertEqual(self.snapshot(self.source),source_before)
        with sessionmaker(self.target)() as db:
            package=db.get(NewsPackage,self.pid);self.assertEqual(package.state,'PAUSED')
            self.assertEqual(service.publish_due(db,datetime.utcnow()+timedelta(days=1)),0);db.commit()
            self.assertEqual(len(list(db.scalars(select(NewsArticle)))),2)
            self.assertEqual(len(list(db.scalars(select(NewsMedia)))),1)
        target_before=self.snapshot(self.target)
        with self.assertRaisesRegex(ValueError,'拒绝覆盖'): transfer(self.source,self.target,apply=True)
        self.assertEqual(self.snapshot(self.target),target_before)
        with self.assertRaisesRegex(ValueError,'同一个数据库'): transfer(self.source,self.source,apply=True)

    def test_target_failure_rolls_back_every_copied_table(self):
        source_before=self.snapshot(self.source);target_before=self.snapshot(self.target)
        def fail(connection,cursor,statement,parameters,context,executemany):
            if statement.startswith('INSERT INTO t_website_news_article'): raise RuntimeError('isolated migration interruption')
        event.listen(self.target,'before_cursor_execute',fail)
        try:
            with self.assertRaisesRegex(RuntimeError,'interruption'): transfer(self.source,self.target,apply=True)
        finally: event.remove(self.target,'before_cursor_execute',fail)
        self.assertEqual(self.snapshot(self.source),source_before)
        self.assertEqual(self.snapshot(self.target),target_before)

    def test_legacy_six_tables_preserve_public_content_and_require_new_approval(self):
        """Rebuild only the explicitly disposable transfer fixture as the frozen old schema."""
        from pathlib import Path
        import importlib.util
        from types import SimpleNamespace
        from website_app.news.editor import UpdateDraft, update as edit
        with get_sessionmaker()() as db:
            articles=list(db.scalars(select(NewsArticle).order_by(NewsArticle.ordinal)))
            first,pending=articles
            service.publish_due(db,first.scheduled_at);db.commit()
            aid,slug,first_time,mid=first.id,first.slug,first.published_at,first.cover_id
            pending_id=pending.id
        with self.source.connect() as c:
            original={table.name:list(c.execute(select(table)).mappings()) for table in TABLES if table.name!=NewsRevision.__tablename__}
        spec=importlib.util.spec_from_file_location('frozen_news',Path('migrations/versions/0001_website_news.py'))
        frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
        # Target is empty and both database names were explicitly guarded in setUpClass.
        with self.target.begin() as c:
            for table in reversed(TABLES): table.drop(c)
            for statement in frozen.DDL: c.exec_driver_sql(statement)
        env={**os.environ,'WEBSITE_DATABASE_URL':self.target_url.render_as_string(hide_password=False)}
        try:
            with self.target.begin() as c:
                legacy_tables,_=source_tables(c)
                for table in legacy_tables:
                    for row in original[table.name]: c.execute(insert(table).values(**{key:row[key] for key in table.c.keys()}))
            with self.source.begin() as c:
                for table in reversed(TABLES):
                    if table.name!=NewsDispatch.__tablename__: c.execute(delete(table))
            with self.target.connect() as c:
                tables,legacy=source_tables(c);before={t.name:fingerprint(c,t) for t in tables}
                self.assertTrue(legacy)
            self.assertTrue(transfer(self.target,self.source)['legacySource'])
            report=transfer(self.target,self.source,apply=True)
            self.assertEqual(report['verifiedCopy'],before);self.assertEqual(report['pausedPackages'],1)
            with self.target.connect() as c: self.assertEqual({t.name:fingerprint(c,t) for t in tables},before)
            with get_sessionmaker()() as db:
                first=db.get(NewsArticle,aid);pending=db.get(NewsArticle,pending_id);package=db.get(NewsPackage,self.pid)
                self.assertEqual(first.published_at,first_time);self.assertEqual(first.editorial_state,'LEGACY')
                self.assertIsNone(first.approved_digest);self.assertEqual(first.related_products,[])
                self.assertEqual(len(list(db.scalars(select(NewsRevision)))),0)
                self.assertEqual(service.publish_due(db,datetime.utcnow()+timedelta(days=1)),0)
                with self.assertRaisesRegex(service.NewsError,'旧排期'): service.control(db,self.pid,'publisher',package.version,'resume')
                self.assertEqual(package.state,'PAUSED')
                action=lambda:SimpleNamespace(expectedVersion=package.version,revisionId=None,reason='',reviewDigest=service.content_digest(pending),publishAt=datetime.utcnow()+timedelta(seconds=30))
                service.editorial_action(db,pending_id,action(),'editor','cancel')
                edit(db,pending_id,UpdateDraft(expectedVersion=package.version,title=pending.title,summary=pending.summary,body=pending.body,
                    category=pending.category,sources=pending.sources,contentKind=pending.content_kind,aiAssisted=pending.ai_assisted,
                    sourceType='original',authorName='隔离验收作者',editorName='隔离验收编辑',rightsBasis='此文由隔离测试作者创作',rightsScope='只用于本机迁移验收环境'), 'editor')
                service.editorial_action(db,pending_id,action(),'editor','submit')
                service.editorial_action(db,pending_id,action(),'publisher','approve')
                service.control(db,self.pid,'publisher',package.version,'resume')
                service.editorial_action(db,pending_id,action(),'publisher','schedule');db.commit()
                self.assertEqual(service.publish_due(db,datetime.utcnow()+timedelta(days=1)),1);db.commit()
                self.assertEqual(service.publish_due(db,datetime.utcnow()+timedelta(days=2)),0);db.commit()
            app=FastAPI();app.include_router(public_pages)
            with TestClient(app) as client:
                self.assertEqual(client.get('/news/'+slug).status_code,200)
                self.assertEqual(client.get('/news/media/'+mid).status_code,200)
            with self.target.begin() as c: c.exec_driver_sql('ALTER TABLE t_website_news_article ADD COLUMN unexpected_fixture INTEGER')
            with self.assertRaisesRegex(ValueError,'合同'): transfer(self.target,self.source)
        finally:
            with self.target.begin() as c:
                if 'unexpected_fixture' in {item['name'] for item in inspect(c).get_columns('t_website_news_article')}:
                    c.exec_driver_sql('ALTER TABLE t_website_news_article DROP COLUMN unexpected_fixture')
            subprocess.run([sys.executable,'-m','alembic','stamp','0003_public_rate'],env=env,check=True,capture_output=True)
            subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)

    def test_private_revision_copy_preserves_original_and_package_pause(self):
        from types import SimpleNamespace
        with get_sessionmaker()() as db:
            articles=list(db.scalars(select(NewsArticle).order_by(NewsArticle.ordinal)));original=articles[0]
            self.assertEqual(service.publish_due(db,original.scheduled_at),1)
            package=db.get(NewsPackage,self.pid)
            package,revision=service.create_revision(db,original.id,package.version,'test-editor')
            body=lambda **extra:SimpleNamespace(expectedVersion=package.version,revisionId=revision.id,reason='',reviewDigest=service.content_digest(revision),publishAt=datetime.utcnow()+timedelta(minutes=5),**extra)
            service.editorial_action(db,original.id,body(),'test-editor','submit')
            service.editorial_action(db,original.id,body(),'test-publisher','approve')
            service.editorial_action(db,original.id,body(),'test-publisher','schedule')
            rid=revision.id;aid=original.id;slug=original.slug;db.commit()
        before=self.snapshot(self.source);result=transfer(self.source,self.target,apply=True)
        self.assertEqual(result['verifiedCopy'],before);self.assertEqual(self.snapshot(self.source),before)
        with sessionmaker(self.target)() as db:
            self.assertEqual(db.get(NewsRevision,rid).editorial_state,'SCHEDULED')
            self.assertEqual(db.get(NewsArticle,aid).slug,slug)
            self.assertEqual(service.publish_due(db,datetime.utcnow()+timedelta(days=2)),0)
            package=db.get(NewsPackage,self.pid)
            service.editorial_action(db,aid,SimpleNamespace(expectedVersion=package.version,revisionId=rid,reason=''),'test-publisher','pause')
            with self.assertRaisesRegex(service.NewsError,'整体暂停'):
                service.editorial_action(db,aid,SimpleNamespace(expectedVersion=package.version,revisionId=rid,reason=''),'test-publisher','resume')
            self.assertEqual(package.state,'PAUSED');db.rollback()

    def test_published_urls_and_images_survive_and_pending_requires_explicit_resume(self):
        with get_sessionmaker()() as db:
            articles = list(db.scalars(select(NewsArticle).order_by(NewsArticle.ordinal)))
            published_id, pending_id = [article.id for article in articles]
            published_slug, pending_slug = [article.slug for article in articles]
            media_id = articles[0].cover_id
            first_time = articles[0].scheduled_at
            self.assertEqual(service.publish_due(db, first_time), 1)
            db.commit()
        source_before = self.snapshot(self.source)
        result = transfer(self.source, self.target, apply=True)
        self.assertEqual(result['pausedPackages'], 1)

        target_sessions = sessionmaker(self.target)
        def target_db():
            with target_sessions() as db:
                yield db
        app = FastAPI()
        app.include_router(public_pages)
        app.dependency_overrides[news_db] = target_db
        with TestClient(app) as client:
            self.assertEqual(client.get('/news/' + published_slug).status_code, 200)
            self.assertEqual(client.get('/news/' + pending_slug).status_code, 404)
            media = client.get('/news/media/' + media_id)
            self.assertEqual(media.status_code, 200)
            with Image.open(BytesIO(media.content)) as picture:
                self.assertEqual(picture.size, (100, 60))
            sitemap = client.get('/news/sitemap.xml').text
            self.assertIn('/news/' + published_slug, sitemap)
            self.assertNotIn('/news/' + pending_slug, sitemap)
            with target_sessions() as db:
                self.assertEqual(service.publish_due(db, datetime.utcnow() + timedelta(days=1)), 0)
                package = db.get(NewsPackage, self.pid)
                service.control(db, package.id, 'target-publisher', package.version, 'resume')
                db.commit()
                self.assertEqual(service.publish_due(db, datetime.utcnow() + timedelta(days=1)), 1)
                db.commit()
                self.assertEqual(db.get(NewsArticle, published_id).published_at, first_time)
                self.assertEqual(db.get(NewsArticle, pending_id).state, 'PUBLISHED')
                self.assertEqual(len(list(db.scalars(select(NewsAudit).where(NewsAudit.action == 'PUBLISH')))), 2)
                self.assertEqual(service.publish_due(db, datetime.utcnow() + timedelta(days=2)), 0)
                db.commit()
            self.assertEqual(client.get('/news/' + pending_slug).status_code, 200)
        self.assertEqual(self.snapshot(self.source), source_before)
