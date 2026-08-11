"""教务第一组：成绩任务终身唯一 + 归档学期写保护 + 迁移安全失败。

覆盖：
1. ARCHIVED 仍阻止同教学任务再创建
2. 软删除仍阻止再创建
3. 唯一约束冲突转 409（不 500）
4. 归档学期省略 termId 不可绕过
5. 伪造活跃 termId 不可绕过
6. 活跃学期从教学任务批次解析可创建
7. 特殊补录学期/角色收紧
8/9. 迁移重复检测零写入；无重复时可建约束（辅助函数级）

当前 public grade service 先校验稳定课程版本；本文件所有真实 API 场景均建立真实 AaCourse，
使学期/唯一约束测试不会被无效 course_id 的旧 fixture 提前截断。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"
_MIG_0122 = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0122_aa_bugfix_credit_grade_uk.py"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _load_mig_0122():
    spec = importlib.util.spec_from_file_location("aa_mig_0122_uk", _MIG_0122)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _seed_terms_and_task(db_mode, *, archived=False, active=True):
    """创建归档/活跃学期 + 稳定课程 + 教学任务批次 + 教学任务。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm

    db = get_sessionmaker()()
    archived_term = AaTerm(
        tenant_id=TID, year_code="2024-2025", term_no=1,
        term_name="2024-2025第1学期", status="ARCHIVED", is_current=False,
    )
    active_term = AaTerm(
        tenant_id=TID, year_code="2026-2027", term_no=1,
        term_name="2026-2027第1学期", status="PUBLISHED", is_current=True,
    )
    other_tenant_term = AaTerm(
        tenant_id=TID + 9, year_code="2026-2027", term_no=2,
        term_name="他租户学期", status="PUBLISHED", is_current=False,
    )
    db.add_all([archived_term, active_term, other_tenant_term])
    db.flush()
    course = AaCourse(
        tenant_id=TID,
        course_code="GUK-MATH",
        course_name="高等数学",
        credit=4,
        status="ENABLED",
    )
    db.add(course); db.flush()

    term = archived_term if archived else active_term
    batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=term.id, batch_name="成绩唯一测试批次", status="APPROVED",
    )
    db.add(batch); db.flush()
    tt = AaTeachingTask(
        tenant_id=TID,
        batch_id=batch.id,
        course_id=course.id,
        course_code=course.course_code,
        course_name=course.course_name,
        teacher_key="academic01",
        teacher_name="教务教师",
        weekly_hours=4,
        start_week=1,
        end_week=18,
        class_id=None,
        status="READY",
    )
    db.add(tt)
    db.commit()
    out = {
        "archived_term_id": archived_term.id,
        "active_term_id": active_term.id,
        "other_tenant_term_id": other_tenant_term.id,
        "course_id": course.id,
        "teaching_task_id": tt.id,
        "batch_id": batch.id,
        "term_id": term.id,
        "term_code": f"{term.year_code}-{term.term_no}",
    }
    db.close()
    return out


def _count_grade_tasks_for_tt(teaching_task_id: int) -> int:
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask
    db = get_sessionmaker()()
    n = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == TID,
        AaGradeTask.teaching_task_id == int(teaching_task_id),
    ).count()
    db.close()
    return n


def test_1_archived_grade_task_blocks_recreate(client, db_mode):
    seed = _seed_terms_and_task(db_mode, archived=False)
    teacher = _hdr(client, "academic01")
    admin = _hdr(client, "school_admin01")
    r1 = client.post(f"{BASE}/grade-tasks", headers=teacher, json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    })
    assert r1.status_code == 200, r1.text
    tid = r1.json()["data"]["gradeTaskId"]

    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask
    db = get_sessionmaker()()
    t = db.get(AaGradeTask, int(tid))
    t.status = "PUBLISHED"
    db.commit(); db.close()

    arc = client.post(f"{BASE}/grade-tasks/{tid}/archive", headers=admin)
    assert arc.status_code == 200, arc.text
    assert arc.json()["data"]["status"] == "ARCHIVED"

    r2 = client.post(f"{BASE}/grade-tasks", headers=teacher, json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    })
    assert r2.status_code == 409, r2.text
    assert _count_grade_tasks_for_tt(seed["teaching_task_id"]) == 1


def test_2_soft_deleted_grade_task_blocks_recreate(client, db_mode):
    seed = _seed_terms_and_task(db_mode, archived=False)
    teacher = _hdr(client, "academic01")
    r1 = client.post(f"{BASE}/grade-tasks", headers=teacher, json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    })
    assert r1.status_code == 200, r1.text
    tid = int(r1.json()["data"]["gradeTaskId"])

    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask
    db = get_sessionmaker()()
    t = db.get(AaGradeTask, tid)
    t.is_deleted = True
    db.commit(); db.close()

    r2 = client.post(f"{BASE}/grade-tasks", headers=teacher, json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    })
    assert r2.status_code == 409, r2.text
    assert "历史" in r2.text or "已删除" in r2.text or "数据修复" in r2.text
    assert _count_grade_tasks_for_tt(seed["teaching_task_id"]) == 1


