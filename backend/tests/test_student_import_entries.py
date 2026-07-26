"""学生导入两条正式入口的回归锁（学生主档统一整改 · 入口收敛）。

锁的不变量：
1. 学生主档只有两条正式写入路径，旧 /import/students/* 已删除且返回 404；
2. 任何正式建档都必须拥有完整、自洽、同租户的学院/专业/班级；
3. 已有学生只复用不重复建档；身份/组织/作废冲突一律阻断；
4. 学生模板不含教师字段，教师模板不含学生组织字段。
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException

TID = 1000000000000000001


# ── 1. 旧入口已删除 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,method", [
    ("/api/v1/import/students/validate", "post"),
    ("/api/v1/import/students/validate-file", "post"),
    ("/api/v1/import/students/confirm", "post"),
])
def test_legacy_student_import_endpoints_are_gone(client, auth_headers, path, method):
    """甲方明确不保留兼容层：不做 redirect / 410 / 代理转发，直接 404。"""
    resp = getattr(client, method)(path, headers=auth_headers, json={})
    assert resp.status_code == 404, f"{path} 仍然可达（{resp.status_code}）"


def test_legacy_import_service_functions_removed():
    """旧 service 包装一并删除，避免留下无入口的死代码。"""
    from app.services import import_export_service as ie

    for gone in ("dry_run", "confirm", "assert_confirm_allowed", "_validate_rows"):
        assert not hasattr(ie, gone), f"{gone} 应随旧入口一起删除"
    # 迁移模块仍在用的解析器与导出能力必须保留
    assert hasattr(ie, "parse_upload_rows") and hasattr(ie, "create_students_export")


def test_student_import_feature_gate_moved_to_new_entry():
    """studentImport 租户特性闸门不能随旧入口一起消失。"""
    import inspect

    from app.api.v1 import system as system_api

    src = inspect.getsource(system_api.student_import_validate_file)
    assert "enforce_student_import" in src, "学生导入入口缺少租户特性闸门"


# ── 2. 模板拆分 ────────────────────────────────────────────────────────────

def test_student_template_has_no_teacher_fields():
    from app.services.identity_import_file_service import STUDENT_HEADERS

    joined = "".join(STUDENT_HEADERS)
    for banned in ("角色", "部门", "岗位", "数据范围"):
        assert banned not in joined, f"学生模板不应出现教师字段：{banned}"
    for need in ("学号", "姓名", "班级名称"):
        assert need in STUDENT_HEADERS


def test_teacher_template_has_no_student_org_fields():
    from app.services.identity_import_file_service import TEACHER_HEADERS

    joined = "".join(TEACHER_HEADERS)
    for banned in ("学院", "专业", "班级", "年级", "学籍"):
        assert banned not in joined, f"教师模板不应出现学生字段：{banned}"
    for need in ("工号", "姓名", "预设角色编码", "数据范围类型"):
        assert need in TEACHER_HEADERS


def test_split_templates_build_and_parse():
    import io as _io

    from openpyxl import Workbook

    from app.services.identity_import_file_service import (STUDENT_HEADERS, build_student_template,
                                                           build_teacher_template,
                                                           parse_student_xlsx, parse_teacher_xlsx)
    assert build_student_template()[:2] == b"PK" and build_teacher_template()[:2] == b"PK"

    wb = Workbook(); ws = wb.active; ws.title = "导入模板"
    ws.append(list(STUDENT_HEADERS))
    ws.append(["20260001", "张三", "信息工程学院", "软件技术", "软件2601", "2026", "男", ""])
    buf = _io.BytesIO(); wb.save(buf)
    out = parse_student_xlsx(buf.getvalue(), "s.xlsx")
    assert out["importKind"] == "STUDENT" and out["teachers"] == []
    assert out["students"][0]["studentNo"] == "20260001"
    assert not out["errors"]

    # 把学生表传到教师入口必须被表头校验拦下，而不是静默解析出空数据
    with pytest.raises(AppException):
        parse_teacher_xlsx(buf.getvalue(), "s.xlsx")


# ── 3. 组织完整性（正式建档不可妥协的底线）──────────────────────────────────

def _seed_org(db, *, disband=False):
    from app.models.org import College, Major, SchoolClass

    col = College(tenant_id=TID, college_name="信息工程学院", status="ACTIVE")
    col2 = College(tenant_id=TID, college_name="机电工程学院", status="ACTIVE")
    db.add_all([col, col2]); db.flush()
    maj = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    maj2 = Major(tenant_id=TID, college_id=col2.id, major_name="数控技术", status="ACTIVE")
    db.add_all([maj, maj2]); db.flush()
    cls = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="软件2601",
                      grade="2026", status="ACTIVE",
                      class_status="DISBANDED" if disband else "NORMAL")
    db.add(cls); db.flush()
    return {"col": col, "col2": col2, "maj": maj, "maj2": maj2, "cls": cls}


def test_formal_create_requires_complete_org(db_mode):
    """只有姓名学号、没有组织 → 正式入口必须拒绝，不允许落一个「半截组织」的主档。"""
    from app.core.student_master_contract import StudentCreateCommand
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        cmd = StudentCreateCommand(student_no="ORG0001", real_name="无组织",
                                   require_complete_org=True)
        with pytest.raises(AppException) as ei:
            master.create_student_in_session(db, tenant_id=TID, cmd=cmd, actor=None)
        msg = str(getattr(ei.value, "message", "") or ei.value)
        assert "完整" in msg and ("学院" in msg or "班级" in msg)
    finally:
        db.rollback(); db.close()


def test_class_only_backfills_full_org(db_mode):
    """只填能唯一定位的班级 → 服务端补全专业与学院后放行。"""
    from app.core.student_master_contract import StudentCreateCommand
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        res = master.create_student_in_session(
            db, tenant_id=TID, actor=None,
            cmd=StudentCreateCommand(student_no="ORG0002", real_name="只填班级",
                                     class_id=org["cls"].id, require_complete_org=True))
        db.flush()
        s = db.get(StudentProfile, res.student_id)
        assert s.class_id == org["cls"].id
        assert s.major_id == org["maj"].id and s.college_id == org["col"].id
    finally:
        db.rollback(); db.close()


def test_disbanded_class_rejected(db_mode):
    from app.core.student_master_contract import StudentCreateCommand
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        org = _seed_org(db, disband=True)
        with pytest.raises(AppException) as ei:
            master.create_student_in_session(
                db, tenant_id=TID, actor=None,
                cmd=StudentCreateCommand(student_no="ORG0003", real_name="解散班",
                                         class_id=org["cls"].id, require_complete_org=True))
        assert "解散" in str(getattr(ei.value, "message", "") or ei.value)
    finally:
        db.rollback(); db.close()


# ── 4. 查重 / 复用 / 冲突（两个入口共用同一 resolver）──────────────────────

def _cmd(**kw):
    from app.core.student_master_contract import StudentCreateCommand
    base = dict(student_no="RU0001", real_name="李四", require_complete_org=True,
                allow_restore=False)
    base.update(kw)
    return StudentCreateCommand(**base)


def test_resolver_creates_then_skips_then_fills(db_mode):
    """同一批数据二次导入应判为跳过；缺字段补齐判为复用。"""
    from app.core.student_master_contract import ACTION_CREATE, ACTION_REUSE, ACTION_SKIP
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        c1 = _cmd(class_id=org["cls"].id)
        r1 = master.resolve_student_for_import(db, tenant_id=TID, cmd=c1)
        assert r1.action == ACTION_CREATE and r1.student_id is None  # 尚未建档
        out1 = master.apply_resolution_in_session(db, tenant_id=TID, cmd=c1, resolution=r1, actor=None)
        db.flush()

        # 完全相同的一行 → 跳过，不再建第二份
        r2 = master.resolve_student_for_import(db, tenant_id=TID, cmd=_cmd(class_id=org["cls"].id))
        assert r2.action == ACTION_SKIP and r2.student_id == out1.student_id

        # 补性别 → 复用并补齐空字段
        r3 = master.resolve_student_for_import(
            db, tenant_id=TID, cmd=_cmd(class_id=org["cls"].id, gender="男"))
        assert r3.action == ACTION_REUSE and "gender" in r3.fillable
    finally:
        db.rollback(); db.close()


def test_resolver_blocks_org_conflict(db_mode):
    """已有完整组织，导入换了班级 → 阻断并指向学籍异动，绝不覆盖。"""
    from app.core.student_master_contract import CONFLICT_ORG
    from app.db.session import get_sessionmaker
    from app.models.org import SchoolClass
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        other = SchoolClass(tenant_id=TID, major_id=org["maj2"].id, class_name="数控2601",
                            grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(other); db.flush()
        c1 = _cmd(class_id=org["cls"].id)
        r1 = master.resolve_student_for_import(db, tenant_id=TID, cmd=c1)
        master.apply_resolution_in_session(db, tenant_id=TID, cmd=c1, resolution=r1, actor=None)
        db.flush()

        r2 = master.resolve_student_for_import(db, tenant_id=TID, cmd=_cmd(class_id=other.id))
        assert r2.blocked and r2.reason_code == CONFLICT_ORG
        assert "学籍异动" in r2.message
    finally:
        db.rollback(); db.close()


def test_resolver_blocks_identity_and_voided(db_mode):
    """同学号不同姓名 → 身份冲突；学号属于作废档案 → 不得靠导入复活。"""
    from app.core.student_master_contract import CONFLICT_IDENTITY, CONFLICT_VOIDED
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        c1 = _cmd(class_id=org["cls"].id)
        r1 = master.resolve_student_for_import(db, tenant_id=TID, cmd=c1)
        out1 = master.apply_resolution_in_session(db, tenant_id=TID, cmd=c1, resolution=r1, actor=None)
        db.flush()

        bad = master.resolve_student_for_import(
            db, tenant_id=TID, cmd=_cmd(class_id=org["cls"].id, real_name="完全不同的人"))
        assert bad.blocked and bad.reason_code == CONFLICT_IDENTITY

        db.get(StudentProfile, out1.student_id).is_deleted = True
        db.flush()
        voided = master.resolve_student_for_import(db, tenant_id=TID, cmd=_cmd(class_id=org["cls"].id))
        assert voided.blocked and voided.reason_code == CONFLICT_VOIDED
    finally:
        db.rollback(); db.close()


def test_resolver_blocks_duplicates_within_file(db_mode):
    from app.core.student_master_contract import CONFLICT_DUP_IN_FILE
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        org = _seed_org(db)
        seen = {"RU0001"}
        dup = master.resolve_student_for_import(
            db, tenant_id=TID, cmd=_cmd(class_id=org["cls"].id), seen_nos=seen)
        assert dup.blocked and dup.reason_code == CONFLICT_DUP_IN_FILE
    finally:
        db.rollback(); db.close()


# ── 5. 两条正式入口都经统一服务 ────────────────────────────────────────────

@pytest.mark.parametrize("module_path,func_name", [
    ("app.services.school_onboarding_service", "run_onboarding"),
    ("app.modules.academic_affairs.services.academic_affairs_service", "_persist_roster_rows"),
])
def test_both_formal_entries_use_shared_resolver(module_path, func_name):
    import importlib
    import inspect

    mod = importlib.import_module(module_path)
    src = inspect.getsource(getattr(mod, func_name))
    assert "resolve_student_for_import" in src, f"{func_name} 未使用统一查重规则"
    assert "require_complete_org=True" in src, f"{func_name} 未强制组织完整性"
    assert "allow_restore=False" in src, f"{func_name} 允许了导入复活作废档案"
