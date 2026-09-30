#!/usr/bin/env python3
"""Verify M0 exceptional-resource boundaries. No executable selectors or approvals."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unique_json(text):
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                raise ValueError('DUPLICATE_JSON_KEY')
            output[key] = value
        return output
    return json.loads(text, object_pairs_hook=pairs)


def assess(repo: Path, source: dict, schema: dict, contract: dict) -> dict:
    """Check only structural/source assertions, never infer customer-row ownership."""
    if (not re.fullmatch(r'[0-9a-f]{40}', str(source.get('sourceSha', '')))
            or schema.get('sourceSha') != source['sourceSha']
            or schema.get('sourceManifestHash') != source.get('sourceManifestHash')):
        raise ValueError('SCHEMA_SOURCE_IDENTITY_MISMATCH')
    if (schema.get('collectionStatus') != 'PASS'
            or schema.get('mysql', {}).get('readerSelectOnly') is not True
            or schema['mysql'].get('readOnly') is not True
            or schema['mysql'].get('businessRowsRead') is not False):
        raise ValueError('REQUIRES_READ_ONLY_SCHEMA_EVIDENCE')
    if type(contract.get('schemaVersion')) is not int or contract['schemaVersion'] != 1 or contract.get('artifactType') != 'M0_BOUNDARY_REVIEW_NOT_EXECUTABLE':
        raise ValueError('INVALID_BOUNDARY_CONTRACT')
    for flag in ('implicitEmployment', 'implicitApiAccess', 'consumerClosureComplete', 'm0Complete', 'm1EntryApproved', 'deletionAuthorized'):
        if contract.get(flag) is not False:
            raise ValueError('BOUNDARY_REVIEW_CANNOT_GRANT_ACCESS_OR_APPROVAL')
    if contract.get('canonicalFeatures') != source.get('moduleMapping', {}).get('canonicalFeatures') or not contract.get('canonicalFeatures'):
        raise ValueError('MODULE_MAPPING_CHANGED')
    if not re.fullmatch(r'[0-9a-f]{40}', str(contract.get('reviewedApplicationSha', ''))):
        raise ValueError('MISSING_REVIEW_SOURCE')
    evidence = contract.get('evidence')
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError('MISSING_SOURCE_ANCHORS')
    anchor_text = {}
    for evidence_id, item in evidence.items():
        name = item['path']; path = repo / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink()
                or not path.resolve().is_relative_to(repo.resolve())):
            raise ValueError('UNSAFE_SOURCE_ANCHOR')
        content = path.read_bytes(); lines = content.decode('utf-8-sig').splitlines()
        if source['sourceFiles'].get(name) != item['sha256'] or hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError('SOURCE_ANCHOR_CHANGED')
        start, end = item['startLine'], item['endLine']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ValueError('INVALID_SOURCE_RANGE')
        anchor_text[evidence_id] = '\n'.join(lines[start-1:end])
        if item.get('symbol') is not None:
            matches = [n for n in ast.walk(ast.parse(content.decode('utf-8-sig'))) if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == item['symbol'] and n.lineno == start and n.end_lineno == end]
            if len(matches) != 1:
                raise ValueError('SOURCE_SYMBOL_CHANGED')
    declarations = source.get('models', [])
    models = {row['table']: row for row in declarations}
    runtime, physical = schema['metadata']['tables'], schema['mysql']['tables']
    if len(models) != len(declarations) or not models or not runtime or not physical:
        raise ValueError('INVALID_RESOURCE_UNIVERSE')
    universe = set(models) | set(runtime) | set(physical)
    fields = {name: set(models.get(name, {}).get('inheritedFieldNames', [])) | set(runtime.get(name, {}).get('columns', {})) | set(physical.get(name, {}).get('columns', {})) for name in universe}
    no_tenant = {name for name in universe if 'tenant_id' not in fields[name]}
    exceptions = {name for name in universe if not (name in models and name in runtime and name in physical)}

    def entries(key, identity='table'):
        rows = contract.get(key)
        if not isinstance(rows, list) or not rows:
            raise ValueError('MISSING_BOUNDARY_ROWS')
        result = {}
        for row in rows:
            name = row.get(identity)
            if not isinstance(name, str) or not name or name in result:
                raise ValueError('DUPLICATE_OR_INVALID_BOUNDARY')
            if identity == 'table' and name not in universe:
                raise ValueError('BOUNDARY_RESOURCE_MISSING')
            if row.get('purgeAuthorized') is not False or not row.get('evidence') or any(e not in evidence for e in row['evidence']):
                raise ValueError('INVALID_BOUNDARY_EVIDENCE_OR_APPROVAL')
            if identity == 'table' and not any(name in anchor_text[e] for e in row['evidence']):
                raise ValueError('RESOURCE_NOT_IN_SOURCE_ANCHOR')
            result[name] = row
        return result

    unscoped = entries('noTenantResources')
    if set(unscoped) != no_tenant:
        raise ValueError('NO_TENANT_REVIEW_COVERAGE_CHANGED')
    for name, row in unscoped.items():
        if row.get('scopeKind') not in {'AUTH_CONTROL','GLOBAL_CONTROL','MULTI_TENANT_CONTROL','GLOBAL_FOUNDATION','PARENT_CONTROL','SELF_TENANT_KEY'} or row.get('selectorImplemented') is not False:
            raise ValueError('INVALID_SCOPE_CONTRACT')
        if not row.get('requiredFields') or not set(row['requiredFields']) <= fields[name] or not set(row.get('relatedTables', [])) <= universe or not row.get('interpretation'):
            raise ValueError('SCOPE_SOURCE_RELATION_CHANGED')
    exceptional = entries('exceptionalTables')
    if set(exceptional) != exceptions:
        raise ValueError('EXCEPTIONAL_RESOURCE_COVERAGE_CHANGED')
    for name, row in exceptional.items():
        presence = {'ast': name in models, 'metadata': name in runtime, 'mysql': name in physical}
        if row.get('presence') != presence or any(type(v) is not bool for v in row['presence'].values()) or row.get('runtimeIntegrationVerified') is not False:
            raise ValueError('EXCEPTIONAL_PRESENCE_CHANGED')
        if row.get('kind') not in {'INTENTIONALLY_UNREGISTERED','LATE_MODEL_REGISTRATION','DYNAMIC_TABLE','SQL_ONLY'} or not row.get('interpretation'):
            raise ValueError('INVALID_EXCEPTIONAL_DISPOSITION')
    shared = entries('sharedFoundation')
    if set(shared) != {'t_tenant','t_user','t_role','t_permission','t_student_profile','t_college','t_major','t_class'}:
        raise ValueError('SHARED_FOUNDATION_COVERAGE_CHANGED')
    for row in shared.values():
        if row.get('ownershipClass') != 'SHARED_FOUNDATION' or row.get('onModuleExit') != 'PRESERVE':
            raise ValueError('SHARED_FOUNDATION_MUST_BE_PRESERVED')
    consumers = entries('consumerCheckpoints', 'id')
    for row in consumers.values():
        if row.get('sourceModule') not in set(contract['canonicalFeatures']) | {'SHARED'} or row.get('runtimeRetirementTest') != 'NOT_RUN' or not row.get('requiredHandling'):
            raise ValueError('INVALID_CONSUMER_CHECKPOINT')
    key_cases = entries('keyDispositions')
    current_keys = {row['table']: row for row in schema.get('comparison', {}).get('runtimeMysqlKeyContracts', [])}
    if set(key_cases) != set(current_keys):
        raise ValueError('KEY_DISPOSITION_COVERAGE_CHANGED')
    for name, row in key_cases.items():
        if row.get('observation') != current_keys[name] or row.get('remediationComplete') is not False or not row.get('handling'):
            raise ValueError('KEY_OBSERVATION_CHANGED')
    return {'schemaVersion': 1, 'artifactType': 'M0_BOUNDARY_VERIFICATION_NOT_APPROVAL',
        'sourceSha': source['sourceSha'], 'sourceManifestHash': source['sourceManifestHash'],
        'status': 'STRUCTURAL_BOUNDARY_ASSERTIONS_VERIFIED',
        'counts': {'resourceUniverse': len(universe), 'noTenantBoundaries': len(unscoped), 'exceptionalResources': len(exceptional), 'sharedFoundation': len(shared), 'consumerCheckpoints': len(consumers), 'sourceAnchors': len(evidence), 'keyDispositions': len(key_cases)},
        'remaining': ['Full consumer closure and actual row-level selectors remain unverified.', 'Single-module golden journeys, final integrated baseline and policy publication remain gated.'],
        'm0Complete': False, 'm1EntryApproved': False, 'deletionAuthorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('repo','inventory','schema-evidence','contract','output'):
        parser.add_argument('--'+flag, required=True, type=Path)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args(); repo, output = args.repo.resolve(strict=True), args.output.resolve()
    if output.is_relative_to(repo) or output.exists():
        parser.error('output must be new and outside the repository')
    try:
        inventory, reconcile = load('module-commercial-inventory'), load('module-commercial-reconcile')
        if inventory.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or inventory.git_read(repo, 'status', '--porcelain'):
            raise ValueError('EXPECTED_CLEAN_EXACT_HEAD')
        contract_path = args.contract.resolve(strict=True)
        if args.contract.is_symlink() or not contract_path.is_relative_to(repo):
            raise ValueError('CONTRACT_MUST_BE_COMMITTED')
        inventory.git_read(repo, 'ls-files', '--error-unmatch', '--', contract_path.relative_to(repo).as_posix())
        contract_bytes = contract_path.read_bytes()
        source = unique_json(args.inventory.read_text(encoding='utf-8')); schema = unique_json(args.schema_evidence.read_text(encoding='utf-8'))
        reconcile.verify_current_inventory(repo, source, args.expected_head)
        if reconcile.reconcile(source, schema['metadata'], schema['mysql']) != schema.get('comparison'):
            raise ValueError('SCHEMA_COMPARISON_CHANGED')
        result = assess(repo, source, schema, unique_json(contract_bytes.decode('utf-8')))
        reconcile.verify_current_inventory(repo, source, args.expected_head)
        if contract_path.read_bytes() != contract_bytes or inventory.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or inventory.git_read(repo, 'status', '--porcelain'):
            raise ValueError('SOURCE_CHANGED_DURING_REVIEW')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream: json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        parser.exit(2, f'M0 boundary verification stopped ({type(exc).__name__}); no stage approval issued.\n')


if __name__ == '__main__':
    main()
