#!/usr/bin/env python3
"""M0 evidence collector: AST vs official metadata vs disposable migrated MySQL.

No business rows, API calls, DDL, or deletion commands are issued by this tool.
A successful collection is NOT an M0 approval; discrepancies remain explicit.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys


def load_inventory_tool():
    path = Path(__file__).with_name('module-commercial-inventory.py')
    spec = importlib.util.spec_from_file_location('m0_source_inventory', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_key_contracts():
    spec = importlib.util.spec_from_file_location('m0_key_contracts', Path(__file__).with_name('module-commercial-key-contracts.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_source(repo: Path, report: dict, expected_sha: str) -> None:
    if not re.fullmatch(r'[0-9a-f]{40}', expected_sha) or report.get('sourceSha') != expected_sha:
        raise ValueError('SOURCE_SHA_MISMATCH')
    files = report.get('sourceFiles')
    if not isinstance(files, dict) or not files:
        raise ValueError('SOURCE_MANIFEST_MISSING')
    tool = load_inventory_tool()
    if tool.digest(files) != report.get('sourceManifestHash'):
        raise ValueError('SOURCE_MANIFEST_HASH_MISMATCH')
    for name, expected in files.items():
        path = repo / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
            raise ValueError('UNSAFE_SOURCE_PATH')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'SOURCE_CONTENT_CHANGED: {name}')
    if report.get('summary', {}).get('issues'):
        raise ValueError('STATIC_INVENTORY_HAS_ISSUES')


def verify_current_inventory(repo: Path, report: dict, expected_sha: str) -> None:
    """A self-consistent partial manifest is not complete source evidence."""
    verify_source(repo, report, expected_sha)
    fresh = load_inventory_tool().inventory(repo)
    if fresh["summary"]["issues"]:
        raise ValueError("CURRENT_INVENTORY_HAS_ISSUES")
    for key in ("schemaVersion", "sourceFiles", "sourceManifestHash", "models", "migrations",
                "staticMigrationHeads", "additionalTableSites", "moduleMapping"):
        if fresh.get(key) != report.get(key):
            raise ValueError(f"INVENTORY_RECOLLECTION_MISMATCH: {key}")


@contextmanager
def no_connections():
    """Even future model imports must not silently open DB/network connections."""
    from sqlalchemy.engine import Engine
    old = socket.socket.connect, socket.create_connection, Engine.connect
    def denied(*args, **kwargs):
        raise RuntimeError('M0_METADATA_IMPORT_CONNECTION_FORBIDDEN')
    socket.socket.connect = socket.create_connection = Engine.connect = denied
    try:
        yield
    finally:
        socket.socket.connect, socket.create_connection, Engine.connect = old


def collect_metadata(repo: Path) -> dict:
    if 'app.db.base' in sys.modules or 'app.models' in sys.modules:
        raise ValueError('METADATA_REQUIRES_FRESH_PROCESS')
    sys.path.insert(0, str(repo / 'backend'))
    from sqlalchemy.dialects.mysql import dialect
    with no_connections():
        from app.db.base import metadata
    if not metadata.tables:
        raise ValueError('EMPTY_RUNTIME_METADATA')
    tables = {}
    keys = load_key_contracts()
    for name, table in sorted(metadata.tables.items()):
        tables[name] = {
            'keyContract': keys.metadata_contract(table),
            'columns': {c.name: {'type': str(c.type.compile(dialect=dialect())),
                                 'nullable': c.nullable, 'primaryKey': c.primary_key}
                        for c in table.columns},
            'foreignKeys': sorted([{'column': c.name, 'target': fk.target_fullname}
                                   for c in table.columns for fk in c.foreign_keys], key=lambda f: (f['column'], f['target'])),
            'indexes': sorted([{'name': i.name, 'unique': i.unique, 'columns': [c.name for c in i.columns]}
                               for i in table.indexes], key=lambda i: i['name'] or ''),
            'uniqueConstraints': sorted([sorted(c.name for c in constraint.columns)
                                         for constraint in table.constraints if constraint.__class__.__name__ == 'UniqueConstraint']),
        }
    import sqlalchemy
    return {'entrypoint': 'app.db.base.metadata', 'sqlalchemyVersion': sqlalchemy.__version__,
            'applicationImportedWithoutConnections': True, 'tables': tables}


def validate_mysql_target(url: str, environment: dict) -> None:
    from sqlalchemy.engine import make_url
    value = make_url(url)
    # Dedicated service and SELECT-only account are provisioned by this workflow.
    # A URL/name by itself is not evidence that an arbitrary database is safe.
    if environment.get('GITHUB_ACTIONS') != 'true' or environment.get('M0_EPHEMERAL_MYSQL') != '1':
        raise ValueError('MYSQL_COLLECTION_REQUIRES_DISPOSABLE_CI_SERVICE')
    if (value.drivername != 'mysql+pymysql' or value.host != '127.0.0.1' or value.port != 3306
            or value.database != 'm0_commercial_audit' or value.username != 'm0_reader' or value.query):
        raise ValueError('MYSQL_TARGET_NOT_ALLOWED')


def collect_mysql(url: str) -> dict:
    validate_mysql_target(url, os.environ)
    from sqlalchemy import create_engine, text
    engine = create_engine(url, pool_pre_ping=False, connect_args={'connect_timeout': 10, 'read_timeout': 30})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
            version, database, identity, readonly = connection.exec_driver_sql(
                'SELECT VERSION(), DATABASE(), CURRENT_USER(), @@session.transaction_read_only').one()
            if database != 'm0_commercial_audit' or not str(identity).startswith('m0_reader@') or readonly != 1:
                raise ValueError('MYSQL_READ_ONLY_IDENTITY_MISMATCH')
            grants = [row[0] for row in connection.exec_driver_sql('SHOW GRANTS')]
            if len(grants) != 2 or any('WITH GRANT OPTION' in g for g in grants) or not all(re.fullmatch(r'GRANT (USAGE ON \*\.\*|SELECT ON `m0_commercial_audit`\.\*) TO .+', g) for g in grants):
                raise ValueError('MYSQL_READER_HAS_UNEXPECTED_PRIVILEGES')
            table_rows = connection.execute(text('SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=:s'), {'s': database}).all()
            tables, views = {}, []
            for name, kind in table_rows:
                if kind != 'BASE TABLE':
                    views.append(name)
                elif name != 'alembic_version':
                    tables[name] = {'columns': {}, 'foreignKeys': [], 'indexes': []}
            if not tables:
                raise ValueError('MYSQL_SCHEMA_EMPTY')
            for t, col, typ, null, key in connection.execute(text('SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_KEY FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=:s ORDER BY TABLE_NAME,ORDINAL_POSITION'), {'s': database}):
                if t in tables:
                    tables[t]['columns'][col] = {'type': typ, 'nullable': null == 'YES', 'primaryKey': key == 'PRI'}
            foreign_rows = connection.execute(text(
                'SELECT k.TABLE_NAME,k.CONSTRAINT_NAME,k.ORDINAL_POSITION,k.COLUMN_NAME,'
                'k.REFERENCED_TABLE_SCHEMA,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,'
                'r.DELETE_RULE,r.UPDATE_RULE FROM information_schema.KEY_COLUMN_USAGE k '
                'JOIN information_schema.REFERENTIAL_CONSTRAINTS r '
                'ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.TABLE_NAME=k.TABLE_NAME '
                'AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME '
                'WHERE k.TABLE_SCHEMA=:s AND k.REFERENCED_TABLE_NAME IS NOT NULL '
                'ORDER BY k.TABLE_NAME,k.CONSTRAINT_NAME,k.ORDINAL_POSITION'), {'s': database}).all()
            for t, _, _, col, schema, dest, dest_col, _, _ in foreign_rows:
                if t in tables:
                    target = f'{dest}.{dest_col}' if schema == database else f'{schema}.{dest}.{dest_col}'
                    tables[t]['foreignKeys'].append({'column': col, 'target': target})
            index_rows = connection.execute(text(
                'SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME,SUB_PART,EXPRESSION,COLLATION '
                'FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=:s '
                'ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX'), {'s': database}).all()
            for t, name, non_unique, seq, col, prefix, expression, collation in index_rows:
                if t in tables:
                    tables[t]['indexes'].append({'name': name, 'unique': non_unique == 0, 'sequence': seq, 'column': col,
                        'prefixLength': prefix, 'expression': expression, 'collation': collation})
            contracts = load_key_contracts().mysql_contracts(tables, foreign_rows, index_rows, database)
            for name, contract in contracts.items():
                tables[name]['keyContract'] = contract
            heads = sorted(connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalars())
            triggers = sorted(row[0] for row in connection.execute(text('SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=:s'), {'s': database}))
            connection.rollback()
            return {'environment': 'GITHUB_ACTIONS_DISPOSABLE_MYSQL', 'serverVersion': version,
                    'readOnly': True, 'readerSelectOnly': True, 'businessRowsRead': False,
                    'schemaHeads': heads, 'tables': dict(sorted(tables.items())), 'views': sorted(views), 'triggers': triggers,
                    'limitations': ['SELECT-only reader may not see trigger definitions; list is not an exhaustive trigger audit.', 'DDL/index types are collected for review, not a full behavioral schema equivalence proof.']}
    finally:
        engine.dispose()


def reconcile(source: dict, runtime: dict, physical: dict | None) -> dict:
    source_models = source.get('models')
    rt = runtime.get('tables')
    if not source_models or not isinstance(rt, dict) or not rt:
        raise ValueError('EMPTY_SCHEMA_EVIDENCE')
    declared = {m['table']: m for m in source_models}
    if len(declared) != len(source_models):
        raise ValueError('DUPLICATE_SOURCE_TABLE')
    result = {'astOnlyTables': sorted(declared.keys() - rt.keys()),
              'runtimeOnlyTables': sorted(rt.keys() - declared.keys()), 'astRuntimeColumns': [],
              'runtimeOnlyVsMysql': [], 'mysqlOnlyTables': [], 'runtimeMysqlColumns': [],
              'runtimeMysqlConstraints': [], 'runtimeMysqlKeyContracts': [], 'migrationHeadsMatch': None}
    for name in sorted(declared.keys() & rt.keys()):
        expected, actual = set(declared[name]['inheritedFieldNames']), set(rt[name]['columns'])
        if expected != actual:
            result['astRuntimeColumns'].append({'table': name, 'astOnly': sorted(expected - actual), 'runtimeOnly': sorted(actual - expected)})
    if physical is not None:
        db = physical.get('tables')
        if not isinstance(db, dict) or not db or not physical.get('schemaHeads') or physical.get('readOnly') is not True:
            raise ValueError('INVALID_MYSQL_EVIDENCE')
        result['runtimeOnlyVsMysql'] = sorted(rt.keys() - db.keys())
        result['mysqlOnlyTables'] = sorted(db.keys() - rt.keys())
        result['migrationHeadsMatch'] = sorted(source['staticMigrationHeads']) == sorted(physical['schemaHeads'])
        keys = load_key_contracts()
        for name in sorted(rt.keys() & db.keys()):
            key_result = keys.compare(rt[name].get('keyContract'), db[name].get('keyContract'))
            if key_result['status'] != 'MATCH':
                result['runtimeMysqlKeyContracts'].append({'table': name, **key_result})
            expected, actual = rt[name]['columns'], db[name]['columns']
            nullable = [key for key in expected.keys() & actual.keys() if expected[key]['nullable'] != actual[key]['nullable']]
            if expected.keys() != actual.keys() or nullable:
                result['runtimeMysqlColumns'].append({'table': name, 'runtimeOnly': sorted(expected.keys() - actual.keys()),
                    'mysqlOnly': sorted(actual.keys() - expected.keys()), 'nullableDifferences': sorted(nullable)})
            fk = lambda row: {(f['column'], f['target']) for f in row.get('foreignKeys', [])}
            pk = lambda row: {col for col, detail in row['columns'].items() if detail.get('primaryKey')}
            if fk(rt[name]) != fk(db[name]) or pk(rt[name]) != pk(db[name]):
                result['runtimeMysqlConstraints'].append({'table': name, 'runtimeOnlyFK': sorted(fk(rt[name])-fk(db[name])),
                    'mysqlOnlyFK': sorted(fk(db[name])-fk(rt[name])), 'primaryKeyDiffers': pk(rt[name]) != pk(db[name])})
    result['coverageStatus'] = 'NOT_RUN' if physical is None else 'REVIEW_REQUIRED' if any(value for key, value in result.items() if key != 'migrationHeadsMatch') or not result['migrationHeadsMatch'] else 'STRUCTURAL_SETS_MATCH'
    result['m0Complete'] = False
    result['deletionAuthorized'] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mysql', action='store_true')
    args = parser.parse_args()
    repo, output = args.repo.resolve(strict=True), args.output.resolve()
    if output.is_relative_to(repo) or output.exists():
        parser.error('output must be new and outside the repository')
    tool = load_inventory_tool()
    try:
        if tool.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or tool.git_read(repo, 'status', '--porcelain'):
            raise ValueError('EXPECTED_CLEAN_EXACT_HEAD')
        source = json.loads(args.inventory.read_text(encoding='utf-8'))
        verify_current_inventory(repo, source, args.expected_head)
        runtime = collect_metadata(repo)
        physical = collect_mysql(os.environ.get('M0_DATABASE_URL', '')) if args.mysql else None
        result = {'schemaVersion': 2, 'sourceSha': args.expected_head, 'sourceManifestHash': source['sourceManifestHash'],
                  'generatedAtUtc': datetime.now(timezone.utc).isoformat(), 'metadata': runtime, 'mysql': physical,
                  'comparison': reconcile(source, runtime, physical), 'collectionStatus': 'PASS',
                  'consumerClosure': 'PENDING', 'policyPublication': 'PENDING'}
        verify_current_inventory(repo, source, args.expected_head)
        if tool.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or tool.git_read(repo, 'status', '--porcelain'):
            raise ValueError('SOURCE_CHANGED_DURING_COLLECTION')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({'sourceSha': args.expected_head, 'runtimeTables': len(runtime['tables']),
                          'mysqlTables': len(physical['tables']) if physical else None, 'comparison': result['comparison']}, ensure_ascii=False))
        return 0  # Collection success is not schema agreement or stage approval.
    except Exception as exc:
        # Never echo connection strings, SQL errors with parameters, or credentials.
        parser.exit(2, f'M0 collection failed ({type(exc).__name__}); no approval issued.\n')


if __name__ == '__main__':
    raise SystemExit(main())
