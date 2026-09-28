"""实习批次按组织范围选人（阶段 E 接线）。

对照原计划的验收清单：整学院选人、多班级去重、排除学生、学院管理员只能选本院、
批次冻结后学生转班不改变已冻结名单、重复冻结不重复建实习记录、名单变化有审计。
"""
from __future__ import annotations

import pytest

TID = 1000000000000000001


@pytest.fixture()
def ctx():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "db-1", "realName": "实习管理员",
                      "currentRoleCode": "SCHOOL_ADMIN"})
    yield
    set_current_user(None)
    set_tenant(None)


@pytest.fixture()
def world(db_mode, ctx):
    """两学院各一专业各一班，每班 2 人；一个 DRAFT 批次。"""
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, StudentProfile
    from app.models.org import College, Major, SchoolClass

    db = get_sessionmaker()()
    try:
        made = {"college": {}, "class": {}, "student": {}}
        for i, cname in enumerate(("批次学院A", "批次学院B"), start=1):
            c = College(tenant_id=TID, college_name=cname, code=f"BP{i}", status="ACTIVE")
            db.add(c); db.flush()
            m = Major(tenant_id=TID, college_id=c.id, major_name=f"{cname}专业",
                      code=f"BPM{i}", status="ACTIVE")
            db.add(m); db.flush()
            k = SchoolClass(tenant_id=TID, major_id=m.id, class_name=f"{cname}班",
                            class_code=f"BPK{i}", grade="2024", status="ACTIVE")
            db.add(k); db.flush()
            made["college"][cname] = c.id
            made["class"][cname] = k.id
            for j in (1, 2):
                no = f"BP{i}{j}"
                s = StudentProfile(tenant_id=TID, student_no=no, real_name=f"实习生{no}",
                                   college_id=c.id, major_id=m.id, class_id=k.id, grade="2024",
                                   current_stage="ENROLLED", student_status="NORMAL",
                                   status="ACTIVE")
                db.add(s); db.flush()
                made["student"][no] = s.id
        b = InternshipBatch(tenant_id=TID, batch_name="2026 春季实习", batch_no="BP2026",
                            status="DRAFT")
        db.add(b); db.flush()
        made["batchId"] = b.id
        db.commit()
        yield made
    finally:
        db.close()


def _user():
    return {"userId": "db-1", "realName": "实习管理员", "currentRoleCode": "SCHOOL_ADMIN"}


# ── 1. 预览 ────────────────────────────────────────────────────────────────

def test_preview_whole_college(world):
    from app.modules.internship.services import internship_participant_service as svc
    out = svc.preview(world["batchId"], {"collegeIds": [world["college"]["批次学院A"]]}, _user())
    assert out["matchedCount"] == 2
    assert sorted(r["studentNo"] for r in out["rows"]) == ["BP11", "BP12"]
    assert all(r["alreadyIn"] is False for r in out["rows"])


def test_preview_dedupes_college_and_class(world):
    """同时选整院和院内班级，同一学生只出现一次。"""
    from app.modules.internship.services import internship_participant_service as svc
    out = svc.preview(world["batchId"], {
        "collegeIds": [world["college"]["批次学院A"]],
        "classIds": [world["class"]["批次学院A"]]}, _user())
    nos = [r["studentNo"] for r in out["rows"]]
    assert sorted(nos) == ["BP11", "BP12"] and len(nos) == len(set(nos))


def test_preview_exclude_student(world):
    from app.modules.internship.services import internship_participant_service as svc
    out = svc.preview(world["batchId"], {
        "collegeIds": [world["college"]["批次学院A"]],
        "excludeStudentIds": [world["student"]["BP11"]]}, _user())
    assert [r["studentNo"] for r in out["rows"]] == ["BP12"]
    assert out["excludedCount"] == 1


def test_preview_saves_rule_for_later_freeze(world):
    """预览会把规则存下来，冻结时可以不再重传。"""
    from app.modules.internship.services import internship_participant_service as svc
    svc.preview(world["batchId"], {"collegeIds": [world["college"]["批次学院A"]]}, _user())
    saved = svc.get_rule(world["batchId"])
    assert saved["rule"]["collegeIds"] == [int(world["college"]["批次学院A"])]
    assert saved["lastPreviewCount"] == 2 and saved["frozen"] is False


