#!/usr/bin/env python3
"""Issue unique short-lived token pools for an internship capacity fixture manifest.

Tokens are written to an ignored local directory and are never printed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.security import create_access_token


def _load_manifest(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing internship fixture manifest: {path}") from exc
    if doc.get("fixture") != "internship-school-scale-v1":
        raise SystemExit("unexpected internship fixture manifest")
    if doc.get("seeded") is not True:
        raise SystemExit("internship token pool requires a seeded fixture manifest")
    return doc


def _student_token(tenant_id: int, index: int) -> str:
    student_no = f"CAP-INT-{index:05d}"
    return create_access_token(
        {
            "userId": f"capacity-internship-student-{index:05d}",
            "loginName": student_no,
            "realName": f"容量实习学生{index:05d}",
            "userType": "STUDENT",
            "tid": "capacity-internship",
            "tenantId": str(tenant_id),
            "activeContextId": f"capacity-internship-student-context-{index:05d}",
            "currentRoleCode": "STUDENT",
            "clientType": "MP",
            "studentNo": student_no,
        },
        expires_in=7200,
    )


def _teacher_token(tenant_id: int, index: int) -> str:
    return create_access_token(
        {
            "userId": f"capacity-internship-teacher-{index:05d}",
            "loginName": f"CAP-INT-TEACHER-{index:05d}",
            "realName": f"容量实习教师{index:05d}",
            "userType": "TEACHER",
            "tid": "capacity-internship",
            "tenantId": str(tenant_id),
            "activeContextId": f"capacity-internship-teacher-context-{index:05d}",
            "currentRoleCode": "SCHOOL_ADMIN",
            "clientType": "MP",
        },
        expires_in=7200,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue internship capacity token pools")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "performance/secrets/internship")
    parser.add_argument("--token-count", type=int, default=20)
    args = parser.parse_args()

    doc = _load_manifest(args.manifest)
    active = int(doc.get("activeInternCount") or 0)
    if not 1 <= args.token_count <= min(active, 3000):
        raise SystemExit(f"token-count must be between 1 and min(activeInternCount, 3000); active={active}")
    tenant_id = int(doc["tenantId"])

    args.out.mkdir(parents=True, exist_ok=True)
    students = [_student_token(tenant_id, i) for i in range(1, args.token_count + 1)]
    teachers = [_teacher_token(tenant_id, i) for i in range(1, args.token_count + 1)]
    (args.out / "student-tokens.json").write_text(json.dumps(students), encoding="utf-8")
    (args.out / "teacher-tokens.json").write_text(json.dumps(teachers), encoding="utf-8")
    (args.out / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    print(
        f"internship_capacity_tokens student={len(students)} teacher={len(teachers)} "
        f"tenant={tenant_id} unique_student_identities=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
