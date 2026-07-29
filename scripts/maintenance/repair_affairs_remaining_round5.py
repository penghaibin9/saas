from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"repair anchor missing: {path}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_test_support() -> None:
    path = "backend/affairs_contract_test_support.py"
    replace_once(
        path,
        '(re.compile(r"/student-affairs/talks/(\\d+)/(?:record|follow-up)$"), "TalkPlan"),',
        '(re.compile(r"/student-affairs/talks/(\\d+)/(?:record|follow-up)$"), "TalkRecord"),',
    )
    replace_once(
        path,
        '''def post_versioned(client, url: str, *, headers=None, json=None, **kwargs):
    """显式模拟真实页面：读取当前详情版本后提交写操作。"""
    return client.post(url, headers=headers, json=versioned_payload(url, json), **kwargs)
''',
        '''def post_versioned(client, url: str, *, headers=None, json=None, **kwargs):
    """显式模拟真实页面：读取当前详情版本后提交写操作。

    同时发送 JSON version 和 x-expected-version，覆盖无 Pydantic Body 的历史端点；
    生产接口仍必须显式校验版本，本助手不会重试或吞掉冲突。
    """
    payload = versioned_payload(url, json)
    request_headers = dict(headers or {})
    request_headers.setdefault("x-expected-version", str(payload["version"]))
    return client.post(url, headers=request_headers, json=payload, **kwargs)


def expire_publicity(model_name: str, entity_id: int, *, days: int = 2) -> None:
    """显式把测试公示记录推进到到期状态，不允许生产创建 0 天公示。"""
    from app import models
    from app.db.session import get_sessionmaker

    model = getattr(models, model_name)
    db = get_sessionmaker()()
    try:
        row = db.get(model, int(entity_id))
        assert row is not None and not getattr(row, "is_deleted", False), (
            f"测试公示记录不存在：{model_name}#{entity_id}"
        )
        assert hasattr(row, "publicity_at"), f"模型没有 publicity_at：{model_name}"
        row.publicity_at = datetime.utcnow() - timedelta(days=max(1, int(days)))
        db.commit()
    finally:
        db.close()
''',
    )


def patch_formal_api_and_service() -> None:
    api = "backend/app/api/v1/student_affairs.py"
    replace_once(
        api,
        '''class EvalAppealReviewBody(BaseModel):
    result: str = Field(..., description="UPHELD/ADJUSTED")
    opinion: str = Field(..., min_length=5)
    scores: Optional[dict] = None
''',
        '''class EvalAppealReviewBody(BaseModel):
    result: str = Field(..., description="UPHELD/ADJUSTED")
    opinion: str = Field(..., min_length=5)
    scores: Optional[dict] = None
    version: int = Field(..., description="乐观锁版本（必填）")
''',
    )
    replace_once(
        api,
        '''class CheckinBody(BaseModel):
    studentId: str = Field(..., min_length=1)


class TransferSubmit(BaseModel):
''',
        '''class CheckinBody(BaseModel):
    studentId: str = Field(..., min_length=1)


class DormCheckoutBody(BaseModel):
    version: int = Field(..., description="当前床位乐观锁版本（必填）")


class TransferSubmit(BaseModel):
''',
    )
    replace_once(
        api,
        '''@router.post("/dorm/beds/{bedId}/checkout", summary="退宿（释放床位）")
def dorm_checkout(bedId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.dorm.allocation.manage"))):
    return success(dorm_svc.checkout(bedId, user), message="已退宿")
''',
        '''@router.post("/dorm/beds/{bedId}/checkout", summary="退宿（释放床位）")
def dorm_checkout(body: DormCheckoutBody, bedId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.dorm.allocation.manage"))):
    return success(dorm_svc.checkout(bedId, user, body.version), message="已退宿")
''',
    )

    service = "backend/app/services/affairs_dorm_service.py"
    replace_once(
        service,
        '''def checkout(bed_id, user) -> dict:
    with session() as db:
''',
        '''def checkout(bed_id, user, expected_version=None) -> dict:
    with session() as db:
''',
    )
    replace_once(
        service,
        '''        if bed.status != "OCCUPIED":
            raise AppException("DATA_CONFLICT", "该床位无人入住")
        if bed.cs_dorm_record_id:
''',
        '''        if bed.status != "OCCUPIED":
            raise AppException("DATA_CONFLICT", "该床位无人入住")
        atomic_claim_version(db, bed, expected_version)
        if bed.cs_dorm_record_id:
''',
    )