# ── 2. 冻结 ────────────────────────────────────────────────────────────────

def test_freeze_creates_records_and_starts_batch(world):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord
    from app.modules.internship.services import internship_participant_service as svc
    from sqlalchemy import select

    out = svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    assert out["total"] == 2 and out["createdRecords"] == 2
    assert out["batchStatus"] == "RUNNING"

    db = get_sessionmaker()()
    try:
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == TID,
            InternshipRecord.batch_id == world["batchId"])).all()
        assert len(recs) == 2
        b = db.get(InternshipBatch, world["batchId"])
        assert b.status == "RUNNING" and b.planned_count == 2
    finally:
        db.close()


def test_freeze_twice_is_rejected_and_records_not_duplicated(world):
    """重复冻结要挡住，且不会给学生建第二条实习记录。"""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord
    from app.modules.internship.services import internship_participant_service as svc
    from sqlalchemy import func, select

    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    with pytest.raises(AppException) as ei:
        svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    assert ei.value.code == "DATA_CONFLICT"

    db = get_sessionmaker()()
    try:
        n = db.scalar(select(func.count()).select_from(InternshipRecord).where(
            InternshipRecord.tenant_id == TID, InternshipRecord.batch_id == world["batchId"]))
        assert n == 2, "重复冻结不得产生重复实习记录"
    finally:
        db.close()


def test_freeze_reuses_existing_internship_record(world):
    """学生已有本批次实习记录（如此前单独建过）时复用，不再新建。"""
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord
    from app.modules.internship.services import internship_participant_service as svc

    db = get_sessionmaker()()
    try:
        db.add(InternshipRecord(tenant_id=TID, student_id=world["student"]["BP11"],
                                batch_id=world["batchId"], status="PREPARING",
                                eligibility_status="PENDING", destination_type="NONE"))
        db.commit()
    finally:
        db.close()

    out = svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    assert out["createdRecords"] == 1 and out["reusedRecords"] == 1


def test_empty_rule_cannot_freeze(world):
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_participant_service as svc
    with pytest.raises(AppException) as ei:
        svc.freeze(world["batchId"], {"rule": {}}, _user())
    assert ei.value.code == "VALIDATION_ERROR"


def test_freeze_writes_audit(world):
    from app.db.session import get_sessionmaker
    from app.models import InternshipAuditTrail
    from app.modules.internship.services import internship_participant_service as svc
    from sqlalchemy import select

    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TID,
            InternshipAuditTrail.target_type == "BATCH",
            InternshipAuditTrail.target_id == world["batchId"])).all()
        hit = [r for r in rows if r.action == "冻结参与人名单"]
        assert hit, "冻结必须留痕"
        detail = hit[0].detail_json.get("detail") or {}
        assert detail.get("total") == 2
        assert detail.get("rule", {}).get("collegeIds")
    finally:
        db.close()


# ── 3. 冻结后名单不随组织变动漂移 ──────────────────────────────────────────

