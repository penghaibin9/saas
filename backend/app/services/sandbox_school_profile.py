"""sandbox-school 数据档位识别。

平台恢复不能只用“学生数恰好 20,000”判断 standard-20k：
若真实试点数据因人工操作暂时变成 19,999，错误回落 legacy-100 会造成二次破坏。
本模块用学生规模 + 20K 专属 staff/org 签名分类；受损 standard 只能报错修复，绝不降级。
"""
from __future__ import annotations

from sqlalchemy import func, select

PROFILE_STANDARD = "standard-20k"
PROFILE_STANDARD_DAMAGED = "standard-20k-damaged"
PROFILE_LEGACY = "legacy-100"
PROFILE_UNKNOWN = "unknown"

EXPECTED_STUDENTS = 20_000
EXPECTED_COLLEGES = 8
EXPECTED_MAJORS = 32
EXPECTED_CLASSES = 384
EXPECTED_BACKGROUND_STAFF = 1_280


def classify_sandbox_profile(db, tenant_id: int) -> dict:
    from app.models import College, Major, SchoolClass, StudentProfile, User

    def count(model, *extra) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            *extra,
        )) or 0)

    students = count(StudentProfile, StudentProfile.is_deleted.is_(False))
    colleges = count(College, College.is_deleted.is_(False))
    majors = count(Major, Major.is_deleted.is_(False))
    classes = count(SchoolClass, SchoolClass.is_deleted.is_(False))
    background_staff = count(
        User,
        User.login_name.like("sbx_%"),
        User.is_deleted.is_(False),
    )

    exact_standard = (
        students == EXPECTED_STUDENTS
        and colleges == EXPECTED_COLLEGES
        and majors == EXPECTED_MAJORS
        and classes == EXPECTED_CLASSES
        and background_staff == EXPECTED_BACKGROUND_STAFF
    )
    standard_signature = (
        background_staff >= 1_000
        or (
            students >= 10_000
            and colleges >= EXPECTED_COLLEGES
            and majors >= EXPECTED_MAJORS
            and classes >= 300
        )
    )
    legacy_signature = (
        students <= 500
        and background_staff < 100
        and colleges <= 8
        and majors <= 20
        and classes <= 50
    )

    if exact_standard:
        profile = PROFILE_STANDARD
    elif standard_signature:
        profile = PROFILE_STANDARD_DAMAGED
    elif legacy_signature:
        profile = PROFILE_LEGACY
    else:
        profile = PROFILE_UNKNOWN

    return {
        "profile": profile,
        "students": students,
        "colleges": colleges,
        "majors": majors,
        "classes": classes,
        "backgroundStaffAccounts": background_staff,
    }


def is_standard_family(report: dict) -> bool:
    return report.get("profile") in {PROFILE_STANDARD, PROFILE_STANDARD_DAMAGED}
