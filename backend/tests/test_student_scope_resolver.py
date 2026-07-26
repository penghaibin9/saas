"""按组织范围选学生（阶段 E 内核）。

验的是学校真会踩的坑：整院选人、跨范围去重、排除个别学生、
学院管理员越不出本院、毕业生不会被拉进新批次、空规则不等于全校。
"""
from __future__ import annotations

import pytest

TID = 1000000000000000008


@pytest.fixture()
def org(db_mode):
    """两个学院 × 各一个专业 × 各两个班，共 8 名在读学生 + 1 名毕业生 + 1 名作废。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.models.org import College, Major, SchoolClass

    db = get_sessionmaker()()
    try:
        made = {"colleges": {}, "majors": {}, "classes": {}, "students": {}}
        for ci, cname in enumerate(("信息工程学院", "机电工程学院"), start=1):
            c = College(tenant_id=TID, college_name=cname, code=f"C{ci}", status="ACTIVE")
            db.add(c)
            db.flush()
            made["colleges"][cname] = c.id
            m = Major(tenant_id=TID, college_id=c.id, major_name=f"{cname}专业",
                      code=f"M{ci}", status="ACTIVE")
            db.add(m)
            db.flush()
            made["majors"][cname] = m.id
            for ki in (1, 2):
                k = SchoolClass(tenant_id=TID, major_id=m.id, class_name=f"{cname}{ki}班",
                                class_code=f"K{ci}{ki}", grade="2024", status="ACTIVE")
                db.add(k)
                db.flush()
                made["classes"][f"{cname}{ki}班"] = k.id
                for si in (1, 2):
                    no = f"SR{ci}{ki}{si}"
                    s = StudentProfile(tenant_id=TID, student_no=no, real_name=f"学生{no}",
                                       college_id=c.id, major_id=m.id, class_id=k.id,
                                       grade="2024", current_stage="ENROLLED",
                                       student_status="NORMAL", status="ACTIVE")
                    db.add(s)
                    db.flush()
                    made["students"][no] = s.id
        # 干扰项：已毕业 + 已作废，都不该被批量选中
        c1 = made["colleges"]["信息工程学院"]
        k1 = made["classes"]["信息工程学院1班"]
        grad = StudentProfile(tenant_id=TID, student_no="SRGRAD", real_name="已毕业",
                              college_id=c1, class_id=k1, grade="2021",
                              current_stage="GRADUATED", student_status="NORMAL", status="ACTIVE")
        gone = StudentProfile(tenant_id=TID, student_no="SRVOID", real_name="已作废",
                              college_id=c1, class_id=k1, grade="2024",
                              current_stage="ENROLLED", student_status="NORMAL",
                              status="ACTIVE", is_deleted=True)
        db.add_all([grad, gone])
        db.commit()
        made["students"]["SRGRAD"] = grad.id
        made["students"]["SRVOID"] = gone.id
        yield made
    finally:
        db.close()


def _resolve(body, user=None):
    from app.db.session import get_sessionmaker
    from app.services import student_scope_resolver as r
    db = get_sessionmaker()()
    try:
        return r.resolve(db, TID, r.parse_rule(body), user=user, limit=None)
    finally:
        db.close()


def _nos(res):
    return sorted(s.student_no for s in res.students)


# ── 1. 基本选人 ────────────────────────────────────────────────────────────

def test_empty_rule_selects_nobody(org):
    """什么都没选 ≠ 全校。误点一下「预览」不能给出全校名单。"""
    res = _resolve({})
    assert res.matched_count == 0 and res.students == []


def test_select_whole_college(org):
    """整院选人：一个学院两个班 4 人，另一个学院不受影响。"""
    res = _resolve({"collegeIds": [org["colleges"]["信息工程学院"]]})
    assert _nos(res) == ["SR111", "SR112", "SR121", "SR122"]


def test_select_multiple_classes_deduplicates(org):
    """同时选整院和院内某个班，同一个学生只出现一次。"""
    res = _resolve({"collegeIds": [org["colleges"]["信息工程学院"]],
                    "classIds": [org["classes"]["信息工程学院1班"]]})
    nos = _nos(res)
    assert nos == ["SR111", "SR112", "SR121", "SR122"]
    assert len(nos) == len(set(nos)), "重复选择不得产生重复名单"


def test_select_single_students_across_colleges(org):
    """点名加人：可以跨学院单独加，用于补录个别学生。"""
    res = _resolve({"studentIds": [org["students"]["SR111"], org["students"]["SR211"]]})
    assert _nos(res) == ["SR111", "SR211"]


def test_select_by_grade(org):
    """按年级选：2024 级全部在读学生。"""
    res = _resolve({"grades": ["2024"]})
    assert len(res.students) == 8


# ── 2. 排除 ────────────────────────────────────────────────────────────────

def test_exclude_students(org):
    """整院选人后剔掉两个（如已休学、已另行安排）。"""
    res = _resolve({"collegeIds": [org["colleges"]["信息工程学院"]],
                    "excludeStudentIds": [org["students"]["SR111"], org["students"]["SR122"]]})
    assert _nos(res) == ["SR112", "SR121"]
    assert res.excluded_count == 2


def test_exclude_whole_class(org):
    """整院选人后整班剔除。"""
    res = _resolve({"collegeIds": [org["colleges"]["信息工程学院"]],
                    "excludeClassIds": [org["classes"]["信息工程学院2班"]]})
    assert _nos(res) == ["SR111", "SR112"]


def test_exclude_beats_include(org):
    """同一个学生既在包含项又在排除项时，排除优先——宁可漏也不错选。"""
    sid = org["students"]["SR111"]
    res = _resolve({"studentIds": [sid], "excludeStudentIds": [sid]})
    assert res.students == [] and res.excluded_count == 1


# ── 3. 只选在籍在读 ────────────────────────────────────────────────────────

def test_graduated_and_voided_never_selected(org):
    """已毕业、已作废的档案不会被拉进新批次。"""
    res = _resolve({"collegeIds": [org["colleges"]["信息工程学院"]]})
    assert "SRGRAD" not in _nos(res), "已毕业不该进批次"
    assert "SRVOID" not in _nos(res), "已作废档案不该进批次"


def test_stage_can_be_widened_explicitly(org):
    """确有需要时可显式放开阶段（如毕业生回访批次），但必须显式写出来。"""
    res = _resolve({"collegeIds": [org["colleges"]["信息工程学院"]],
                    "stages": ["GRADUATED"]})
    assert _nos(res) == ["SRGRAD"]


# ── 4. 数据范围 ────────────────────────────────────────────────────────────

def test_college_admin_cannot_reach_other_college(org, monkeypatch):
    """学院管理员把规则写成"全校"，也只能拿到自己范围内的学生，
    并如实报告被裁掉多少人（不静默吞）。"""
    from app.services import student_scope_resolver as r
    allowed = {org["classes"]["信息工程学院1班"], org["classes"]["信息工程学院2班"]}
    monkeypatch.setattr(r, "_scope_filter", lambda user: (allowed, None))

    res = _resolve({"grades": ["2024"]}, user={"userId": "db-9", "currentRoleCode": "COLLEGE_ADMIN"})
    assert _nos(res) == ["SR111", "SR112", "SR121", "SR122"]
    assert res.out_of_scope_count == 4, "另一个学院的 4 人应记为越范围"


def test_scope_fail_closed_returns_nothing(org, monkeypatch):
    """没配数据范围的角色拿到空集合，绝不回退成全校。"""
    from app.services import student_scope_resolver as r
    monkeypatch.setattr(r, "_scope_filter", lambda user: (set(), None))

    res = _resolve({"grades": ["2024"]}, user={"userId": "db-9", "currentRoleCode": "COUNSELOR"})
    assert res.students == [] and res.matched_count == 0
    assert res.out_of_scope_count == 8


def test_internal_call_without_user_is_not_narrowed(org):
    """脚本/定时任务不带登录人时不做人身份收敛（否则回填任务永远选不到人）。"""
    res = _resolve({"grades": ["2024"]}, user=None)
    assert len(res.students) == 8 and res.out_of_scope_count == 0


# ── 5. 规则解析与预览 ──────────────────────────────────────────────────────

def test_illegal_id_is_rejected_not_ignored(db_mode):
    """规则里混进非法 id 直接报错。静默忽略会变成"我明明选了却没选上"的玄学。"""
    from app.core.exceptions import AppException
    from app.services import student_scope_resolver as r
    with pytest.raises(AppException) as ei:
        r.parse_rule({"classIds": ["abc"]})
    assert ei.value.code == "VALIDATION_ERROR"


def test_rule_roundtrip_is_stable(db_mode):
    """规则落库再读回来必须等价——批次冻结要靠它复算名单。"""
    from app.services import student_scope_resolver as r
    body = {"collegeIds": [3, 1, 2], "excludeStudentIds": [9], "grades": ["2024"]}
    once = r.parse_rule(body).to_dict()
    twice = r.parse_rule(once).to_dict()
    assert once == twice
    assert once["collegeIds"] == [1, 2, 3], "落库表示要有序，便于比对规则是否变化"


def test_preview_rows_have_org_names_and_no_sensitive_fields(org):
    """预览行带学院/专业/班级名（否则页面只有一串 id），且不含手机号/身份证。"""
    from app.db.session import get_sessionmaker
    from app.services import student_scope_resolver as r

    db = get_sessionmaker()()
    try:
        out = r.resolve_preview(db, TID, {"classIds": [org["classes"]["信息工程学院1班"]]})
        assert out["matchedCount"] == 2
        row = out["rows"][0]
        assert row["collegeName"] == "信息工程学院"
        assert row["className"] == "信息工程学院1班"
        assert not any(k in row for k in ("phone", "idCard", "idCardEncrypted"))
    finally:
        db.close()


def test_tenant_isolation(org):
    """别的学校的学生不会被选进来。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_scope_resolver as r

    db = get_sessionmaker()()
    try:
        other = StudentProfile(tenant_id=TID + 1, student_no="SROTHER", real_name="外校生",
                               grade="2024", current_stage="ENROLLED",
                               student_status="NORMAL", status="ACTIVE")
        db.add(other)
        db.commit()
        res = r.resolve(db, TID, r.parse_rule({"grades": ["2024"]}), user=None, limit=None)
        assert "SROTHER" not in [s.student_no for s in res.students]
    finally:
        db.close()
