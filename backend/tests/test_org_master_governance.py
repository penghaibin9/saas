"""组织主数据 HTTP/服务专项：跨租户父级、重复编码、乐观锁、统一写入。"""
from __future__ import annotations

import pytest

TID = 1000000000000000001
AA_ORGS = "/api/v1/academic-affairs/orgs"


def _hdr(client, login_name="school_admin01"):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_org_master_rejects_cross_tenant_parent(monkeypatch):
    from app.core.exceptions import AppException
    from app.services import org_master_service as oms

    class FakeScalars:
        def first(self):
            return None  # 当前租户查不到父级

    class FakeDB:
        def scalars(self, *_a, **_k):
            return FakeScalars()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

        def add(self, *_a):
            pass

        def refresh(self, *_a):
            pass

    monkeypatch.setattr(oms, "_tid", lambda: 1)
    monkeypatch.setattr(oms, "get_sessionmaker", lambda: (lambda: FakeDB()))
    with pytest.raises(AppException) as ei:
        oms.save_org_node(node_type="MAJOR", name="软工", code="SE01", parent_id=99)
    assert "当前租户" in str(ei.value.message) or "不存在" in str(ei.value.message)


def test_org_master_duplicate_code_rejected(monkeypatch):
    from app.core.exceptions import AppException
    from app.services import org_master_service as oms

    class Hit:
        id = 7

    class FakeScalars:
        def __init__(self, val):
            self.val = val

        def first(self):
            return self.val

    class FakeDB:
        def __init__(self):
            self.n = 0

        def scalars(self, *_a, **_k):
            self.n += 1
            return FakeScalars(Hit() if self.n >= 1 else None)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

        def add(self, *_a):
            pass

        def refresh(self, *_a):
            pass

    monkeypatch.setattr(oms, "_tid", lambda: 1)
    monkeypatch.setattr(oms, "get_sessionmaker", lambda: (lambda: FakeDB()))
    with pytest.raises(AppException) as ei:
        oms.save_org_node(node_type="COLLEGE", name="计科", code="C01")
    assert "编码已存在" in str(ei.value.message)


def test_org_master_rejects_disabled_parent(monkeypatch):
    from app.core.exceptions import AppException
    from app.services import org_master_service as oms

    class DisabledCollege:
        id = 3
        tenant_id = 1
        status = "DISABLED"
        is_deleted = False

    class FakeScalars:
        def __init__(self, val):
            self.val = val

        def first(self):
            return self.val

    class FakeDB:
        def __init__(self):
            self.n = 0

        def scalars(self, *_a, **_k):
            self.n += 1
            if self.n == 1:
                return FakeScalars(DisabledCollege())
            return FakeScalars(None)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

        def add(self, *_a):
            pass

        def refresh(self, *_a):
            pass

    monkeypatch.setattr(oms, "_tid", lambda: 1)
    monkeypatch.setattr(oms, "get_sessionmaker", lambda: (lambda: FakeDB()))
    with pytest.raises(AppException) as ei:
        oms.save_org_node(node_type="MAJOR", name="软工", code="SE02", parent_id=3)
    assert "停用" in str(ei.value.message)


def test_org_master_optimistic_lock_conflict(monkeypatch):
    from app.core.exceptions import AppException
    from app.services import org_master_service as oms

    class Row:
        id = 8
        tenant_id = 1
        college_name = "旧名"
        code = "C08"
        status = "ACTIVE"
        is_deleted = False
        version = 2

    class FakeScalars:
        def first(self):
            return Row()

    class FakeDB:
        def scalars(self, *_a, **_k):
            return FakeScalars()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

        def add(self, *_a):
            pass

        def refresh(self, *_a):
            pass

    monkeypatch.setattr(oms, "_tid", lambda: 1)
    monkeypatch.setattr(oms, "get_sessionmaker", lambda: (lambda: FakeDB()))
    with pytest.raises(AppException) as ei:
        oms.save_org_node(
            node_type="COLLEGE",
            name="新名",
            code="C08",
            node_id=8,
            expected_version=1,
        )
    assert ei.value.code == "DATA_CONFLICT" or "冲突" in str(ei.value.message) or "修改" in str(ei.value.message)


def test_academic_org_service_uses_org_master():
    import inspect
    from app.modules.academic_affairs.services import academic_affairs_org_service as svc

    src = (
        inspect.getsource(svc.create_college)
        + inspect.getsource(svc.update_college)
        + inspect.getsource(svc.create_major)
        + inspect.getsource(svc.update_major)
        + inspect.getsource(svc.create_class)
        + inspect.getsource(svc.update_class)
    )
    assert "org_master_service" in src
    assert "save_org_node" in src


