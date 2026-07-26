"""影子学生止血：旧域不再独立建学生 + 读取双读主档身份（阶段 D）。

要守住的业务事实：
- 在校服务/旧学业/就业三个域不能再凭姓名学号造一个"只在本域存在的学生"；
- 已绑定学籍的台账行，改了学籍就跟着变；
- 还没回填的历史行照常能看，但要明确标出"这条还没接上主档"，不能假装是主档数据。
"""
from __future__ import annotations

import pytest

TID = 1000000000000000004


@pytest.fixture()
def ctx():
    """服务层直调需要租户与操作人上下文。"""
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "db-1", "realName": "测试管理员", "currentRoleCode": "SCHOOL_ADMIN",
                      "dataScope": "TENANT_ALL"})
    yield
    set_current_user(None)
    set_tenant(None)


def _mk_profile(db, no="SD20260001", name="沈明", college=None, major=None, klass=None):
    from app.models import StudentProfile
    s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, current_stage="ENROLLED",
                       student_status="NORMAL", status="ACTIVE",
                       college_id=college, major_id=major, class_id=klass)
    db.add(s)
    db.flush()
    return s


def _mk_org(db):
    """建一条完整组织链，用于校验双读会把主档的组织名带出来。"""
    from app.models.org import College, Major, SchoolClass
    c = College(tenant_id=TID, college_name="智能工程学院", code="ZN", status="ACTIVE")
    db.add(c)
    db.flush()
    m = Major(tenant_id=TID, college_id=c.id, major_name="工业机器人", code="GYJQR",
              status="ACTIVE")
    db.add(m)
    db.flush()
    k = SchoolClass(tenant_id=TID, major_id=m.id, class_name="机器人2601",
                    class_code="JQR2601", grade="2026", status="ACTIVE")
    db.add(k)
    db.flush()
    return c, m, k


# ── 1. 冻结独立新增 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_path,label", [
    ("app.services.campus_service_service", "在校服务"),
    ("app.services.academic_service", "旧学业"),
    ("app.modules.employment.services.employment_service", "就业"),
])
def test_create_without_master_profile_is_rejected(db_mode, ctx, mod_path, label):
    """查无学籍时新增业务台账被拒，且给的是"去哪儿建档"而不是含糊报错。"""
    import importlib
    from app.core.exceptions import AppException

    svc = importlib.import_module(mod_path)
    with pytest.raises(AppException) as ei:
        svc.create_student({"name": "查无此人", "studentNo": "NOSUCH0001"})
    assert ei.value.code == "DEPRECATED_WRITE_PATH", f"{label} 应拒绝独立建学生"
    assert ei.value.http_status == 410
    assert "学籍" in ei.value.message and "建" in ei.value.message


@pytest.mark.parametrize("mod_path,model_name", [
    ("app.services.campus_service_service", "CsServiceStudent"),
    ("app.services.academic_service", "AcademicStudent"),
    ("app.modules.employment.services.employment_service", "EmpStudent"),
])
def test_create_binds_master_and_snapshots_identity(db_mode, ctx, mod_path, model_name):
    """有学籍时可建，且身份字段取主档、不采信调用方传的假姓名。"""
    import importlib
    from app.db.session import get_sessionmaker
    from app import models

    svc = importlib.import_module(mod_path)
    model = getattr(models, model_name)
    db = get_sessionmaker()()
    try:
        c, m, k = _mk_org(db)
        p = _mk_profile(db, no=f"SD{model_name[:3]}001", name="真实姓名",
                        college=c.id, major=m.id, klass=k.id)
        db.commit()
        pid = p.id
    finally:
        db.close()

    out = svc.create_student({"name": "调用方乱填的名字", "studentNo": f"SD{model_name[:3]}001",
                              "className": "乱填班级"})
    assert out["profileStudentId"] == str(pid)

    db = get_sessionmaker()()
    try:
        row = db.get(model, int(out["id"]))
        assert int(row.student_id) == pid, "新建业务行必须绑定主档"
        assert row.name == "真实姓名", "姓名必须来自主档，不能采信调用方传值"
        assert row.class_name == "机器人2601", "班级必须来自主档组织"
    finally:
        db.close()


