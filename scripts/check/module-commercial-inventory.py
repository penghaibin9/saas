#!/usr/bin/env python3
"""M0 read-only source inventory. This is never a deletion selector or approval.

Only Python AST and Git metadata are read; application imports and database
connections are deliberately absent. Output must be new and outside the repo.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

MODULE_FEATURES = {
    "internship": "internship", "graduationDesign": "graduation",
    "studentAffairs": "studentAffairs", "academicAffairs": "academicAffairs",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def git_read(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            capture_output=True, text=True, timeout=15,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    return result.stdout.strip()


def assignment_values(nodes: list[ast.stmt]) -> dict[str, ast.expr | None]:
    values: dict[str, ast.expr | None] = {}
    for node in nodes:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            values[node.target.id] = node.value
    return values


def literal(node: ast.expr | None) -> Any:
    if node is None:
        return None
    return ast.literal_eval(node)


def python_paths(root: Path, repo: Path, issues: list[dict]) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        issues.append({"path": str(root.relative_to(repo)), "code": "SOURCE_ROOT_UNAVAILABLE"})
        return []
    paths = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs):
            path = Path(directory) / name
            if path.is_symlink():
                issues.append({"path": str(path.relative_to(repo)), "code": "SYMLINK_NOT_SCANNED"})
                dirs.remove(name)
            elif name == "__pycache__":
                dirs.remove(name)
        for name in files:
            if not name.endswith(".py"):
                continue
            path = Path(directory) / name
            if path.is_symlink():
                issues.append({"path": str(path.relative_to(repo)), "code": "SYMLINK_NOT_SCANNED"})
            else:
                paths.append(path)
    return sorted(paths)


def module_mapping(manifest: dict) -> dict:
    modules = manifest.get("modules")
    if not isinstance(modules, list):
        raise ValueError("module manifest has no modules list")
    keys = [item.get("moduleKey") for item in modules if isinstance(item, dict)]
    if len(keys) != len(modules) or len(set(keys)) != len(keys):
        raise ValueError("module manifest has duplicate or malformed keys")
    indexed = {item["moduleKey"]: item for item in modules}
    for key, feature in MODULE_FEATURES.items():
        if indexed.get(key, {}).get("featureKey") != feature:
            raise ValueError(f"commercial module mapping drift: {key}")
    if indexed.get("employment", {}).get("featureKey") != "employment":
        raise ValueError("employment must remain independent")
    if "graduation" not in indexed["graduationDesign"].get("aliases", []):
        raise ValueError("graduation compatibility alias missing")
    return {"manifestVersion": manifest.get("manifestVersion"),
            "canonicalFeatures": MODULE_FEATURES, "implicitEmployment": False,
            "implicitApiAccess": False, "sharedCapabilitiesReview": "PENDING",
            "warning": "Navigation dataOwner is not a resource deletion owner."}


def inventory(repo: Path) -> dict:
    repo = repo.resolve(strict=True)
    issues: list[dict] = []
    hashes: dict[str, str] = {}
    classes: list[dict] = []
    migrations: list[dict] = []
    dynamic_tables: list[dict] = []
    app_paths = python_paths(repo / "backend/app", repo, issues)
    migration_paths = python_paths(repo / "backend/alembic/versions", repo, issues)
    for path in app_paths + migration_paths:
        relative = path.relative_to(repo).as_posix()
        try:
            source = path.read_bytes()
            hashes[relative] = hashlib.sha256(source).hexdigest()
            tree = ast.parse(source.decode("utf-8-sig"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            issues.append({"path": relative, "code": "SOURCE_PARSE_ERROR", "errorType": type(exc).__name__})
            continue
        if path in migration_paths:
            assigned = assignment_values(tree.body)
            if "revision" not in assigned:
                if path.name != "__init__.py":
                    issues.append({"path": relative, "code": "MISSING_MIGRATION_REVISION"})
                continue
            try:
                revision = literal(assigned["revision"])
                down = literal(assigned.get("down_revision"))
                parents = [] if down is None else [down] if isinstance(down, str) else list(down)
                if not isinstance(revision, str) or not revision or any(not isinstance(p, str) or not p for p in parents):
                    raise ValueError("invalid revision")
                migrations.append({"path": relative, "revision": revision, "parents": parents})
            except (ValueError, TypeError, SyntaxError):
                issues.append({"path": relative, "code": "DYNAMIC_MIGRATION_REQUIRES_REVIEW"})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and ast.unparse(node.func).split(".")[-1] == "Table":
                dynamic_tables.append({"path": relative, "line": node.lineno, "kind": "TABLE_CALL_REVIEW"})
            if not isinstance(node, ast.ClassDef):
                continue
            assigned = assignment_values(node.body)
            columns = {}
            for key, value in assigned.items():
                if isinstance(value, ast.Call) and ast.unparse(value.func).split(".")[-1] in {"mapped_column", "Column"}:
                    foreign_keys = []
                    for call in ast.walk(value):
                        if isinstance(call, ast.Call) and ast.unparse(call.func).split(".")[-1] == "ForeignKey":
                            target = call.args[0] if call.args else None
                            foreign_keys.append(target.value if isinstance(target, ast.Constant) and isinstance(target.value, str) else "UNRESOLVED")
                    columns[key] = {"line": value.lineno, "foreignKeys": foreign_keys}
            table = None
            if "__tablename__" in assigned:
                try:
                    table = literal(assigned["__tablename__"])
                    if not isinstance(table, str) or not table:
                        raise ValueError("not a literal table")
                except (ValueError, TypeError, SyntaxError):
                    issues.append({"path": relative, "line": node.lineno, "code": "DYNAMIC_TABLE_REQUIRES_REVIEW"})
            if "__table__" in assigned:
                dynamic_tables.append({"path": relative, "line": node.lineno, "kind": "TABLE_ATTRIBUTE_REVIEW"})
            classes.append({"table": table, "model": node.name, "path": relative,
                            "startLine": node.lineno, "endLine": node.end_lineno,
                            "bases": [ast.unparse(base) for base in node.bases], "fields": columns})
    by_name: dict[str, list[dict]] = {}
    for entry in classes:
        by_name.setdefault(entry["model"], []).append(entry)

    def inherited(entry: dict, seen: frozenset[str] = frozenset()) -> set[str]:
        key = entry["path"] + ":" + entry["model"]
        if key in seen:
            return set()
        fields = set(entry["fields"])
        for base in entry["bases"]:
            candidates = by_name.get(base, [])
            if len(candidates) == 1:
                fields.update(inherited(candidates[0], seen | {key}))
        return fields

    models = []
    for entry in classes:
        if not entry["table"]:
            continue
        names = inherited(entry)
        models.append({**entry, "fileSha256": hashes[entry["path"]],
                       "tenantScopedSyntactic": "tenant_id" in names,
                       "inheritedFieldNames": sorted(names),
                       "ownershipClass": "UNKNOWN", "reviewStatus": "UNREVIEWED",
                       "logicalIdFieldsToReview": sorted(name for name in names if name.endswith("_id") and name != "tenant_id"),
                       "purgeAuthorized": False})
    duplicates = sorted(table for table, count in Counter(m["table"] for m in models).items() if count > 1)
    revisions = Counter(m["revision"] for m in migrations)
    missing_parents = sorted({p for m in migrations for p in m["parents"]} - revisions.keys())
    heads = sorted(revisions.keys() - {p for m in migrations for p in m["parents"]})
    if duplicates:
        issues.append({"code": "DUPLICATE_TABLE_DECLARATIONS", "tables": duplicates})
    if any(count > 1 for count in revisions.values()) or missing_parents or len(heads) != 1:
        issues.append({"code": "MIGRATION_GRAPH_REQUIRES_REVIEW", "missingParents": missing_parents,
                       "duplicateRevisions": sorted(key for key, count in revisions.items() if count > 1), "heads": heads})
    manifest_path = repo / "shared/contracts/module-manifest.json"
    mapping = None
    try:
        if manifest_path.is_symlink():
            raise ValueError("symlink manifest")
        content = manifest_path.read_bytes()
        hashes[manifest_path.relative_to(repo).as_posix()] = hashlib.sha256(content).hexdigest()
        mapping = module_mapping(json.loads(content))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        issues.append({"code": "MODULE_MANIFEST_REQUIRES_REVIEW", "errorType": type(exc).__name__})
    changed_during_scan = []
    for relative, expected in hashes.items():
        path = repo / relative
        try:
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                changed_during_scan.append(relative)
        except OSError:
            changed_during_scan.append(relative)
    if changed_during_scan:
        issues.append({"code": "SOURCE_CHANGED_DURING_SCAN", "paths": changed_during_scan})
    return {"schemaVersion": 1, "evidenceLevel": "STATIC_ONLY", "sourceManifestHash": digest(hashes),
            "sourceFiles": hashes, "moduleMapping": mapping, "models": sorted(models, key=lambda m: (m["table"], m["path"])),
            "migrations": migrations, "staticMigrationHeads": heads, "additionalTableSites": dynamic_tables,
            "summary": {"pythonFiles": len(app_paths), "tableDeclarations": len(models), "uniqueTables": len({m["table"] for m in models}),
                        "migrationFiles": len(migrations), "issues": issues},
            "gates": {"staticScan": "FAIL" if issues else "PASS", "runtimeMetadata": "NOT_RUN", "mysqlSchema": "NOT_RUN",
                      "consumerClosure": "PENDING", "policyPublication": "PENDING", "m0Complete": False,
                      "runtimeEntitlementChanged": False, "deletionAuthorized": False}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    output = args.output.resolve()
    if output.is_relative_to(repo) or output.exists():
        parser.error("output must be a new file outside the repository")
    try:
        head = git_read(repo, "rev-parse", "HEAD")
        before = git_read(repo, "status", "--porcelain=v1", "--untracked-files=normal")
        if head != args.expected_head or before:
            raise ValueError("Expected clean exact-head source; no files were modified")
        result = inventory(repo)
        if git_read(repo, "rev-parse", "HEAD") != head or git_read(repo, "status", "--porcelain=v1", "--untracked-files=normal"):
            raise ValueError("Source changed during inventory")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        parser.exit(2, f"Inventory stopped: {exc}\n")
    result["sourceSha"] = head
    result["generatedAtUtc"] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"sourceSha": head, "output": str(output), **result["summary"], "gates": result["gates"]}, ensure_ascii=False))
    return 0 if result["gates"]["staticScan"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