def test_mysql_college_major_class_via_org_master(client, db_mode):
    """MySQL：学院/专业/班级写入口经统一服务成功，并覆盖重复编码。"""
    hdr = _hdr(client)
    col = client.post(
        f"{AA_ORGS}/colleges",
        headers=hdr,
        json={"collegeName": "治理学院", "code": "GOV_COL_A", "shortName": "治院", "sortOrder": 1},
    )
    assert col.status_code == 200, col.text
    col_id = col.json()["data"]["id"]

    maj = client.post(
        f"{AA_ORGS}/majors",
        headers=hdr,
        json={
            "collegeId": col_id,
            "majorName": "治理专业",
            "code": "GOV_MAJ_A",
            "educationYears": 3,
            "trainingLevel": "HIGHER",
            "enrollStatus": "ENROLLING",
        },
    )
    assert maj.status_code == 200, maj.text
    maj_id = maj.json()["data"]["id"]

    cls = client.post(
        f"{AA_ORGS}/classes",
        headers=hdr,
        json={
            "majorId": maj_id,
            "className": "治理2601",
            "classCode": "GOV_CLS_A",
            "grade": "2026",
            "capacity": 40,
            "classStatus": "NORMAL",
        },
    )
    assert cls.status_code == 200, cls.text

    # 重复学院编码
    dup = client.post(
        f"{AA_ORGS}/colleges",
        headers=hdr,
        json={"collegeName": "重复学院", "code": "GOV_COL_A"},
    )
    assert dup.status_code in (400, 422)
    assert "编码" in (dup.json().get("message") or dup.text)

    # 系统侧重复检测只读
    dups = client.get("/api/v1/system/org-duplicate-codes", headers=hdr)
    assert dups.status_code == 200


def test_mysql_disabled_parent_and_optimistic_lock(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College

    hdr = _hdr(client)
    col = client.post(
        f"{AA_ORGS}/colleges",
        headers=hdr,
        json={"collegeName": "停用父级学院", "code": "GOV_COL_DIS"},
    ).json()["data"]
    col_id = int(col["id"])

    db = get_sessionmaker()()
    row = db.get(College, col_id)
    assert row is not None
    row.status = "DISABLED"
    db.commit()
    db.close()

    bad_maj = client.post(
        f"{AA_ORGS}/majors",
        headers=hdr,
        json={"collegeId": str(col_id), "majorName": "应失败专业", "code": "GOV_MAJ_DIS"},
    )
    assert bad_maj.status_code in (400, 422)
    body = bad_maj.json()
    blob = str(body.get("message") or "") + str(body.get("details") or "") + bad_maj.text
    assert "停用" in blob

    # 再启用后测乐观锁：错误 expectedVersion
    db = get_sessionmaker()()
    row = db.get(College, col_id)
    row.status = "ACTIVE"
    db.commit()
    ver = int(row.version or 0)
    db.close()

    conflict = client.put(
        f"{AA_ORGS}/colleges/{col_id}",
        headers=hdr,
        json={
            "collegeName": "改名冲突",
            "code": "GOV_COL_DIS",
            "expectedVersion": ver - 1 if ver > 0 else -1,
        },
    )
    assert conflict.status_code in (400, 409, 422)
    msg = conflict.json().get("message") or conflict.text
    assert any(x in msg for x in ("冲突", "修改", "刷新", "version", "Version"))


def test_mysql_cross_tenant_parent_blocked(client, db_mode):
    """跨租户父级：在别租户插入学院后，本租户挂专业应失败。"""
    from app.db.session import get_sessionmaker
    from app.models import College

    hdr = _hdr(client)
    db = get_sessionmaker()()
    other = College(tenant_id=TID + 7, college_name="外租户学院", code="OTHER_COL", status="ACTIVE")
    db.add(other)
    db.commit()
    oid = other.id
    db.close()

    r = client.post(
        f"{AA_ORGS}/majors",
        headers=hdr,
        json={"collegeId": str(oid), "majorName": "跨租户专业", "code": "X_TENANT_MAJ"},
    )
    assert r.status_code in (400, 422, 404)
    body = r.json()
    msg = str(body.get("message") or "") + str(body.get("details") or "") + r.text
    assert any(x in msg for x in ("租户", "不存在", "学院"))
