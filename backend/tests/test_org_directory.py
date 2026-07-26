"""公共组织目录接口（选人场景共用的组织树 / 年级源）。

守两件事：
1. 学院管理员打开选人页看到的是本院，不是全校；没配范围的一律空树（不回退全校）。
2. 学生/家长拿不到组织结构——组织树本身就是一份"学校有哪些班"的清单。
"""
from __future__ import annotations

import pytest

TID = 1000000000000000001


@pytest.fixture()
def org(db_mode):
    """两个学院各一专业各一班，班里各 2 人；另加一个没挂专业的孤儿班。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.models.org import College, Major, SchoolClass

    db = get_sessionmaker()()
    try:
        made = {"college": {}, "major": {}, "class": {}}
        for i, cname in enumerate(("公共学院A", "公共学院B"), start=1):
            c = College(tenant_id=TID, college_name=cname, code=f"OD{i}", status="ACTIVE")
            db.add(c)
            db.flush()
            m = Major(tenant_id=TID, college_id=c.id, major_name=f"{cname}专业",
                      code=f"ODM{i}", status="ACTIVE")
            db.add(m)
            db.flush()
            k = SchoolClass(tenant_id=TID, major_id=m.id, class_name=f"{cname}班",
                            class_code=f"ODK{i}", grade=f"202{i}", status="ACTIVE")
            db.add(k)
            db.flush()
            made["college"][cname] = c.id
            made["major"][cname] = m.id
            made["class"][cname] = k.id
            for s in (1, 2):
                db.add(StudentProfile(
                    tenant_id=TID, student_no=f"OD{i}{s}", real_name=f"目录生{i}{s}",
                    college_id=c.id, major_id=m.id, class_id=k.id, grade=f"202{i}",
                    current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
        db.commit()
        yield made
    finally:
        db.close()


def _tree(client, headers):
    r = client.get("/api/v1/directory/org-tree", headers=headers).json()
    assert r["code"] == 0, r
    return r["data"]["tree"]


def _labels(tree):
    return sorted(n["label"] for n in tree)


# ── 1. 树形与内容 ──────────────────────────────────────────────────────────

def test_tree_is_three_levels_and_cascader_ready(client, auth_headers, org):
    """直接可喂 AppOrgCascader：每层都是 {value,label,children}。"""
    tree = _tree(client, auth_headers)
    assert "公共学院A" in _labels(tree)
    college = [n for n in tree if n["label"] == "公共学院A"][0]
    assert set(college) >= {"value", "label", "children"}
    major = college["children"][0]
    assert major["label"] == "公共学院A专业"
    klass = major["children"][0]
    assert klass["label"] == "公共学院A班"
    assert klass["studentCount"] == 2, "班级节点要带人数，选人时才知道会圈进多少人"
    assert klass["grade"] == "2021"


def test_tree_has_no_student_personal_data(client, auth_headers, org):
    """组织树只回组织信息，不得夹带学生个人信息。"""
    import json
    blob = json.dumps(_tree(client, auth_headers), ensure_ascii=False)
    for leaked in ("目录生", "OD11", "idCard", "phone"):
        assert leaked not in blob, f"组织树不应出现 {leaked}"


def test_empty_major_is_pruned(client, auth_headers, org):
    """没有可见班级的专业/学院不出现在树里，避免点开一片空。"""
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major

    db = get_sessionmaker()()
    try:
        c = College(tenant_id=TID, college_name="空壳学院", code="ODX", status="ACTIVE")
        db.add(c)
        db.flush()
        db.add(Major(tenant_id=TID, college_id=c.id, major_name="空壳专业",
                     code="ODMX", status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    assert "空壳学院" not in _labels(_tree(client, auth_headers))


def test_orphan_class_is_surfaced_not_hidden(client, auth_headers, org):
    """组织关系没挂全的班级要显式列出来，否则教学秘书只会看到"学生不见了"。"""
    from app.db.session import get_sessionmaker
    from app.models.org import SchoolClass

    db = get_sessionmaker()()
    try:
        db.add(SchoolClass(tenant_id=TID, major_id=0, class_name="孤儿班",
                           class_code="ODORP", grade="2022", status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    tree = _tree(client, auth_headers)
    orphan = [n for n in tree if n["value"] == "__ORPHAN__"]
    assert orphan, "未挂专业的班级应单列一档"
    assert orphan[0]["children"][0]["children"][0]["label"] == "孤儿班"


# ── 2. 数据范围 ────────────────────────────────────────────────────────────

def test_scope_limited_role_sees_only_own_classes(client, auth_headers, org, monkeypatch):
    """只授了 A 学院班级范围的角色，树里只有 A 学院。"""
    from app.api.v1 import org_directory as od
    monkeypatch.setattr(od, "_visible_class_ids",
                        lambda user: {int(org["class"]["公共学院A"])})

    tree = _tree(client, auth_headers)
    assert _labels(tree) == ["公共学院A"]


def test_no_scope_is_fail_closed(client, auth_headers, org, monkeypatch):
    """没配数据范围 → 空树 + scopeLimited 标记，绝不回退全校。"""
    from app.api.v1 import org_directory as od
    monkeypatch.setattr(od, "_visible_class_ids", lambda user: set())

    r = client.get("/api/v1/directory/org-tree", headers=auth_headers).json()
    assert r["code"] == 0
    assert r["data"]["tree"] == [] and r["data"]["scopeLimited"] is True


def test_student_and_parent_are_denied(client, auth_headers, org, monkeypatch):
    """学生/家长身份直接 403，不给整校组织清单。"""
    from app.api.v1 import org_directory as od
    from app.core import permissions as perm

    for utype in ("STUDENT", "PARENT"):
        monkeypatch.setattr(perm, "get_current_user",
                            lambda: {"userId": "u1", "userType": utype}, raising=False)
        # 依赖注入已在应用启动时绑定，这里直接测服务层守卫本身
        from app.core.exceptions import AppException
        with pytest.raises(AppException) as ei:
            od._reject_student_side({"userId": "u1", "userType": utype})
        assert ei.value.code == "NO_PERMISSION"


def test_tenant_isolation(client, auth_headers, org):
    """别的学校的学院不会出现在本校树里。"""
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass

    db = get_sessionmaker()()
    try:
        c = College(tenant_id=TID + 99, college_name="外校学院", code="ODF", status="ACTIVE")
        db.add(c)
        db.flush()
        m = Major(tenant_id=TID + 99, college_id=c.id, major_name="外校专业",
                  code="ODFM", status="ACTIVE")
        db.add(m)
        db.flush()
        db.add(SchoolClass(tenant_id=TID + 99, major_id=m.id, class_name="外校班",
                           class_code="ODFK", grade="2024", status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    assert "外校学院" not in _labels(_tree(client, auth_headers))


# ── 3. 教职工目录 ──────────────────────────────────────────────────────────

def test_teachers_exclude_students_and_hide_contacts(client, auth_headers, org):
    """教职工目录不含学生，且不回手机号/邮箱——选择器不需要这些。"""
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User

    db = get_sessionmaker()()
    try:
        db.add(User(tenant_id=TID, login_name="od_teacher01", real_name="目录教师甲",
                    password_hash=hash_password("Test@123456"), user_type="TEACHER",
                    status="ACTIVE"))
        db.add(User(tenant_id=TID, login_name="od_stu01", real_name="目录学生甲",
                    password_hash=hash_password("Test@123456"), user_type="STUDENT",
                    status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/directory/teachers", headers=auth_headers).json()
    assert r["code"] == 0
    labels = [x["label"] for x in r["data"]["items"]]
    assert "目录教师甲" in labels
    assert "目录学生甲" not in labels, "学生不属于教职工目录"
    for item in r["data"]["items"]:
        assert not any(k in item for k in ("phone", "email", "idCard"))


def test_teachers_keyword_filter(client, auth_headers, org):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User

    db = get_sessionmaker()()
    try:
        db.add(User(tenant_id=TID, login_name="od_kw_zhang", real_name="张搜索",
                    password_hash=hash_password("Test@123456"), user_type="TEACHER",
                    status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/directory/teachers?keyword=张搜索", headers=auth_headers).json()
    assert [x["label"] for x in r["data"]["items"]] == ["张搜索"]


def test_teachers_reject_student_side():
    from app.api.v1 import org_directory as od
    from app.core.exceptions import AppException

    with pytest.raises(AppException) as ei:
        od._reject_student_side({"userId": "s1", "userType": "STUDENT"})
    assert ei.value.code == "NO_PERMISSION"


# ── 4. 年级 ────────────────────────────────────────────────────────────────

def test_grades_are_distinct_with_counts(client, auth_headers, org):
    """年级来自主档去重，带人数，倒序（新年级在前）。"""
    r = client.get("/api/v1/directory/grades", headers=auth_headers).json()
    assert r["code"] == 0
    items = {x["value"]: x for x in r["data"]["items"]}
    assert "2021" in items and "2022" in items
    assert items["2021"]["studentCount"] == 2
    values = [x["value"] for x in r["data"]["items"]]
    assert values == sorted(values, reverse=True)


def test_grades_respect_scope(client, auth_headers, org, monkeypatch):
    """年级同样按数据范围裁剪，否则从年级下拉就能推出全校有哪些年级。"""
    from app.api.v1 import org_directory as od
    monkeypatch.setattr(od, "_visible_class_ids",
                        lambda user: {int(org["class"]["公共学院A"])})

    r = client.get("/api/v1/directory/grades", headers=auth_headers).json()
    assert [x["value"] for x in r["data"]["items"]] == ["2021"]
