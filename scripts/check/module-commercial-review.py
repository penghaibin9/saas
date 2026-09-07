#!/usr/bin/env python3
"""Verify explicit M0 schema dispositions against fresh evidence; never approve a purge."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def load_check(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def unique_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def column_observation(schema, difference):
    table = difference['table']
    columns = sorted(set(difference['runtimeOnly'] + difference['mysqlOnly'] + difference['nullableDifferences']))
    rt = schema['metadata']['tables'][table]['columns']
    db = schema['mysql']['tables'][table]['columns']
    return {'difference': difference, 'runtime': {c: rt.get(c) for c in columns}, 'mysql': {c: db.get(c) for c in columns}}


def assess(repo: Path, source: dict, schema: dict, review: dict):
    if schema.get('sourceSha') != source.get('sourceSha') or schema.get('sourceManifestHash') != source.get('sourceManifestHash'):
        raise ValueError('SCHEMA_SOURCE_IDENTITY_MISMATCH')
    if schema.get('collectionStatus') != 'PASS' or schema.get('mysql', {}).get('readerSelectOnly') is not True or schema['mysql'].get('businessRowsRead') is not False:
        raise ValueError('REQUIRES_READ_ONLY_SCHEMA_EVIDENCE')
    # Recompute, rather than trusting a comparison array copied into a JSON artifact.
    expected = load_check('module-commercial-reconcile').reconcile(source, schema['metadata'], schema['mysql'])
    if expected != schema.get('comparison'):
        raise ValueError('SCHEMA_COMPARISON_TAMPERED')
    if review.get('artifactType') != 'M0_SCHEMA_DISPOSITIONS_NOT_APPROVAL' or review.get('schemaVersion') != 1 or review.get('deletionAuthorized') is not False:
        raise ValueError('NOT_A_REVIEW_ONLY_CONTRACT')
    if not re.fullmatch(r'[0-9a-f]{40}', str(review.get('reviewedApplicationSha', ''))):
        raise ValueError('REVIEW_SOURCE_SHA_MISSING')
    if not isinstance(review.get('evidence'), dict) or not review['evidence']:
        raise ValueError('REVIEW_EVIDENCE_MISSING')
    for item in review['evidence'].values():
        name = item['path']
        path = repo / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
            raise ValueError('UNSAFE_REVIEW_PATH')
        content = path.read_bytes()
        if source['sourceFiles'].get(name) != item['sha256'] or hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError('REVIEW_SOURCE_CONTENT_CHANGED')
        start, end = item['startLine'], item['endLine']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(content.decode('utf-8-sig').splitlines()):
            raise ValueError('INVALID_REVIEW_LINE_RANGE')
    cases = review.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('NO_REVIEWED_CASES')
    indexed = {}
    for row in cases:
        table = row.get('table', '')
        if not re.fullmatch(r't_[a-z0-9_]+', table) or table in indexed:
            raise ValueError('INVALID_OR_DUPLICATE_REVIEW_TABLE')
        if row.get('code') not in review.get('decisions', {}) or row.get('remediationComplete') is not False or row.get('purgeAuthorized') is not False:
            raise ValueError('REVIEW_CANNOT_AUTHORIZE_MUTATIONS')
        if not row.get('evidence') or any(key not in review['evidence'] for key in row['evidence']):
            raise ValueError('CASE_EVIDENCE_MISSING')
        if not re.fullmatch(r'[0-9a-f]{64}', str(row.get('observationHash', ''))):
            raise ValueError('INVALID_OBSERVATION_HASH')
        decision = review['decisions'][row['code']]
        if any(not isinstance(decision.get(field), str) or not decision[field].strip() for field in ('reason', 'nextCheck', 'handling')):
            raise ValueError('INCOMPLETE_DISPOSITION')
        indexed[table] = row
    results = []
    current = schema['comparison']['runtimeMysqlColumns']
    for difference in current:
        table = difference['table']
        row = indexed.get(table)
        fingerprint = digest(column_observation(schema, difference))
        status = 'UNREVIEWED' if row is None else 'SOURCE_OR_SCHEMA_CHANGED' if fingerprint != row['observationHash'] else 'DISPOSITION_VERIFIED'
        results.append({'table': table, 'status': status, 'observedHash': fingerprint,
                        'decision': row['code'] if status == 'DISPOSITION_VERIFIED' else None,
                        'difference': difference, 'purgeAuthorized': False, 'remediationComplete': False})
    absent = sorted(indexed.keys() - {row['table'] for row in current})
    unknown_keys = schema['comparison'].get('runtimeMysqlKeyContracts', [])
    return {'schemaVersion': 1, 'artifactType': 'M0_DISPOSITION_VERIFICATION',
        'sourceSha': source['sourceSha'], 'sourceManifestHash': source['sourceManifestHash'],
        'reviewedApplicationSha': review['reviewedApplicationSha'], 'reviewFileHash': digest(review),
        'results': results, 'retiredOrChangedReviewCases': absent,
        'counts': dict(Counter(row['status'] for row in results)),
        'decisionCounts': dict(Counter(row['decision'] for row in results if row['decision'])),
        'keyContractReviewRequired': len(unknown_keys),
        'status': 'REVIEW_REQUIRED' if absent or any(row['status'] != 'DISPOSITION_VERIFIED' for row in results) else 'DISPOSITIONS_VERIFIED_NOT_REMEDIATED',
        'limitations': ['This verifies explicit column-difference dispositions, not absence of all defects.',
                       'PK/FK/unique differences are separate; column review never suppresses them.',
                       'No customer rows, policy approvals, consumer closures or executable selectors are proven.'],
        'm0Complete': False, 'm1EntryApproved': False, 'deletionAuthorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('repo', 'inventory', 'schema-evidence', 'review', 'output'):
        parser.add_argument('--' + flag, required=True, type=Path)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args()
    repo, output = args.repo.resolve(strict=True), args.output.resolve()
    if output.is_relative_to(repo) or output.exists():
        parser.error('output must be new and outside the repository')
    inventory = load_check('module-commercial-inventory')
    verify = load_check('module-commercial-reconcile').verify_current_inventory
    try:
        if inventory.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or inventory.git_read(repo, 'status', '--porcelain'):
            raise ValueError('EXPECTED_CLEAN_EXACT_HEAD')
        review_path = args.review.resolve(strict=True)
        if not review_path.is_relative_to(repo):
            raise ValueError('REVIEW_MUST_BE_COMMITTED_IN_CURRENT_REPOSITORY')
        inventory.git_read(repo, 'ls-files', '--error-unmatch', '--', review_path.relative_to(repo).as_posix())
        review_bytes = review_path.read_bytes()
        source = unique_json(args.inventory.read_text(encoding='utf-8'))
        schema = unique_json(args.schema_evidence.read_text(encoding='utf-8'))
        verify(repo, source, args.expected_head)
        report = assess(repo, source, schema, unique_json(review_bytes.decode('utf-8')))
        verify(repo, source, args.expected_head)
        if review_path.read_bytes() != review_bytes or inventory.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or inventory.git_read(repo, 'status', '--porcelain'):
            raise ValueError('SOURCE_CHANGED_DURING_REVIEW')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps({key: report[key] for key in ('sourceSha', 'status', 'counts', 'decisionCounts', 'keyContractReviewRequired', 'm0Complete')}, ensure_ascii=False))
    except Exception as exc:
        parser.exit(2, f'M0 disposition verification stopped ({type(exc).__name__}); no stage approval issued.\n')


if __name__ == '__main__':
    main()
