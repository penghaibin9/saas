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


REANCHOR_FILE = "M0-schema-evidence-reanchors.json"


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


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_review_path(repo: Path, name: str) -> Path:
    path = repo / name
    if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
        raise ValueError('UNSAFE_REVIEW_PATH')
    return path


def _validate_reanchor_contract(repo: Path, source_files: dict, review: dict, reanchors: dict | None) -> dict:
    if reanchors is None:
        return {}
    if (
        reanchors.get('schemaVersion') != 1
        or reanchors.get('artifactType') != 'M0_SCHEMA_EVIDENCE_REANCHORS_NOT_APPROVAL'
        or reanchors.get('deletionAuthorized') is not False
        or reanchors.get('purgeAuthorized') is not False
    ):
        raise ValueError('REANCHOR_NOT_REVIEW_ONLY')
    entries = reanchors.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('REANCHOR_ENTRIES_MISSING')

    resolved = {}
    covered_stale = set()
    for row in entries:
        name = row.get('path', '')
        current_path = _safe_review_path(repo, name)
        previous_sha = str(row.get('fromSha256', ''))
        current_sha = str(row.get('toSha256', ''))
        source_change_commit = str(row.get('sourceChangeCommit', ''))
        offset = row.get('lineOffset')
        window = row.get('changeWindow') or {}
        evidence_ids = row.get('evidenceIds')
        reason = row.get('reason')
        if not re.fullmatch(r'[0-9a-f]{64}', previous_sha) or not re.fullmatch(r'[0-9a-f]{64}', current_sha) or previous_sha == current_sha:
            raise ValueError('INVALID_REANCHOR_HASH')
        if not re.fullmatch(r'[0-9a-f]{40}', source_change_commit):
            raise ValueError('REANCHOR_CHANGE_COMMIT_MISSING')
        if type(offset) is not int or not -10000 <= offset <= 10000:
            raise ValueError('INVALID_REANCHOR_LINE_OFFSET')
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('REANCHOR_REASON_MISSING')
        if not isinstance(evidence_ids, list) or not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError('INVALID_REANCHOR_EVIDENCE_IDS')
        if any(type(window.get(k)) is not int for k in ('oldStart', 'oldEnd', 'newStart', 'newEnd')):
            raise ValueError('INVALID_REANCHOR_CHANGE_WINDOW')
        old_start, old_end = window['oldStart'], window['oldEnd']
        new_start, new_end = window['newStart'], window['newEnd']
        if not (1 <= old_start <= old_end and 1 <= new_start <= new_end):
            raise ValueError('INVALID_REANCHOR_CHANGE_WINDOW')
        if old_start != new_start:
            raise ValueError('REANCHOR_WINDOW_OFFSET_MISMATCH')
        net_offset = (new_end - new_start + 1) - (old_end - old_start + 1)

        content = current_path.read_bytes()
        if source_files.get(name) != current_sha or _sha256(content) != current_sha:
            raise ValueError('REANCHOR_CURRENT_SOURCE_CHANGED')
        line_count = len(content.decode('utf-8-sig').splitlines())

        for evidence_id in evidence_ids:
            if evidence_id in resolved:
                raise ValueError('DUPLICATE_REANCHOR_EVIDENCE')
            item = review['evidence'].get(evidence_id)
            if not item:
                raise ValueError('REANCHOR_EVIDENCE_MISSING')
            if item.get('path') != name or item.get('sha256') != previous_sha:
                raise ValueError('REANCHOR_EVIDENCE_SOURCE_MISMATCH')
            start, end = item.get('startLine'), item.get('endLine')
            if type(start) is not int or type(end) is not int or not 1 <= start <= end:
                raise ValueError('INVALID_REVIEW_LINE_RANGE')

            # One source edit can leave reviewed evidence on both sides of the
            # changed window. Evidence wholly before the window keeps offset 0;
            # evidence wholly after it moves by the net line delta. Any anchor
            # touching the changed window requires a fresh M0 disposition instead
            # of a line-only reanchor receipt.
            if end < old_start:
                expected_offset = 0
            elif start > old_end:
                expected_offset = net_offset
            else:
                raise ValueError('REANCHOR_OVERLAPS_CHANGED_EVIDENCE')
            if offset != expected_offset:
                raise ValueError('REANCHOR_WINDOW_OFFSET_MISMATCH')

            current_start, current_end = start + offset, end + offset
            if not 1 <= current_start <= current_end <= line_count:
                raise ValueError('INVALID_REANCHOR_RESOLVED_LINE_RANGE')
            resolved[evidence_id] = {
                'path': name,
                'sha256': current_sha,
                'startLine': current_start,
                'endLine': current_end,
                'reanchored': True,
                'sourceChangeCommit': source_change_commit,
            }
            covered_stale.add(evidence_id)

    stale = {
        key for key, item in review['evidence'].items()
        if source_files.get(item.get('path')) != item.get('sha256')
    }
    if stale != covered_stale:
        raise ValueError('REANCHOR_STALE_EVIDENCE_COVERAGE_MISMATCH')
    return resolved


