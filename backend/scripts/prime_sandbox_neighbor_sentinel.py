"""仅供 20K GitHub Gate 使用：预置/复核 demo-school 旁租户哨兵。

该脚本故意保持最小：1 个真实 Tenant + 20 个 StudentProfile。
--prime 只允许在迁移后的门禁空库中落哨兵；--verify 只读且绝不补数据。
随后 standard-20k 全量 reset 必须同时通过自身 20→20 计数保护和本脚本逐行复核。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WORKFLOW_NAME = "Sandbox 20K Real-School Data Gate"
DEMO_TID = 1000000000000000012
DEMO_CODE = "demo-school"
SENTINEL_COUNT = 20


def _expected_rows() -> dict[str, tuple[str, str, str, str, str]]:
    return {
        f"D-SENT-{index:04d}": (
            f"旁租户哨兵{index:02d}",
            "2025",
            "ENROLLED",
            "NORMAL",
            "ACTIVE",
        )
        for index in range(1, SENTINEL_COUNT + 1)
    }


def _assert_gate_only() -> None:
    if os.getenv("GITHUB_WORKFLOW") != WORKFLOW_NAME:
        raise RuntimeError("仅允许 Sandbox 20K Real-School Data Gate 调用旁租户哨兵脚本")


def _load_actual(db, StudentProfile) -> dict[str, tuple[str, str, str, str, str]]:
    rows = db.execute(select(
        StudentProfile.student_no,
        StudentProfile.real_name,
        StudentProfile.grade,
        StudentProfile.current_stage,
        StudentProfile.student_status,
        StudentProfile.status,
    ).where(
        StudentProfile.tenant_id == DEMO_TID,
        StudentProfile.is_deleted.is_(False),
    ).order_by(StudentProfile.student_no)).all()
    return {
        str(student_no): (
            str(real_name),
            str(grade),
            str(current_stage),
            str(student_status),
            str(status),
        )
        for student_no, real_name, grade, current_stage, student_status, status in rows
    }


def _resolve_tenant(db, Tenant, *, create: bool):
    by_id = db.get(Tenant, DEMO_TID)
    by_code = db.scalars(select(Tenant).where(Tenant.tenant_code == DEMO_CODE)).first()
    if by_id is not None and by_id.tenant_code != DEMO_CODE:
        raise RuntimeError(
            f"固定旁租户ID已被占用 id={DEMO_TID} code={by_id.tenant_code!r}"
        )
    if by_code is not None and int(by_code.id) != DEMO_TID:
        raise RuntimeError(
            f"demo-school code 已绑定其他租户 id={by_code.id} expected={DEMO_TID}"
        )
    tenant = by_id or by_code
    if tenant is None and create:
        tenant = Tenant(
            id=DEMO_TID,
            tenant_code=DEMO_CODE,
            school_name="demo-school 旁租户保护哨兵",
            short_name="旁租户哨兵",
            deploy_mode="SAAS",
            db_mode="SHARED",
            status="ACTIVE",
        )
        db.add(tenant)
        db.flush()
    if tenant is None:
        raise RuntimeError("demo-school 旁租户不存在；verify 禁止自动补建")
    return tenant


def prime(db, StudentProfile, Tenant) -> None:
    _resolve_tenant(db, Tenant, create=True)
    expected = _expected_rows()
    actual = _load_actual(db, StudentProfile)
    if actual and actual != expected:
        raise RuntimeError(
            "demo-school 旁租户不是空库哨兵状态，拒绝覆盖现有学生事实："
            f"expected={SENTINEL_COUNT} actual={len(actual)}"
        )
    if not actual:
        for student_no, (real_name, grade, current_stage, student_status, status) in expected.items():
            db.add(StudentProfile(
                tenant_id=DEMO_TID,
                student_no=student_no,
                real_name=real_name,
                grade=grade,
                current_stage=current_stage,
                student_status=student_status,
                status=status,
            ))
        db.commit()
    verify(db, StudentProfile, Tenant)


def verify(db, StudentProfile, Tenant) -> None:
    tenant = _resolve_tenant(db, Tenant, create=False)
    if tenant.status != "ACTIVE":
        raise RuntimeError(f"demo-school 旁租户状态被修改: {tenant.status!r}")
    actual = _load_actual(db, StudentProfile)
    expected = _expected_rows()
    if actual != expected:
        missing = sorted(set(expected) - set(actual))[:10]
        extra = sorted(set(actual) - set(expected))[:10]
        changed = [
            student_no
            for student_no in sorted(set(expected) & set(actual))
            if expected[student_no] != actual[student_no]
        ][:10]
        raise RuntimeError(
            "demo-school 旁租户哨兵被改变："
            f"expected={SENTINEL_COUNT} actual={len(actual)} "
            f"missing={missing} extra={extra} changed={changed}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="20K Gate 旁租户保护哨兵")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prime", action="store_true", help="迁移后空库预置旁租户哨兵")
    mode.add_argument("--verify", action="store_true", help="全量 reset 后只读复核旁租户哨兵")
    args = ap.parse_args()

    try:
        _assert_gate_only()
    except RuntimeError as exc:
        print(f"[20k-neighbor-sentinel] FAIL {exc}")
        return 2

    from app.db.session import db_enabled, get_sessionmaker
    from app.models import StudentProfile, Tenant

    if not db_enabled():
        print("[20k-neighbor-sentinel] FAIL DB_ENABLED=false")
        return 3

    db = get_sessionmaker()()
    try:
        if args.prime:
            prime(db, StudentProfile, Tenant)
            action = "PRIME"
        else:
            verify(db, StudentProfile, Tenant)
            action = "VERIFY"
        print(
            f"[20k-neighbor-sentinel] PASS action={action} tenant={DEMO_CODE} "
            f"tenantId={DEMO_TID} students={SENTINEL_COUNT}"
        )
        return 0
    except RuntimeError as exc:
        db.rollback()
        print(f"[20k-neighbor-sentinel] FAIL {exc}")
        return 4
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())