def test_3_integrity_error_on_uk_becomes_409(client, db_mode):
    """真实 API 验证预检；core 单元分支验证并发窗口 UK 冲突也转 409。"""
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_grade_core_service as core

    seed = _seed_terms_and_task(db_mode, archived=False)
    body = SimpleNamespace(
        teachingTaskId=str(seed["teaching_task_id"]),
        termId=None, termCode=None, courseName=None, classId=None, credit=None,
        usualRatio=30, midtermRatio=0, finalRatio=70, passLine=60,
        adminSupplementReason=None,
    )
    user = {"userId": "u_academic01", "loginName": "academic01", "currentRoleCode": "ACADEMIC_TEACHER",
            "realName": "教师"}

    assert client.post(f"{BASE}/grade-tasks", headers=_hdr(client, "academic01"), json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    }).status_code == 200
    r2 = client.post(f"{BASE}/grade-tasks", headers=_hdr(client, "academic01"), json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    })
    assert r2.status_code == 409, r2.text
    assert _count_grade_tasks_for_tt(seed["teaching_task_id"]) == 1

    fake = IntegrityError("stmt", {}, Exception("Duplicate entry for key 'uk_aa_grade_task_tt'"))
    assert core._is_grade_task_tt_uk_violation(fake) is True
    other = IntegrityError("stmt", {}, Exception("Duplicate entry for key 'uk_other'"))
    assert core._is_grade_task_tt_uk_violation(other) is False

    with patch.object(core, "_find_existing_grade_task_by_teaching_task", side_effect=[None, MagicMock(
            id=99, status="NOT_STARTED", is_deleted=False)]):
        mock_db = MagicMock()
        mock_tt = MagicMock()
        mock_tt.is_deleted = False
        mock_tt.tenant_id = TID
        mock_tt.teacher_key = "academic01"
        mock_tt.class_id = None
        mock_tt.course_name = "高等数学"
        mock_tt.batch_id = seed["batch_id"]
        mock_tt.credit = None
        mock_db.get.side_effect = lambda model, pk: mock_tt
        mock_db.flush.side_effect = IntegrityError(
            "INSERT", {}, Exception("Duplicate entry 'x' for key 'uk_aa_grade_task_tt'")
        )
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_db
        mock_cm.__exit__.return_value = None
        with patch.object(core, "session", return_value=mock_cm):
            with patch.object(core, "_resolve_grade_task_term", return_value=(seed["term_id"], "2026-2027-1")):
                with patch.object(core, "_tid", return_value=TID):
                    with patch.object(core, "_user_keys", return_value={"academic01"}):
                        with pytest.raises(AppException) as ei2:
                            core.create_grade_task(body, user)
                        assert ei2.value.http_status == 409
                        assert ei2.value.code == "DATA_CONFLICT"


def test_4_archived_term_without_term_id_rejected(client, db_mode):
    seed = _seed_terms_and_task(db_mode, archived=True)
    teacher = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks", headers=teacher, json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    })
    assert r.status_code == 409, r.text
    assert _count_grade_tasks_for_tt(seed["teaching_task_id"]) == 0


def test_5_forged_active_term_id_rejected(client, db_mode):
    seed = _seed_terms_and_task(db_mode, archived=True)
    teacher = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks", headers=teacher, json={
        "teachingTaskId": str(seed["teaching_task_id"]),
        "termId": str(seed["active_term_id"]),
        "usualRatio": 30, "finalRatio": 70,
    })
    assert r.status_code == 409, r.text
    assert "不一致" in r.text or "归档" in r.text or "TERM_ARCHIVED" in r.text or "伪造" in r.text
    assert _count_grade_tasks_for_tt(seed["teaching_task_id"]) == 0