def test_duplicate_create_for_same_student_rejected(db_mode, ctx):
    """同一学生在同一个域重复建台账要拦住（以前靠学号查重，绑定后按 student_id 查）。"""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        _mk_profile(db, no="SDDUP001", name="重复建档")
        db.commit()
    finally:
        db.close()

    svc.create_student({"studentNo": "SDDUP001"})
    with pytest.raises(AppException) as ei:
        svc.create_student({"studentNo": "SDDUP001"})
    assert ei.value.code == "DATA_CONFLICT"


def test_voided_profile_does_not_accept_new_business_record(db_mode, ctx):
    """学籍已作废的学生不能被业务域重新拉活——要恢复得走学籍的受控恢复（阶段 B）。"""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        p = _mk_profile(db, no="SDVOID01", name="已作废")
        p.is_deleted = True
        db.commit()
    finally:
        db.close()

    with pytest.raises(AppException) as ei:
        svc.create_student({"studentNo": "SDVOID01"})
    assert ei.value.code == "DEPRECATED_WRITE_PATH"


def test_duplicate_student_no_impossible_at_db_level(db_mode):
    """主档学号唯一由数据库约束兜底；解析器里的"命中多条"分支是防御性冗余。

    写这条是为了让口径显式：一旦有人放宽 uk_tenant_student_no，这个测试会立刻变红，
    提醒重新审视按学号匹配主档的所有地方（含回填脚本）。
    """
    from sqlalchemy.exc import IntegrityError
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        _mk_profile(db, no="SDUK0001", name="甲")
        db.commit()
        with pytest.raises(IntegrityError):
            _mk_profile(db, no="SDUK0001", name="乙")
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_cross_tenant_profile_id_rejected(db_mode, ctx):
    """传别的学校的 studentId 不能绑（多租户红线）。"""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        other = StudentProfile(tenant_id=TID + 1, student_no="OTHER001", real_name="外校生",
                               current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        db.add(other)
        db.commit()
        oid = other.id
    finally:
        db.close()

    with pytest.raises(AppException) as ei:
        svc.create_student({"studentId": str(oid)})
    assert ei.value.code == "VALIDATION_ERROR"


# ── 2. 身份字段只读主档 ────────────────────────────────────────────────────

def test_bound_row_identity_is_readonly_in_business_domain(db_mode, ctx):
    """已绑定的行不能在业务域改姓名/班级——否则又出现两个版本的同一个人。"""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        _mk_profile(db, no="SDRO001", name="只读校验")
        db.commit()
    finally:
        db.close()

    out = svc.create_student({"studentNo": "SDRO001"})
    with pytest.raises(AppException) as ei:
        svc.update_student(out["id"], {"className": "私自改的班"})
    assert ei.value.code == "DEPRECATED_WRITE_PATH"
    assert "更正" in ei.value.message

    # 业务字段照常可改
    assert svc.update_student(out["id"], {"careLevel": "KEY_CARE"})["id"] == out["id"]


def test_resubmitting_unchanged_identity_is_not_rejected(db_mode, ctx):
    """表单把只读的姓名一起提交回来不算"改身份"——页面显示的是主档姓名，
    台账存量若还没同步过，只跟存量比对会把正常保存误判成违规。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent, StudentProfile
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        p = _mk_profile(db, no="SDRS001", name="主档新名")
        row = CsServiceStudent(tenant_id=TID, name="台账旧名", student_no="SDRS001",
                               student_id=p.id, record_status="ACTIVE")
        db.add(row)
        db.commit()
        rid = row.id
        assert db.get(StudentProfile, p.id).real_name == "主档新名"
    finally:
        db.close()

    # 页面拿到的是双读后的主档姓名，原样提交必须放行
    assert svc.update_student(str(rid), {"name": "主档新名", "careLevel": "FOCUS"})["id"] == str(rid)
    # 台账里的历史快照原样回填同样放行
    assert svc.update_student(str(rid), {"name": "台账旧名"})["id"] == str(rid)


def test_unbound_legacy_row_still_editable(db_mode, ctx):
    """还没回填的历史行不受影响，仍可维护，避免止血把老数据锁死。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        row = CsServiceStudent(tenant_id=TID, name="历史行", student_no="SDLEG001",
                               class_name="老班级", record_status="ACTIVE")
        db.add(row)
        db.commit()
        rid = row.id
    finally:
        db.close()

    assert svc.update_student(str(rid), {"className": "新班级"})["id"] == str(rid)


# ── 3. 双读 ────────────────────────────────────────────────────────────────

def test_bound_row_shows_master_identity_after_correction(db_mode, ctx):
    """改了学籍姓名，旧域列表立刻显示新姓名（不必等任何同步任务）。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent, StudentProfile
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        p = _mk_profile(db, no="SDDR001", name="旧名字")
        row = CsServiceStudent(tenant_id=TID, name="旧名字", student_no="SDDR001",
                               student_id=p.id, record_status="ACTIVE")
        db.add(row)
        db.commit()
        # 学籍更名（此处直接改库，模拟学籍更正落库后的状态）
        db.get(StudentProfile, p.id).real_name = "改后名字"
        db.commit()
    finally:
        db.close()

    items, _ = svc.list_students(1, 20)
    hit = [x for x in items if x["studentNo"] == "SDDR001"]
    assert hit, "绑定行应出现在列表里"
    assert hit[0]["name"] == "改后名字", "双读应显示主档当前姓名"
    assert hit[0]["legacyFallback"] is False
    assert hit[0]["identitySource"] == "MASTER"


def test_unbound_row_marked_as_legacy_fallback(db_mode, ctx):
    """未绑定行照常展示旧快照，但必须自曝 legacyFallback，不许伪装成主档数据。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent
    from app.services import campus_service_service as svc

    db = get_sessionmaker()()
    try:
        db.add(CsServiceStudent(tenant_id=TID, name="孤儿行", student_no="SDDR002",
                                record_status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    items, _ = svc.list_students(1, 20)
    hit = [x for x in items if x["studentNo"] == "SDDR002"]
    assert hit and hit[0]["name"] == "孤儿行"
    assert hit[0]["legacyFallback"] is True
    assert hit[0]["identitySource"] == "LEGACY_SNAPSHOT"
    assert hit[0]["profileStudentId"] == ""


def test_projection_sync_covers_legacy_domains(db_mode, ctx):
    """学籍更正后投影同步要覆盖旧学业/就业/迎新，否则按新姓名搜不到人。"""
    from app.db.session import get_sessionmaker
    from app.models import AcademicStudent, EmpStudent
    from app.services.student_projection_sync import sync_student_projections_in_session

    db = get_sessionmaker()()
    try:
        p = _mk_profile(db, no="SDPS001", name="同步前")
        db.add(AcademicStudent(tenant_id=TID, name="同步前", student_no="SDPS001", student_id=p.id))
        db.add(EmpStudent(tenant_id=TID, name="同步前", student_no="SDPS001", student_id=p.id))
        db.commit()

        p.real_name = "同步后"
        p.student_no = "SDPS002"
        out = sync_student_projections_in_session(db, p)
        db.commit()

        assert out["academic"] == 1 and out["employment"] == 1
        from sqlalchemy import select
        a = db.scalars(select(AcademicStudent).where(AcademicStudent.student_id == p.id)).first()
        e = db.scalars(select(EmpStudent).where(EmpStudent.student_id == p.id)).first()
        assert a.name == "同步后" and a.student_no == "SDPS002"
        assert e.name == "同步后" and e.student_no == "SDPS002"
    finally:
        db.close()


# ── 4. 域导入 ──────────────────────────────────────────────────────────────

def test_domain_import_rejects_rows_without_master_profile(db_mode, ctx):
    """Excel 里没建过档的学号在预检阶段就报错，不能等确认导入时才造出影子学生。"""
    from app.services import domain_import_service as dis
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        _mk_profile(db, no="SDIMP001", name="已建档")
        db.commit()
    finally:
        db.close()

    res = dis.dry_run("academic", [
        {"name": "已建档", "studentNo": "SDIMP001"},
        {"name": "没建档", "studentNo": "SDIMP999"},
    ])
    assert res["okRows"] == 1 and res["errorRows"] == 1
    assert "学籍档案" in res["errors"][0]["message"]


def test_domain_import_orientation_still_allows_new_candidates(db_mode, ctx):
    """迎新是例外：录取候选人本来就还没有学籍，不能被这条规则误伤。"""
    from app.services import domain_import_service as dis

    res = dis.dry_run("orientation", [{"name": "新生甲", "admissionNo": "LQD0001"}])
    assert res["okRows"] == 1 and res["errorRows"] == 0
