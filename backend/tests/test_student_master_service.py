"""统一主档写入口回归锁（学生主档统一整改 阶段 B）。

锁四条不变量：
1. 全仓只有 student_master_application_service 能构造 StudentProfile（四条建档链已收敛）；
2. 组织父链必须自洽（班级属于专业、专业属于学院，跨租户不可见）；
3. 主档更新必须带 expectedVersion 且做原子 CAS（并发不能后写覆盖前写）；
4. 普通编辑不得改组织归属（须走学籍异动）。
"""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException


# ── 1. 建档入口已收敛 ──────────────────────────────────────────────────────

def test_only_master_service_constructs_student_profile():
    """业务代码不得再直接 StudentProfile(...)；演示 seed 与服务自身除外。"""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    allowed_files = {
        "student_master_application_service.py",  # 唯一合法写入口
        "platform_service.py", "sandbox_service.py",  # 演示/沙箱 seed
    }
    rx = re.compile(r"(?<!class )\bStudentProfile\s*\(")
    offenders = []
    for path in root.rglob("*.py"):
        if path.name in allowed_files or "__pycache__" in path.parts:
            continue
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or not rx.search(line):
                continue
            # 跳过 docstring 里的说明文字
            if "StudentProfile(" in stripped and ("复用" in stripped or "此前各自" in stripped):
                continue
            offenders.append(f"{path.name}:{no} {stripped[:70]}")
    assert not offenders, "发现绕过统一服务的建档点：\n" + "\n".join(offenders)


@pytest.mark.parametrize("module_path,func_name", [
    ("app.services.db_service", "create_student"),
    ("app.services.import_export_service", "confirm"),
    ("app.services.school_onboarding_service", "run_onboarding"),
    ("app.modules.academic_affairs.services.academic_affairs_service", "_persist_roster_rows"),
])
def test_creation_paths_delegate_to_master_service(module_path, func_name):
    """四条建档链都必须调统一服务，而不是自己拼 ORM。"""
    import importlib

    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name, None)
    if fn is None:
        pytest.skip(f"{module_path}.{func_name} 不存在（函数名可能已变，需同步本测试）")
    src = inspect.getsource(fn)
    assert "create_student_in_session" in src, f"{func_name} 未经统一服务建档"


# ── 2. 组织父链校验 ────────────────────────────────────────────────────────
# db_mode 每个测试重建干净库且不 seed 组织数据，故这里自建学院/专业/班级，
# 不依赖既有数据（依赖既有数据会让核心校验在空库上静默 skip，等于没测）。

TID = 1000000000000000001


def _seed_org(db):
    """建两套学院→专业，外加一个挂在 major_a 下的班级，用于构造父子冲突。"""
    from app.models.org import College, Major, SchoolClass

    col_a = College(tenant_id=TID, college_name="信息工程学院", status="ACTIVE")
    col_b = College(tenant_id=TID, college_name="机电工程学院", status="ACTIVE")
    db.add_all([col_a, col_b])
    db.flush()
    maj_a = Major(tenant_id=TID, college_id=col_a.id, major_name="软件技术", status="ACTIVE")
    maj_b = Major(tenant_id=TID, college_id=col_b.id, major_name="数控技术", status="ACTIVE")
    db.add_all([maj_a, maj_b])
    db.flush()
    cls_a = SchoolClass(tenant_id=TID, major_id=maj_a.id, class_name="软件2601",
                        grade="2026", status="ACTIVE")
    db.add(cls_a)
    db.flush()
    return {"col_a": col_a, "col_b": col_b, "maj_a": maj_a, "maj_b": maj_b, "cls_a": cls_a}


def test_org_validator_rejects_mismatched_parent_chain(db_mode):
    """班级不属于所选专业 → 422，不能默默写进主档。"""
    from app.db.session import get_sessionmaker
    from app.services.student_org_validator import validate_student_org_path

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        with pytest.raises(AppException) as ei:
            validate_student_org_path(db, tenant_id=TID, college_id=None,
                                      major_id=org["maj_b"].id, class_id=org["cls_a"].id,
                                      actor=None)
        assert "不属于" in str(getattr(ei.value, "message", "") or ei.value)
    finally:
        db.rollback()
        db.close()