def test_6_active_term_resolved_from_batch(client, db_mode):
    seed = _seed_terms_and_task(db_mode, archived=False)
    teacher = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks", headers=teacher, json={
        "teachingTaskId": str(seed["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70,
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("termId") == str(seed["term_id"])
    assert data.get("termCode") == seed["term_code"]
    # V2 正式课程身份合同统一使用数值主键；term/teachingTask 等兼容字段仍保持字符串。
    assert data.get("courseId") == int(seed["course_id"])


def test_7_admin_supplement_term_and_role_rules(client, db_mode):
    seed = _seed_terms_and_task(db_mode, archived=False)
    admin = _hdr(client, "school_admin01")
    common = {
        "courseId": str(seed["course_id"]),
        "usualRatio": 30,
        "finalRatio": 70,
        "adminSupplementReason": "管理员特殊补录原因充分",
    }

    r0 = client.post(f"{BASE}/grade-tasks", headers=admin, json=dict(common))
    assert r0.status_code in (400, 422), r0.text

    r1 = client.post(f"{BASE}/grade-tasks", headers=admin, json={**common, "termCode": "2026-2027-1"})
    assert r1.status_code in (400, 422), r1.text

    r2 = client.post(f"{BASE}/grade-tasks", headers=admin,
                     json={**common, "termId": str(seed["archived_term_id"])})
    assert r2.status_code == 409, r2.text

    r3 = client.post(f"{BASE}/grade-tasks", headers=admin,
                     json={**common, "termId": str(seed["other_tenant_term_id"])})
    assert r3.status_code in (403, 404), r3.text

    r4 = client.post(f"{BASE}/grade-tasks", headers=admin,
                     json={**common, "termId": str(seed["active_term_id"])})
    assert r4.status_code == 200, r4.text
    assert r4.json()["data"]["termId"] == str(seed["active_term_id"])
    assert r4.json()["data"]["termCode"] == "2026-2027-1"
    assert r4.json()["data"]["courseId"] == int(seed["course_id"])

    from app.core.security import create_access_token
    college_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-college-g1", "realName": "学院教务", "userType": "STAFF",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx_college_g1",
        "currentRoleCode": "COLLEGE_ADMIN", "clientType": "PC"})}
    r5 = client.post(f"{BASE}/grade-tasks", headers=college_hdr,
                     json={**common, "termId": str(seed["active_term_id"])})
    assert r5.status_code in (400, 403, 422), r5.text


def test_8_migration_duplicate_check_zero_write(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask
    from sqlalchemy import text

    mig = _load_mig_0122()
    db = get_sessionmaker()()
    try:
        db.execute(text("ALTER TABLE t_aa_grade_task DROP INDEX uk_aa_grade_task_tt"))
        db.commit()
    except Exception:
        db.rollback()

    a = AaGradeTask(
        tenant_id=TID, teaching_task_id=88001, course_name="重复A",
        usual_ratio=30, final_ratio=70, status="PUBLISHED",
    )
    b = AaGradeTask(
        tenant_id=TID, teaching_task_id=88001, course_name="重复B",
        usual_ratio=30, final_ratio=70, status="NOT_STARTED",
    )
    db.add_all([a, b]); db.commit()
    snap = [
        (a.id, a.teaching_task_id, a.status, bool(a.is_deleted)),
        (b.id, b.teaching_task_id, b.status, bool(b.is_deleted)),
    ]
    bind = db.connection()
    groups = mig.find_grade_task_teaching_task_duplicates(bind)
    assert any(g[1] == 88001 and g[2] >= 2 for g in groups)
    report = mig.format_grade_task_duplicate_report(bind, groups)
    assert ("88001" in report and "需要人工确认" in report) or "人工" in report

    with pytest.raises(RuntimeError) as ei:
        mig._abort_on_duplicates(bind)
    assert "88001" in str(ei.value)

    db.expire_all()
    a2 = db.get(AaGradeTask, snap[0][0])
    b2 = db.get(AaGradeTask, snap[1][0])
    assert (a2.teaching_task_id, a2.status, bool(a2.is_deleted)) == (snap[0][1], snap[0][2], snap[0][3])
    assert (b2.teaching_task_id, b2.status, bool(b2.is_deleted)) == (snap[1][1], snap[1][2], snap[1][3])
    db.close()


def test_9_migration_no_dup_allows_uk_helper(db_mode):
    mig = _load_mig_0122()
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask

    db = get_sessionmaker()()
    db.add(AaGradeTask(
        tenant_id=TID, teaching_task_id=99001, course_name="唯一课",
        usual_ratio=40, final_ratio=60, status="NOT_STARTED", credit=1.5,
    ))
    db.add(AaGradeTask(
        tenant_id=TID, teaching_task_id=99002, course_name="另一课",
        usual_ratio=40, final_ratio=60, status="NOT_STARTED", credit=2.5,
    ))
    db.commit()
    bind = db.connection()
    assert mig.find_grade_task_teaching_task_duplicates(bind) == []
    mig._abort_on_duplicates(bind)

    from sqlalchemy import select
    rows = db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == TID, AaGradeTask.teaching_task_id.in_([99001, 99002])
    )).all()
    credits = {float(r.credit) for r in rows if r.credit is not None}
    assert 1.5 in credits and 2.5 in credits
    db.close()