def validate_review_evidence(repo: Path, source_files: dict, review: dict, reanchors: dict | None = None) -> dict:
    if not isinstance(review.get('evidence'), dict) or not review['evidence']:
        raise ValueError('REVIEW_EVIDENCE_MISSING')
    resolved = _validate_reanchor_contract(repo, source_files, review, reanchors)
    for evidence_id, item in review['evidence'].items():
        if evidence_id in resolved:
            continue
        name = item['path']
        path = _safe_review_path(repo, name)
        content = path.read_bytes()
        if source_files.get(name) != item['sha256'] or _sha256(content) != item['sha256']:
            raise ValueError('REVIEW_SOURCE_CONTENT_CHANGED')
        start, end = item['startLine'], item['endLine']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(content.decode('utf-8-sig').splitlines()):
            raise ValueError('INVALID_REVIEW_LINE_RANGE')
        resolved[evidence_id] = {
            'path': name,
            'sha256': item['sha256'],
            'startLine': start,
            'endLine': end,
            'reanchored': False,
        }
    return resolved


def assess(repo: Path, source: dict, schema: dict, review: dict, reanchors: dict | None = None):
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
    resolved_evidence = validate_review_evidence(repo, source['sourceFiles'], review, reanchors)
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
    reanchored = sorted(key for key, item in resolved_evidence.items() if item['reanchored'])
    return {'schemaVersion': 1, 'artifactType': 'M0_DISPOSITION_VERIFICATION',
        'sourceSha': source['sourceSha'], 'sourceManifestHash': source['sourceManifestHash'],
        'reviewedApplicationSha': review['reviewedApplicationSha'], 'reviewFileHash': digest(review),
        'reanchorContractHash': digest(reanchors) if reanchors else None,
        'reanchoredEvidence': reanchored, 'reanchoredEvidenceCount': len(reanchored),
        'results': results, 'retiredOrChangedReviewCases': absent,
        'counts': dict(Counter(row['status'] for row in results)),
        'decisionCounts': dict(Counter(row['decision'] for row in results if row['decision'])),
        'keyContractReviewRequired': len(unknown_keys),
        'status': 'REVIEW_REQUIRED' if absent or any(row['status'] != 'DISPOSITION_VERIFIED' for row in results) else 'DISPOSITIONS_VERIFIED_NOT_REMEDIATED',
        'limitations': ['This verifies explicit column-difference dispositions, not absence of all defects.',
                       'PK/FK/unique differences are separate; column review never suppresses them.',
                       'Evidence re-anchors only relocate previously reviewed line ranges wholly outside an explicit source-change window; they do not approve a purge.',
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
        reanchor_path = review_path.with_name(REANCHOR_FILE)
        reanchor_bytes = None
        reanchors = None
        if reanchor_path.exists():
            if not reanchor_path.resolve().is_relative_to(repo):
                raise ValueError('REANCHOR_MUST_BE_COMMITTED_IN_CURRENT_REPOSITORY')
            inventory.git_read(repo, 'ls-files', '--error-unmatch', '--', reanchor_path.relative_to(repo).as_posix())
            reanchor_bytes = reanchor_path.read_bytes()
            reanchors = unique_json(reanchor_bytes.decode('utf-8'))
        source = unique_json(args.inventory.read_text(encoding='utf-8'))
        schema = unique_json(args.schema_evidence.read_text(encoding='utf-8'))
        verify(repo, source, args.expected_head)
        report = assess(repo, source, schema, unique_json(review_bytes.decode('utf-8')), reanchors)
        verify(repo, source, args.expected_head)
        if (
            review_path.read_bytes() != review_bytes
            or (reanchor_bytes is not None and reanchor_path.read_bytes() != reanchor_bytes)
            or inventory.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head
            or inventory.git_read(repo, 'status', '--porcelain')
        ):
            raise ValueError('SOURCE_CHANGED_DURING_REVIEW')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps({key: report[key] for key in ('sourceSha', 'status', 'counts', 'decisionCounts', 'keyContractReviewRequired', 'reanchoredEvidenceCount', 'm0Complete')}, ensure_ascii=False))
    except Exception as exc:
        parser.exit(2, f'M0 disposition verification stopped ({type(exc).__name__}); no stage approval issued.\n')


if __name__ == '__main__':
    main()
