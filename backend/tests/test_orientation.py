"""数字迎新域测试：台账 CRUD + 绿色通道/材料/宿舍/异常各闭环 + 审计 + 看板。"""
from __future__ import annotations

from datetime import datetime

MAIN_TID = 1000000000000000001


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (College, GreenChannelApplication, Major, OrientationBatch,
                            OrientationException, OrientationMaterial, OrientationStudent,
                            SchoolClass)
    from app.services.orientation_flow_service import (ensure_published_flow_version,
                                                        ensure_student_steps)
    db = get_sessionmaker()()
    try:
        college = College(tenant_id=MAIN_TID, college_name="迎新测试学院", code="ORI-TEST-COL", status="ACTIVE")
        db.add(college); db.flush()
        major = Major(tenant_id=MAIN_TID, college_id=college.id, major_name="迎新测试专业",
                      code="ORI-TEST-MAJ", status="ACTIVE")
        db.add(major); db.flush()
        school_class = SchoolClass(tenant_id=MAIN_TID, major_id=major.id,
                                   class_name="软件2601班", class_code="ORI-TEST-CLS",
                                   grade="2026", status="ACTIVE")
        flow_version = ensure_published_flow_version(db, MAIN_TID)
        batch = OrientationBatch(tenant_id=MAIN_TID, batch_name="测试迎新批次",
                                 batch_no="ORI-TEST-2026", year="2026", status="ACTIVE",
                                 planned_count=2, flow_version_id=flow_version.id)
        db.add_all([school_class, batch]); db.flush()
        s = OrientationStudent(tenant_id=MAIN_TID, batch_id=batch.id,
                               name="新生甲", admission_no="LQ2026999001",
                               college_id=college.id, college_name=college.college_name,
                               major_id=major.id, major_name=major.major_name,
                               class_id=school_class.id,
                               class_name="软件2601班", phone_encrypted="13800009999",
                               id_card_encrypted="330102200801019999", stage="ADMITTED",
                               report_status="PREPARED", payment_status="UNPAID",
                               material_status="UPLOADED", dorm_status="ASSIGNED", risk_level="HIGH",
                               building="梧桐苑1号楼", room="1-301-1", counselor="李辅导",
                               steps_json={"ACTIVATE": "DONE", "PAYMENT": "BLOCKED"},
                               blocked_step="PAYMENT", blocked_reason="未缴费", payable_amount=8600,
                               paid_amount=0, source_type="MANUAL", source_record_id="LQ2026999001")
        db.add(s)
        db.flush()
        ensure_student_steps(db, s, status_source="PROCESS_FACT")
        gc = GreenChannelApplication(tenant_id=MAIN_TID, ori_student_id=s.id, apply_type="生源地助学贷款",
                                     apply_amount=8600, submit_time=datetime.utcnow(), status="REVIEWING")
        mat = OrientationMaterial(tenant_id=MAIN_TID, ori_student_id=s.id, material_type="AID_PROOF",
                                  file_name="困难认定表.pdf", submit_time=datetime.utcnow(), status="UPLOADED")
        exc = OrientationException(tenant_id=MAIN_TID, ori_student_id=s.id, exception_type="PAYMENT",
                                   description="缴费异常", risk_level="MEDIUM", status="OPEN", handler="李辅导")
        db.add_all([gc, mat, exc])
        db.commit()
        return {"student": s.id, "gc": gc.id, "mat": mat.id, "exc": exc.id,
                "batch": batch.id, "class": school_class.id}
    finally:
        db.close()


def test_students_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/orientation/students", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["reportStatusLabel"] == "预报到完成"
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["greenChannels"]) == 1 and len(det["data"]["materials"]) == 1
    assert det["data"]["student"]["steps"]["PAYMENT"] == "BLOCKED"
    assert len(det["data"]["steps"]) == 7
    assert det["data"]["steps"][0] == {"key": "ACTIVATE", "label": "账号激活"}
    assert det["data"]["steps"][3]["key"] == "PAYMENT"


