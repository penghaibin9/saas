from __future__ import annotations
TID = 1000000000000000001
BASE = "/api/v1/student-affairs"
def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login", json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}
def test_dorm_exception_batch_enriches_existing_risk_relation(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, CsDormException, User
    db = get_sessionmaker()(); sid = int(db_mode["student"])
    linked = CsDormException(tenant_id=TID, cs_student_id=sid, exc_type="NIGHT_ABSENCE", detail="夜间检查发现未按时归寝", status="PENDING_HANDLE")
    plain = CsDormException(tenant_id=TID, cs_student_id=sid, exc_type="HYGIENE", detail="卫生检查需要整改", status="PENDING_HANDLE")
    db.add_all([linked, plain]); db.flush()
    owner = db.query(User).filter(User.tenant_id == TID, User.login_name == "school_admin01", User.is_deleted.is_(False)).first()
    risk = AffairsRiskRecord(tenant_id=TID, student_id=sid, source="DORM", source_ref_id=linked.id, risk_level="HIGH", status="PROCESSING", owner_id=owner.id if owner else None, title="宿舍异常联动风险")
    db.add(risk); db.commit(); linked_id, plain_id, risk_id = linked.id, plain.id, risk.id; owner_name = owner.real_name if owner else ""; db.close()
    data = client.get(f"{BASE}/dorm/exceptions?studentId={sid}&page=1&pageSize=50", headers=_hdr(client, "school_admin01")).json()["data"]
    by_id = {int(row["exceptionId"]): row for row in data["items"]}; related = by_id[linked_id]["relatedRisk"]
    assert related["riskId"] == str(risk_id) and related["riskLevel"] == "HIGH" and related["status"] == "PROCESSING" and related["statusLabel"] == "处置中"
    if owner_name: assert related["ownerName"] == owner_name
    assert by_id[plain_id]["relatedRisk"] is None
def test_dorm_risk_enrichment_is_page_batched():
    import inspect
    from app.services import affairs_dorm_service
    src = inspect.getsource(affairs_dorm_service.list_exceptions)
    assert "AffairsRiskRecord.source_ref_id.in_(exception_ids" in src
    assert "AffairsRiskRecord.id.in_(linked_risk_ids" in src
    assert "User.id.in_(owner_ids)" in src and "risk_by_exception.get(int(x.id))" in src
    loop = src.split("for x in rows:", 1)[1]
    assert "db.get(AffairsRiskRecord" not in loop and "db.get(User" not in loop