def test_frozen_roster_survives_class_transfer(world):
    """冻结后学生转班：仍在名单里，显示的是主档新班级，同时标出与快照不一致。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.modules.internship.services import internship_participant_service as svc

    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())

    db = get_sessionmaker()()
    try:
        s = db.get(StudentProfile, world["student"]["BP11"])
        s.class_id = world["class"]["批次学院B"]      # 转到另一个学院的班
        db.commit()
    finally:
        db.close()

    items, total = svc.list_participants(world["batchId"], 1, 50)
    assert total == 2, "转班不得把人挤出已冻结名单"
    hit = [x for x in items if x["studentNo"] == "BP11"][0]
    assert hit["className"] == "批次学院B班", "展示以主档当前班级为准"
    assert hit["snapshotClassName"] == "批次学院A班"
    assert hit["classChanged"] is True, "与冻结快照不一致要标出来"


def test_frozen_roster_shows_master_name_after_rename(world):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.modules.internship.services import internship_participant_service as svc

    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    db = get_sessionmaker()()
    try:
        db.get(StudentProfile, world["student"]["BP11"]).real_name = "改名后"
        db.commit()
    finally:
        db.close()

    items, _ = svc.list_participants(world["batchId"], 1, 50)
    assert "改名后" in [x["name"] for x in items]


# ── 4. 人工增减 ────────────────────────────────────────────────────────────

def test_add_participant_manually(world):
    from app.modules.internship.services import internship_participant_service as svc
    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    out = svc.add_participants(world["batchId"], [world["student"]["BP21"]], _user(), "转专业补录")
    assert out["added"] == 1
    items, total = svc.list_participants(world["batchId"], 1, 50)
    assert total == 3
    assert [x["source"] for x in items if x["studentNo"] == "BP21"] == ["MANUAL"]


def test_add_existing_participant_is_idempotent(world):
    from app.modules.internship.services import internship_participant_service as svc
    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    out = svc.add_participants(world["batchId"], [world["student"]["BP11"]], _user(), "重复添加")
    assert out["added"] == 0
    _items, total = svc.list_participants(world["batchId"], 1, 50)
    assert total == 2


def test_remove_participant_keeps_history(world):
    from app.modules.internship.services import internship_participant_service as svc
    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    items, _ = svc.list_participants(world["batchId"], 1, 50)
    target = items[0]
    svc.remove_participant(world["batchId"], target["id"], "已休学", target["version"])

    active, total = svc.list_participants(world["batchId"], 1, 50)
    assert total == 1
    with_removed, total2 = svc.list_participants(world["batchId"], 1, 50, include_removed=True)
    assert total2 == 2
    removed = [x for x in with_removed if x["status"] == "REMOVED"][0]
    assert removed["removeReason"] == "已休学"


def test_remove_requires_reason_and_version(world):
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_participant_service as svc
    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    items, _ = svc.list_participants(world["batchId"], 1, 50)
    target = items[0]

    with pytest.raises(AppException):
        svc.remove_participant(world["batchId"], target["id"], "", target["version"])
    with pytest.raises(AppException) as ei:
        svc.remove_participant(world["batchId"], target["id"], "已休学", target["version"] + 99)
    assert ei.value.code == "APPROVAL_VERSION_CONFLICT"


def test_removed_student_can_be_added_back(world):
    """移出后又要加回来：复活原行，不撞唯一键。"""
    from app.modules.internship.services import internship_participant_service as svc
    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    items, _ = svc.list_participants(world["batchId"], 1, 50)
    target = items[0]
    svc.remove_participant(world["batchId"], target["id"], "误移出", target["version"])
    out = svc.add_participants(world["batchId"], [target["studentId"]], _user(), "加回")
    assert out["added"] == 1
    _a, total = svc.list_participants(world["batchId"], 1, 50)
    assert total == 2


# ── 5. 数据范围 ────────────────────────────────────────────────────────────

def test_college_admin_cannot_freeze_other_college(world, monkeypatch):
    """学院管理员即使把规则写成全校，也只会圈到本院学生。"""
    from app.services import student_scope_resolver as r
    from app.modules.internship.services import internship_participant_service as svc

    monkeypatch.setattr(r, "_scope_filter",
                        lambda user: ({int(world["class"]["批次学院A"])}, None))
    out = svc.freeze(world["batchId"], {"rule": {"grades": ["2024"]}},
                     {"userId": "db-9", "currentRoleCode": "COLLEGE_ADMIN"})
    assert out["total"] == 2
    items, _ = svc.list_participants(world["batchId"], 1, 50)
    assert sorted(x["studentNo"] for x in items) == ["BP11", "BP12"]


def test_manual_add_respects_scope(world, monkeypatch):
    """点名补录也不能越权把别院学生塞进来。"""
    from app.services import student_scope_resolver as r
    from app.modules.internship.services import internship_participant_service as svc

    svc.freeze(world["batchId"], {"rule": {"collegeIds": [world["college"]["批次学院A"]]}}, _user())
    monkeypatch.setattr(r, "_scope_filter",
                        lambda user: ({int(world["class"]["批次学院A"])}, None))
    out = svc.add_participants(world["batchId"], [world["student"]["BP21"]],
                               {"userId": "db-9", "currentRoleCode": "COLLEGE_ADMIN"}, "越权尝试")
    assert out["added"] == 0
    assert out["rejectedOutOfScope"] == [int(world["student"]["BP21"])]