def test_org_validator_rejects_major_not_in_college(db_mode):
    """专业不属于所选学院 → 422。"""
    from app.db.session import get_sessionmaker
    from app.services.student_org_validator import validate_student_org_path

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        with pytest.raises(AppException) as ei:
            validate_student_org_path(db, tenant_id=TID, college_id=org["col_b"].id,
                                      major_id=org["maj_a"].id, class_id=None, actor=None)
        assert "不属于" in str(getattr(ei.value, "message", "") or ei.value)
    finally:
        db.rollback()
        db.close()


def test_org_validator_backfills_parents_from_class(db_mode):
    """只传班级时应自动补齐专业与学院，保证落库三个 ID 自洽。"""
    from app.db.session import get_sessionmaker
    from app.services.student_org_validator import validate_student_org_path

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        got = validate_student_org_path(db, tenant_id=TID, college_id=None, major_id=None,
                                        class_id=org["cls_a"].id, actor=None)
        assert got.class_id == org["cls_a"].id
        assert got.major_id == org["maj_a"].id, "应由班级反推专业"
        assert got.college_id == org["col_a"].id, "应由专业反推学院"
    finally:
        db.rollback()
        db.close()


def test_org_validator_rejects_cross_tenant(db_mode):
    """跨租户组织一律 404（防用 ID 枚举探测其它学校的组织结构）。"""
    from app.db.session import get_sessionmaker
    from app.services.student_org_validator import validate_student_org_path

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        with pytest.raises(AppException):
            validate_student_org_path(db, tenant_id=TID + 999999, college_id=None,
                                      major_id=None, class_id=org["cls_a"].id, actor=None)
    finally:
        db.rollback()
        db.close()


def test_org_validator_rejects_disbanded_class(db_mode):
    """已解散班级不得作为新生归属。"""
    from app.db.session import get_sessionmaker
    from app.services.student_org_validator import validate_student_org_path

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        org["cls_a"].class_status = "DISBANDED"
        db.flush()
        with pytest.raises(AppException) as ei:
            validate_student_org_path(db, tenant_id=TID, college_id=None, major_id=None,
                                      class_id=org["cls_a"].id, actor=None)
        assert "解散" in str(getattr(ei.value, "message", "") or ei.value)
    finally:
        db.rollback()
        db.close()


# ── 3 & 4. 更新口径 ────────────────────────────────────────────────────────

def test_update_requires_expected_version():
    """缺 expectedVersion 必须拒绝，否则并发保存会互相覆盖。"""
    from app.core.student_master_contract import StudentIdentityUpdateCommand
    from app.services import student_master_application_service as master

    src = inspect.getsource(master.update_identity_in_session)
    assert "expected_version" in src and "DATA_CONFLICT" in src
    # 命令对象把 expected_version 放在首位且无默认值，调用方无法遗漏
    sig = inspect.signature(StudentIdentityUpdateCommand)
    assert sig.parameters["expected_version"].default is inspect.Parameter.empty


def test_update_uses_atomic_cas():
    """必须是条件更新（WHERE version=?），不能只做读-比-写。"""
    from app.services import student_master_application_service as master

    src = inspect.getsource(master.update_identity_in_session)
    assert "StudentProfile.version == current_version" in src, "缺少原子 CAS 条件"
    assert "synchronize_session=False" in src


def test_normal_edit_rejects_org_fields():
    """普通主档编辑传学院/专业/班级要显式报错，不能像以前那样静默忽略。"""
    from app.services import db_service

    src = inspect.getsource(db_service.update_student)
    for field in ("collegeId", "majorId", "classId"):
        assert field in src
    assert "学籍异动" in src, "拒绝时必须指明正确路径"