def patch_tests() -> None:
    credit = "backend/tests/test_affairs_credit_appeal.py"
    replace_once(
        credit,
        'json={"action": "APPROVE"}).json()',
        'json={"action": "APPROVE", "opinion": "经核实同意补记积分"}).json()',
    )

    dorm = "backend/tests/test_affairs_dorm.py"
    replace_once(
        dorm,
        '''    sf = StudentProfile(tenant_id=TID, student_no="F001", real_name="女生乙", class_id=a.id, gender="F",
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sm); db.add(sf); db.flush()
    ids = {"A": a.id, "sm": sm.id, "sf": sf.id}
    db.commit()
    db.close()
    return ids
''',
        '''    sf = StudentProfile(tenant_id=TID, student_no="F001", real_name="女生乙", class_id=a.id, gender="F",
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sm2 = StudentProfile(tenant_id=TID, student_no="M002", real_name="男生丙", class_id=a.id, gender="M",
                         current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add_all([sm, sf, sm2]); db.flush()
    ids = {"A": a.id, "sm": sm.id, "sf": sf.id, "sm2": sm2.id}
    db.commit()
    db.close()
    ensure_workflow_assignees([ids["sm"], ids["sf"], ids["sm2"]])
    return ids
''',
    )
    replace_once(
        dorm,
        '''    bid = client.post(f"{BASE}/dorm/buildings", headers=hdr, json={
        "buildingName": "紫荆1号楼", "buildingCode": "ZJ01", "genderLimit": gender}).json()["data"]["buildingId"]
''',
        '''    bid = client.post(f"{BASE}/dorm/buildings", headers=hdr, json={
        "buildingName": "紫荆1号楼", "buildingCode": "ZJ01", "genderLimit": gender,
        "managerTeacherKey": "dorm01"}).json()["data"]["buildingId"]
''',
    )
    replace_once(dorm, '"reason": "调宿"', '"reason": "学生申请调整宿舍床位"')
    replace_once(
        dorm,
        '''    r = client.post(f"{BASE}/dorm/transfers/{tid}/review", headers=hdr, json={
        "action": "APPROVE", "version": first["version"]}).json()  # 宿管→执行
''',
        '''    r = client.post(f"{BASE}/dorm/transfers/{tid}/review", headers=_hdr(client, "dorm01"), json={
        "action": "APPROVE", "version": first["version"]}).json()  # 宿管→执行
''',
    )
    replace_once(
        dorm,
        'json={"studentId": str(ids["sm"])}).json()\n    assert r["data"]["status"] == "OCCUPIED"',
        'json={"studentId": str(ids["sm2"])}).json()\n    assert r["data"]["status"] == "OCCUPIED"',
    )

    funding = "backend/tests/test_affairs_funding.py"
    replace_once(
        funding,
        'from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned',
        'from affairs_contract_test_support import expire_publicity, ensure_owner_scope, ensure_workflow_assignees, post_versioned',
    )
    replace_once(
        funding,
        '''    post_versioned(client, f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                json={"action": "APPROVE", "level": "DIFFICULT"})
    post_versioned(client, f"{BASE}/aid/applications/{aid_id}/publicity-confirm", headers=hdr)
''',
        '''    post_versioned(client, f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                json={"action": "APPROVE", "level": "DIFFICULT"})
    expire_publicity("AidApply", aid_id)
    post_versioned(client, f"{BASE}/aid/applications/{aid_id}/publicity-confirm", headers=hdr)
''',
    )
    replace_once(
        funding,
        '''    assert d["status"] == "PUBLICITY"
    c = post_versioned(client, f"{BASE}/funding/applications/{app_id}/publicity-confirm", headers=hdr).json()
''',
        '''    assert d["status"] == "PUBLICITY"
    expire_publicity("FundingApplication", app_id)
    c = post_versioned(client, f"{BASE}/funding/applications/{app_id}/publicity-confirm", headers=hdr).json()
''',
    )


def audit() -> None:
    helper = Path("backend/affairs_contract_test_support.py").read_text(encoding="utf-8")
    assert '"TalkRecord"' in helper
    assert 'x-expected-version' in helper
    api = Path("backend/app/api/v1/student_affairs.py").read_text(encoding="utf-8")
    assert "class DormCheckoutBody" in api
    assert "body.version" in api
    assert "class EvalAppealReviewBody" in api and "乐观锁版本（必填）" in api
    service = Path("backend/app/services/affairs_dorm_service.py").read_text(encoding="utf-8")
    assert "def checkout(bed_id, user, expected_version=None)" in service
    assert "atomic_claim_version(db, bed, expected_version)" in service


if __name__ == "__main__":
    patch_test_support()
    patch_formal_api_and_service()
    patch_tests()
    audit()
    print("student affairs remaining round5 repair passed", flush=True)
