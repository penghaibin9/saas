"""D2-U 大数据量合同：候选列表真分页，preview 只定点查询选中 ID。"""
from __future__ import annotations

from uuid import uuid4

from app.db.session import get_sessionmaker

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_many(db_mode, count=220):
    del db_mode
    from app.models import Major, SchoolClass, StudentProfile

    marker = f"D2USCALE{uuid4().hex[:8]}"
    db = get_sessionmaker()()
    major = Major(
        tenant_id=TID,
        college_id=880001,
        major_name=f"规模专业-{marker}",
        code=f"SC-{uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db.add(major)
    db.flush()
    klass = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"规模班-{marker}",
        grade="2026",
        status="ACTIVE",
    )
    db.add(klass)
    db.flush()
    students = [
        StudentProfile(
            tenant_id=TID,
            student_no=f"{marker}-{i:04d}",
            real_name=f"规模学生{marker}-{i:04d}",
            college_id=major.college_id,
            major_id=major.id,
            class_id=klass.id,
            current_stage="ORIENTATION",
            student_status="PENDING_REGISTER",
            status="ACTIVE",
        )
        for i in range(count)
    ]
    db.add_all(students)
    db.flush()
    ids = [row.id for row in students]
    db.commit()
    db.close()
    return marker, ids


def _open_batch(client, headers):
    response = client.post(
        f"{BASE}/registration-batches",
        headers=headers,
        json={
            "batchName": f"D2U规模批次-{uuid4().hex[:8]}",
            "registerType": "ENROLL",
            "open": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["batchId"]


def test_d2u_large_candidate_list_pages_in_sql_and_preview_never_materializes_all_candidates(
    client, db_mode, monkeypatch
):
    """220 人仅是回归探针；核心合同是便利性路径不再调用 legacy 全量 materializer。"""
    from app.modules.academic_affairs.services import academic_affairs_service as canonical

    marker, ids = _seed_many(db_mode, 220)
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)

    def _forbid_full_materializer(*_args, **_kwargs):
        raise AssertionError("D2-U must not materialize all registration candidates in Python")

    monkeypatch.setattr(canonical, "_batch_pending_candidates", _forbid_full_materializer)

    page = client.get(
        f"{BASE}/registration-batches/{batch_id}/registration-candidates",
        headers=headers,
        params={"keyword": marker, "page": 3, "pageSize": 20},
    )
    assert page.status_code == 200, page.text
    data = page.json()["data"]
    assert data["total"] == 220
    assert data["page"] == 3
    assert data["pageSize"] == 20
    assert len(data["items"]) == 20
    assert all(marker in row["studentNo"] for row in data["items"])

    # preview 仍只查所选 2 人；即便 legacy 全量候选器被强制炸掉也应成功。
    preview = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register-preview",
        headers=headers,
        json={"studentIds": [ids[0], ids[-1]]},
    )
    assert preview.status_code == 200, preview.text
    pdata = preview.json()["data"]
    assert pdata["selected"] == 2
    assert pdata["ready"] == 2
    assert len(pdata["items"]) == 2
    assert pdata["previewToken"]
