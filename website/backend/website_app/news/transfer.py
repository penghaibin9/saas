"""Read-only source snapshot, exact copy into an empty website target, then pause.

Only the seven news tables are read. No account, school or student data is copied.
Default execution is an inspection. Never overwrite a populated target.
"""
import argparse
import base64
import hashlib
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, select, func, update, insert, inspect, Table, MetaData
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from website_app.db import get_engine
from website_app.news.models import NewsDispatch, NewsMedia, NewsPackage, NewsArticle, NewsRevision, NewsMediaLink, NewsAudit
from website_app.news import service

TABLES = [model.__table__ for model in (NewsDispatch, NewsMedia, NewsPackage, NewsArticle, NewsRevision, NewsMediaLink, NewsAudit)]
EDITORIAL_COLUMNS = set(service.METADATA_FIELDS.values()) | {'editorial_state', 'review_reason', 'approved_digest'}

def source_tables(connection):
    """Read only the known news schema; reject partial or unknown column contracts."""
    schema = inspect(connection)
    revision_present = schema.has_table(NewsRevision.__tablename__)
    result = []
    for table in TABLES:
        if table.name == NewsRevision.__tablename__ and not revision_present: continue
        if not schema.has_table(table.name): raise ValueError('来源新闻表不完整，不能迁移')
        reflected = Table(table.name, MetaData(), autoload_with=connection, resolve_fks=False)
        expected = set(table.c.keys())
        if not revision_present and table.name == NewsArticle.__tablename__: expected -= EDITORIAL_COLUMNS
        if set(reflected.c.keys()) != expected:
            raise ValueError('来源新闻字段不符合完整旧版或新版合同，已停止迁移')
        result.append(table if revision_present else reflected)
    return result, not revision_present

def encode(value):
    if isinstance(value, bytes): return {'binary': base64.b64encode(value).decode('ascii')}
    if isinstance(value, datetime): return {'datetime': value.isoformat(timespec='microseconds')}
    raise TypeError('不支持的新闻字段类型')

def rows(connection, table):
    query = select(table).order_by(*table.primary_key.columns)
    try:
        with connection.execution_options(stream_results=True).execute(query) as result:
            yield from result.mappings()
    finally:
        connection.execution_options(stream_results=False)

def fingerprint(connection, table):
    checksum, count = hashlib.sha256(), 0
    for row in rows(connection, table):
        data = json.dumps(dict(row), default=encode, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode('utf-8')
        checksum.update(len(data).to_bytes(8, 'big')); checksum.update(data); count += 1
    return {'rows': count, 'sha256': checksum.hexdigest()}

def identity(connection):
    return tuple(connection.exec_driver_sql('SELECT @@server_uuid, DATABASE()').one())

def transfer(source_engine, target_engine, *, apply=False):
    with source_engine.connect() as source, target_engine.connect() as target:
        if identity(source) == identity(target): raise ValueError('来源与目标是同一个数据库，已拒绝操作')
        source.commit(); target.commit()
        source = source.execution_options(isolation_level='REPEATABLE READ')
        source.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
        # First table read starts the consistent read snapshot, held through copy and verification.
        source_contract, legacy = source_tables(source)
        before = {table.name: fingerprint(source, table) for table in source_contract}
        if before[NewsDispatch.__tablename__]['rows'] != 1:
            raise ValueError('来源发布调度记录不完整，不能迁移')
        if source.scalar(select(NewsDispatch.id)) != 1:
            raise ValueError('来源调度标识不符合新闻发布合同')
        with target.begin():
            gate = target.execute(select(NewsDispatch.id).where(NewsDispatch.id == 1).with_for_update()).scalar_one_or_none()
            if gate != 1: raise ValueError('目标尚未完成独立官网迁移')
            existing = {table.name: target.scalar(select(func.count()).select_from(table)) for table in TABLES if table.name != NewsDispatch.__tablename__}
            report = {'source': before, 'legacySource':legacy, 'targetCounts': existing, 'targetEmpty': not any(existing.values()), 'applied': False}
            if not apply: return report
            if any(existing.values()): raise ValueError('目标已有新闻或审计，拒绝覆盖；请使用新的空目标库')
            for table in source_contract:
                destination = next(item for item in TABLES if item.name == table.name)
                for row in rows(source, table):
                    values = dict(row)
                    if table.name == NewsDispatch.__tablename__:
                        target.execute(update(table).where(table.c.id == 1).values(**{key:value for key,value in values.items() if key != 'id'}))
                    else:
                        if legacy and table.name == NewsArticle.__tablename__:
                            values.update(source_type='unverified', author_name='', editor_name='', rights_basis='',
                                rights_scope='', rights_evidence='', related_products=[], editorial_state='LEGACY',
                                rights_valid_until=None, review_reason='', approved_digest=None)
                        target.execute(insert(destination).values(**values))
            # Reflected source columns project the exact old contract on the target too.
            after = {table.name: fingerprint(target, table) for table in source_contract}
            if before != after:
                raise ValueError('迁移校验不一致，目标事务已取消，未报告成功')
            # A second site's worker must never publish the migrated pending queue automatically.
            with Session(bind=target, join_transaction_mode='create_savepoint') as db:
                queued = list(db.scalars(select(NewsPackage).where(NewsPackage.state == 'QUEUED')))
                for package in queued:
                    service.control(db, package.id, 'website-transfer', package.version, 'pause')
                gate = db.get(NewsDispatch, 1); gate.heartbeat_at = None; gate.last_error = ''
                db.commit()
            report.update(applied=True, verifiedCopy=after, pausedPackages=len(queued))
        source.rollback()
        return report

def main():
    parser = argparse.ArgumentParser(description='官网新闻独立迁移：默认只读核验，实际导入仅允许空目标库')
    parser.add_argument('--apply-to-empty-target', action='store_true')
    args = parser.parse_args()
    source_url = make_url(os.environ['WEBSITE_NEWS_SOURCE_URL'])
    if source_url.get_backend_name() != 'mysql': raise ValueError('新闻来源必须是 MySQL')
    source = create_engine(source_url, hide_parameters=True, pool_pre_ping=True)
    try:
        report = transfer(source, get_engine(), apply=args.apply_to_empty_target)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        source.dispose()

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Connection and database errors may contain configuration or draft content.
        raise SystemExit('新闻迁移未完成，未继续执行：' + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