def test_create_and_void_student(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    c = client.post("/api/v1/orientation/students", headers=auth_headers,
                    json={"name": "新生乙", "admissionNo": "LQ2026999002",
                          "batchId": ids["batch"], "classId": ids["class"]}).json()
    assert c["code"] == 0
    sid = c["data"]["id"]
    from sqlalchemy import func, select
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudentStep
    db = get_sessionmaker()()
    try:
        canonical_count = db.scalar(select(func.count()).select_from(OrientationStudentStep).where(
            OrientationStudentStep.tenant_id == MAIN_TID,
            OrientationStudentStep.orientation_student_id == int(sid),
            OrientationStudentStep.is_deleted.is_(False),
        ))
        assert canonical_count == 7
    finally:
        db.close()
    dup = client.post("/api/v1/orientation/students", headers=auth_headers,
                      json={"name": "x", "admissionNo": "LQ2026999002",
                            "batchId": ids["batch"], "classId": ids["class"]}).json()
    assert dup["code"] == 409001
    bad = client.post(f"/api/v1/orientation/students/{sid}/void", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/orientation/students/{sid}/void", headers=auth_headers,
                     json={"reason": "录取信息重复，作废该记录"}).json()
    assert ok["code"] == 0


def test_green_channel_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/orientation/green-channels/{ids['gc']}/reject", headers=auth_headers,
                      json={"expectedVersion": 0, "reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/orientation/green-channels/{ids['gc']}/approve", headers=auth_headers,
                     json={"expectedVersion": 0, "remark": "材料齐全予以通过"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    # 通过后学生缴费状态转绿色通道，并解除 PAYMENT 卡点
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["paymentStatus"] == "GREEN_CHANNEL"
    assert det["data"]["student"]["blockedStep"] == ""
    assert det["data"]["student"]["steps"]["PAYMENT"] == "DONE"
    dup = client.post(f"/api/v1/orientation/green-channels/{ids['gc']}/approve", headers=auth_headers,
                      json={"expectedVersion": 0}).json()
    assert dup["code"] == 409001


def test_material_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/orientation/materials/{ids['mat']}/return", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/orientation/materials/{ids['mat']}/approve", headers=auth_headers,
                     json={}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"


def test_dorm_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    before = client.get("/api/v1/orientation/dorms", headers=auth_headers).json()["data"]["items"][0]
    ex = client.post(f"/api/v1/orientation/dorms/{ids['student']}/exception", headers=auth_headers,
                     json={"note": "床位与系统记录不一致"}).json()
    assert ex["code"] == 0
    exceptions = client.get("/api/v1/orientation/exceptions?exceptionType=DORM&status=OPEN", headers=auth_headers).json()
    assert exceptions["data"]["total"] == 1
    after = client.get("/api/v1/orientation/dorms", headers=auth_headers).json()["data"]["items"][0]
    # 登记待处理异常不能伪造或覆盖权威床位入住事实。
    for field in ("housingStatus", "dormStatus", "bedId"):
        assert after.get(field) == before.get(field)


def test_exception_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    fu = client.post(f"/api/v1/orientation/exceptions/{ids['exc']}/followup", headers=auth_headers,
                     json={"content": "已电话联系家长", "way": "PHONE"}).json()
    assert fu["code"] == 0
    esc = client.post(f"/api/v1/orientation/exceptions/{ids['exc']}/escalate", headers=auth_headers,
                      json={"reason": "多次联系无果，升级处理"}).json()
    assert esc["code"] == 0 and esc["data"]["status"] == "ESCALATED"
    det = client.get(f"/api/v1/orientation/exceptions/{ids['exc']}", headers=auth_headers).json()
    assert det["data"]["exception"]["riskLevel"] == "HIGH" and len(det["data"]["exception"]["followUps"]) == 1


def test_dashboard_and_audit(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    dash = client.get("/api/v1/orientation/dashboard", headers=auth_headers).json()
    assert dash["code"] == 0 and any(k["key"] == "total" for k in dash["data"]["kpis"])
    assert any(k["key"] == "prepared" for k in dash["data"]["kpis"])
    assert len(dash["data"]["stepFunnel"]) == 7
    # 触发一条审计后可查
    client.post(f"/api/v1/orientation/materials/{ids['mat']}/approve", headers=auth_headers, json={})
    audit = client.get("/api/v1/orientation/audit-logs?bizType=MATERIAL", headers=auth_headers).json()
    assert audit["code"] == 0 and audit["data"]["total"] >= 1


def test_update_student(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    denied = client.put(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers,
                        json={"reportStatus": "CHECKED_IN", "counselor": "王辅导"})
    assert denied.status_code == 400
    assert "正式办理流程" in denied.json()["message"]
    ok = client.put(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers,
                    json={"counselor": "王辅导"}).json()
    assert ok["code"] == 0
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["reportStatus"] == "PREPARED"
    assert det["data"]["student"]["counselor"] == "王辅导"


def test_progress_blocked_and_resolve(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    scoped = client.get(
        f"/api/v1/orientation/progress?batchId={ids['batch']}", headers=auth_headers,
    ).json()
    assert scoped["code"] == 0 and scoped["data"]["total"] == 1
    other = client.get(
        "/api/v1/orientation/progress?batchId=9007199254740991", headers=auth_headers,
    ).json()
    assert other["code"] == 0 and other["data"]["total"] == 0
    bad = client.put(f"/api/v1/orientation/progress/{ids['student']}/blocked", headers=auth_headers,
                     json={"blockedStep": "MATERIAL", "blockedReason": "短"}).json()
    assert bad["code"] == 422001
    ok = client.put(f"/api/v1/orientation/progress/{ids['student']}/blocked", headers=auth_headers,
                    json={"blockedStep": "MATERIAL", "blockedReason": "材料缺失需补交"}).json()
    assert ok["code"] == 0
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["blockedStep"] == "MATERIAL"
    assert det["data"]["student"]["steps"]["MATERIAL"] == "BLOCKED"
    resolved = client.post(f"/api/v1/orientation/progress/{ids['student']}/resolve", headers=auth_headers,
                           json={"note": "已人工处理"}).json()
    assert resolved["code"] == 0
    det2 = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det2["data"]["student"]["blockedStep"] == ""
    assert det2["data"]["student"]["steps"]["MATERIAL"] == "WAIVED"
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudentStep
    db = get_sessionmaker()()
    try:
        canonical = db.scalars(select(OrientationStudentStep).where(
            OrientationStudentStep.tenant_id == MAIN_TID,
            OrientationStudentStep.orientation_student_id == ids["student"],
            OrientationStudentStep.step_key == "MATERIAL",
        )).one()
        assert canonical.status == "WAIVED"
        assert canonical.status_source == "MANUAL_WAIVER"
        assert canonical.waived_by and canonical.waived_at
        assert canonical.waive_reason == "已人工处理"
        assert canonical.waive_evidence_ref.startswith("orientation-audit:")
    finally:
        db.close()


def test_canonical_student_step_overwrites_tampered_json_projection(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    first = client.get(
        f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers
    ).json()
    assert first["data"]["student"]["steps"]["PAYMENT"] == "BLOCKED"

    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent
    db = get_sessionmaker()()
    try:
        student = db.get(OrientationStudent, ids["student"])
        student.steps_json = {**(student.steps_json or {}), "PAYMENT": "DONE"}
        db.commit()
    finally:
        db.close()

    second = client.get(
        f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers
    ).json()
    assert second["data"]["student"]["steps"]["PAYMENT"] == "BLOCKED"


def test_update_dorm_rejects_legacy_state_write(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    before = client.get("/api/v1/orientation/dorms", headers=auth_headers).json()["data"]["items"][0]
    denied = client.put(f"/api/v1/orientation/dorms/{ids['student']}", headers=auth_headers,
                        json={"building": "梧桐苑 2 号楼", "room": "2-105-1", "dormStatus": "ASSIGNED"})
    assert denied.status_code == 400
    assert "房态图" in denied.json()["message"]
    after = client.get("/api/v1/orientation/dorms", headers=auth_headers).json()["data"]["items"][0]
    for field in ("building", "room", "bedId", "dormStatus", "housingStatus"):
        assert after.get(field) == before.get(field)


def test_requires_login(client):
    assert client.get("/api/v1/orientation/dashboard").json()["code"] == 401001


def test_batch_closed_loop(client, auth_headers, db_mode):
    # 新建（草稿）
    c = client.post("/api/v1/orientation/batches", headers=auth_headers,
                    json={"batchName": "2026 级新生迎新", "batchNo": "ORI-2026",
                          "year": "2026", "startDate": "2026-09-01", "reportEndDate": "2026-09-15",
                          "plannedCount": 3200, "remark": "秋季迎新"}).json()
    assert c["code"] == 0
    bid = c["data"]["id"]
    # 编号唯一
    dup = client.post("/api/v1/orientation/batches", headers=auth_headers,
                      json={"batchName": "重复", "batchNo": "ORI-2026"}).json()
    assert dup["code"] != 0
    # 列表 + 脱敏无关，状态为草稿
    lst = client.get("/api/v1/orientation/batches", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    row = lst["data"]["items"][0]
    assert row["statusLabel"] == "草稿" and row["plannedCount"] == 3200
    # 非法流转：草稿不能直接结束
    bad = client.post(f"/api/v1/orientation/batches/{bid}/close", headers=auth_headers).json()
    assert bad["code"] != 0
    # 启用 草稿→进行中
    act = client.post(f"/api/v1/orientation/batches/{bid}/activate", headers=auth_headers).json()
    assert act["code"] == 0 and act["data"]["status"] == "ACTIVE"
    # 重复启用被拒
    assert client.post(f"/api/v1/orientation/batches/{bid}/activate", headers=auth_headers).json()["code"] != 0
    # 编辑
    upd = client.put(f"/api/v1/orientation/batches/{bid}", headers=auth_headers,
                     json={"plannedCount": 3300}).json()
    assert upd["code"] == 0
    assert client.get(f"/api/v1/orientation/batches/{bid}", headers=auth_headers).json()["data"]["plannedCount"] == 3300
    # 结束 进行中→已结束
    cl = client.post(f"/api/v1/orientation/batches/{bid}/close", headers=auth_headers).json()
    assert cl["code"] == 0 and cl["data"]["status"] == "CLOSED"
    # 已结束不可编辑
    assert client.put(f"/api/v1/orientation/batches/{bid}", headers=auth_headers,
                      json={"remark": "x"}).json()["code"] != 0
    # 审计留痕（BATCH 类型）
    logs = client.get("/api/v1/orientation/audit-logs?bizType=BATCH", headers=auth_headers).json()
    assert logs["code"] == 0 and logs["data"]["total"] >= 3


def test_verify_closed_loop(client, auth_headers, db_mode):
    from sqlalchemy import func, select
    from app.db.session import get_sessionmaker
    from app.models import OrientationException

    ids = _seed(db_mode)
    sid = ids["student"]
    version = client.get(f"/api/v1/orientation/students/{sid}", headers=auth_headers).json()["data"]["student"]["version"]
    # 不通过但原因太短 → 拒绝
    bad = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                      json={"passed": False, "reason": "x", "expectedVersion": version}).json()
    assert bad["code"] != 0
    # 通过 → stage=PRE_STUDENT_VERIFIED，环节 INFO=DONE
    ok = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                     json={"passed": True, "expectedVersion": version}).json()
    assert ok["code"] == 0 and ok["data"]["stage"] == "PRE_STUDENT_VERIFIED"
    stale = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                        json={"passed": False, "reason": "旧页面不得覆盖最新核验结果", "expectedVersion": version}).json()
    assert stale["code"] != 0 and stale["bizCode"] == "DATA_CONFLICT"
    version = ok["data"]["version"]
    det = client.get(f"/api/v1/orientation/students/{sid}", headers=auth_headers).json()
    assert det["data"]["student"]["steps"]["INFO"] == "DONE"
    # 不通过（含原因） → 记录成功
    fail = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                       json={"passed": False, "reason": "身份证与录取信息不一致", "expectedVersion": version}).json()
    assert fail["code"] == 0 and fail["data"]["stage"] == "ADMITTED" and fail["data"]["passed"] is False
    version = fail["data"]["version"]
    returned = client.get(f"/api/v1/orientation/students/{sid}", headers=auth_headers).json()["data"]["student"]
    assert returned["steps"]["INFO"] == "BLOCKED"
    assert returned["blockedStep"] == "INFO"
    assert returned["blockedReason"] == "身份证与录取信息不一致"
    assert returned["exceptionNote"] == "身份证与录取信息不一致"
    db = get_sessionmaker()()
    try:
        identity_exception = db.scalars(select(OrientationException).where(
            OrientationException.tenant_id == MAIN_TID,
            OrientationException.ori_student_id == int(sid),
            OrientationException.exception_type == "IDENTITY",
            OrientationException.status == "OPEN",
        )).one()
        assert identity_exception.description == "身份证与录取信息不一致"
    finally:
        db.close()
    repeated = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                           json={"passed": False, "reason": "身份证信息仍需学生补正", "expectedVersion": version}).json()
    assert repeated["code"] == 0
    db = get_sessionmaker()()
    try:
        assert db.scalar(select(func.count()).select_from(OrientationException).where(
            OrientationException.tenant_id == MAIN_TID,
            OrientationException.ori_student_id == int(sid),
            OrientationException.exception_type == "IDENTITY",
            OrientationException.status == "OPEN",
        )) == 1
    finally:
        db.close()
    # 审计留痕（核验动作 ≥ 2 条）
    logs = client.get("/api/v1/orientation/audit-logs?keyword=核验", headers=auth_headers).json()
    assert logs["code"] == 0 and logs["data"]["total"] >= 2


def test_checkin_point_crud(client, auth_headers, db_mode):
    c = client.post("/api/v1/orientation/checkin-points", headers=auth_headers,
                    json={"name": "东门报到点", "location": "东大门", "capacity": 300, "inCharge": "王老师"}).json()
    assert c["code"] == 0
    pid = c["data"]["id"]
    lst = client.get("/api/v1/orientation/checkin-points", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1 and lst["data"]["items"][0]["statusLabel"] == "启用"
    t = client.post(f"/api/v1/orientation/checkin-points/{pid}/toggle", headers=auth_headers).json()
    assert t["code"] == 0 and t["data"]["status"] == "DISABLED"
    u = client.put(f"/api/v1/orientation/checkin-points/{pid}", headers=auth_headers, json={"capacity": 500}).json()
    assert u["code"] == 0
    d = client.post(f"/api/v1/orientation/checkin-points/{pid}/delete", headers=auth_headers).json()
    assert d["code"] == 0
    assert client.get("/api/v1/orientation/checkin-points", headers=auth_headers).json()["data"]["total"] == 0


def test_flow_config(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/orientation/flow-config", headers=auth_headers).json()
    assert lst["code"] == 0 and len(lst["data"]) == 7  # 首次自动 seed 7 环节
    fid = lst["data"][3]["id"]
    upd = client.put(f"/api/v1/orientation/flow-config/{fid}", headers=auth_headers, json={"enabled": False}).json()
    assert upd["code"] == 0 and upd["data"]["enabled"] is False
    again = client.get("/api/v1/orientation/flow-config", headers=auth_headers).json()
    assert again["code"] == 0 and len(again["data"]) == 7  # 不重复 seed

    created = client.post("/api/v1/orientation/batches", headers=auth_headers, json={
        "batchName": "下一届冻结版本测试", "batchNo": "ORI-NEXT-FLOW-VERSION", "year": "2027",
    }).json()
    assert created["code"] == 0
    activated = client.post(
        f"/api/v1/orientation/batches/{created['data']['id']}/activate", headers=auth_headers
    ).json()
    assert activated["code"] == 0

    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import OrientationBatch, OrientationFlowStep
    db = get_sessionmaker()()
    try:
        old_batch = db.get(OrientationBatch, ids["batch"])
        new_batch = db.get(OrientationBatch, int(created["data"]["id"]))
        assert old_batch.flow_version_id != new_batch.flow_version_id
        old_payment = db.scalars(select(OrientationFlowStep).where(
            OrientationFlowStep.flow_version_id == old_batch.flow_version_id,
            OrientationFlowStep.step_key == "PAYMENT",
        )).one()
        new_payment = db.scalars(select(OrientationFlowStep).where(
            OrientationFlowStep.flow_version_id == new_batch.flow_version_id,
            OrientationFlowStep.step_key == "PAYMENT",
        )).one()
        assert old_payment.enabled is True
        assert new_payment.enabled is False
    finally:
        db.close()


def test_complete_standard_flow_config_is_explicit_idempotent_and_preserves_legacy(client, auth_headers, db_mode):
    from sqlalchemy import delete, func, select
    from app.db.session import get_sessionmaker
    from app.models import OrientationAuditTrail, OrientationBatch, OrientationFlowConfig, OrientationFlowStep, OrientationFlowVersion, OrientationStudent
    from app.services.orientation_flow_service import ensure_published_flow_version

    db = get_sessionmaker()()
    try:
        db.execute(delete(OrientationFlowConfig).where(OrientationFlowConfig.tenant_id == MAIN_TID))
        db.add_all([
            OrientationFlowConfig(tenant_id=MAIN_TID, step_key="IDENTITY", step_name="身份核验", enabled=True, required=True, sort_order=10),
            OrientationFlowConfig(tenant_id=MAIN_TID, step_key="DORM", step_name="宿舍办理", enabled=False, required=False, sort_order=20),
            OrientationFlowConfig(tenant_id=MAIN_TID, step_key="FINANCE", step_name="绿色通道", enabled=True, required=False, sort_order=30),
        ])
        db.flush()
        legacy_version = ensure_published_flow_version(db, MAIN_TID)
        empty_batch = OrientationBatch(tenant_id=MAIN_TID, batch_name="空批次流程升级测试",
                                       batch_no="ORI-EMPTY-FLOW-REFRESH", year="2027",
                                       status="ACTIVE", flow_version_id=legacy_version.id)
        db.add(empty_batch); db.flush()
        empty_batch_id = int(empty_batch.id)
        historical_batch = OrientationBatch(
            tenant_id=MAIN_TID, batch_name="含作废历史名单的批次",
            batch_no="ORI-HISTORICAL-FLOW-REFRESH", year="2027",
            status="ACTIVE", flow_version_id=legacy_version.id,
        )
        db.add(historical_batch); db.flush()
        historical_student = OrientationStudent(
            tenant_id=MAIN_TID, batch_id=historical_batch.id, name="已作废新生",
            admission_no="ORI-HISTORICAL-VOID-001", stage="ADMITTED",
            report_status="NOT_REPORTED", record_status="VOIDED", is_deleted=True,
            source_type="MANUAL", source_record_id="ORI-HISTORICAL-VOID-001",
            steps_json={"INFO": "TODO"},
        )
        db.add(historical_student)
        historical_batch_id = int(historical_batch.id)
        legacy_version_id = int(legacy_version.id)
        frozen_before = db.scalar(select(func.count()).select_from(OrientationFlowVersion).where(
            OrientationFlowVersion.tenant_id == MAIN_TID,
        )) or 0
        db.commit()
    finally:
        db.close()

    first = client.post("/api/v1/orientation/flow-config/complete-standard", headers=auth_headers).json()
    assert first["code"] == 0
    assert first["data"]["addedCount"] == 6
    assert first["data"]["restoredCount"] == 0
    assert first["data"]["totalCount"] == 9
    assert {"ACTIVATE", "INFO", "MATERIAL", "PAYMENT", "DORM", "CHECKIN", "CONFIRM"}.issubset(
        {item["stepKey"] for item in first["data"]["items"]}
    )
    dorm = next(item for item in first["data"]["items"] if item["stepKey"] == "DORM")
    assert dorm["stepName"] == "宿舍办理" and dorm["enabled"] is False and dorm["required"] is False
    assert {"IDENTITY", "FINANCE"}.issubset({item["stepKey"] for item in first["data"]["items"]})
    assert first["data"]["retiredLegacyCount"] == 2
    assert all(not item["enabled"] for item in first["data"]["items"] if item["stepKey"] in {"IDENTITY", "FINANCE"})
    canonical = [item["stepKey"] for item in first["data"]["items"] if item["stepKey"] not in {"IDENTITY", "FINANCE"}]
    assert canonical == ["ACTIVATE", "INFO", "MATERIAL", "PAYMENT", "DORM", "CHECKIN", "CONFIRM"]
    legacy_id = next(item["id"] for item in first["data"]["items"] if item["stepKey"] == "IDENTITY")
    blocked = client.put(f"/api/v1/orientation/flow-config/{legacy_id}", headers=auth_headers, json={"enabled": True}).json()
    assert blocked["code"] != 0 and "历史兼容" in blocked["message"]

    second = client.post("/api/v1/orientation/flow-config/complete-standard", headers=auth_headers).json()
    assert second["code"] == 0 and second["data"]["addedCount"] == 0 and second["data"]["totalCount"] == 9

    historical = client.post(
        f"/api/v1/orientation/batches/{historical_batch_id}/refresh-flow-version",
        headers=auth_headers, json={"expectedVersion": 0},
    ).json()
    assert historical["code"] != 0 and "已有 1 名新生" in historical["message"]

    refreshed = client.post(f"/api/v1/orientation/batches/{empty_batch_id}/refresh-flow-version",
                            headers=auth_headers, json={"expectedVersion": 0}).json()
    assert refreshed["code"] == 0 and refreshed["data"]["changed"] is True
    assert int(refreshed["data"]["flowVersionId"]) != legacy_version_id
    stale = client.post(f"/api/v1/orientation/batches/{empty_batch_id}/refresh-flow-version",
                        headers=auth_headers, json={"expectedVersion": 0}).json()
    assert stale["code"] != 0 and "其他操作更新" in stale["message"]
    db = get_sessionmaker()()
    try:
        assert (db.scalar(select(func.count()).select_from(OrientationFlowVersion).where(
            OrientationFlowVersion.tenant_id == MAIN_TID,
        )) or 0) == frozen_before + 1
        assert (db.scalar(select(func.count()).select_from(OrientationFlowStep).where(
            OrientationFlowStep.flow_version_id == legacy_version_id,
        )) or 0) == 3
        refreshed_steps = list(db.scalars(select(OrientationFlowStep).where(
            OrientationFlowStep.flow_version_id == int(refreshed["data"]["flowVersionId"]),
        ).order_by(OrientationFlowStep.sort_order)))
        assert [step.step_key for step in refreshed_steps] == [
            "ACTIVATE", "INFO", "MATERIAL", "PAYMENT", "DORM", "CHECKIN", "CONFIRM",
            "IDENTITY", "FINANCE",
        ]
        assert [step.step_key for step in refreshed_steps if step.enabled] == [
            "ACTIVATE", "INFO", "MATERIAL", "PAYMENT", "CHECKIN", "CONFIRM",
        ]
        assert (db.scalar(select(func.count()).select_from(OrientationAuditTrail).where(
            OrientationAuditTrail.tenant_id == MAIN_TID,
            OrientationAuditTrail.action == "补齐标准流程环节",
        )) or 0) == 6
    finally:
        db.close()

def test_notice_send(client, auth_headers, db_mode):
    a = client.post("/api/v1/orientation/notices", headers=auth_headers,
                    json={"title": "报到须知", "channel": "INAPP"}).json()
    assert a["code"] == 0
    s1 = client.post(f"/api/v1/orientation/notices/{a['data']['id']}/send", headers=auth_headers).json()
    assert s1["code"] == 0 and s1["data"]["status"] == "SENT"
    b = client.post("/api/v1/orientation/notices", headers=auth_headers,
                    json={"title": "缴费提醒", "channel": "SMS"}).json()
    s2 = client.post(f"/api/v1/orientation/notices/{b['data']['id']}/send", headers=auth_headers).json()
    assert s2["code"] == 0 and s2["data"]["status"] == "DISABLED" and s2["data"]["failReason"]


def test_archive_requires_finished_batch(client, auth_headers, db_mode):
    _seed(db_mode)
    c = client.post("/api/v1/orientation/archives", headers=auth_headers,
                    json={"archiveName": "2026 迎新归档", "batchNo": "ORI-TEST-2026"}).json()
    assert c["code"] == 0
    aid = c["data"]["id"]
    r = client.post(f"/api/v1/orientation/archives/{aid}/run", headers=auth_headers).json()
    assert r["code"] != 0 and "关闭迎新批次" in r["message"]
    # 完整报到→学院确认→关闭批次→归档及幂等回读由 O5 同一业务故事验证。
    rows = client.get("/api/v1/orientation/archives", headers=auth_headers).json()["data"]["items"]
    assert next(row for row in rows if row["id"] == aid)["status"] == "PENDING"
