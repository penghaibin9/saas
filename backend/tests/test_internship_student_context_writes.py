"""学生 PC/小程序共用的岗位实习 Context 写入口回归测试。"""
from __future__ import annotations

from uuid import uuid4

from app.core.security import create_access_token

TID = 1000000000000000001
BASE = "/api/v1/mobile/internship/context"


def _student_headers(student_no: str) -> dict:
    token = create_access_token({
        "userId": f"student-{student_no}",
        "realName": "Context 测试学生",
        "userType": "STUDENT",
        "tenantId": str(TID),
        "studentNo": student_no,
        "currentRoleCode": "STUDENT",
        "clientType": "MP",
    })
    return {"Authorization": f"Bearer {token}"}


def _two_batch_records(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    suffix = uuid4().hex[:10]
    student_no = f"CTX-{suffix}"
    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=TID,
            student_no=student_no,
            real_name="Context 测试学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        stale_batch = InternshipBatch(
            tenant_id=TID,
            batch_name=f"旧批次-{suffix}",
            batch_no=f"CTX-OLD-{suffix}",
            planned_count=1,
            status="RUNNING",
        )
        current_batch = InternshipBatch(
            tenant_id=TID,
            batch_name=f"当前批次-{suffix}",
            batch_no=f"CTX-NOW-{suffix}",
            planned_count=1,
            status="RUNNING",
        )
        db.add_all([stale_batch, current_batch])
        db.flush()
        stale_record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=stale_batch.id,
            status="ONBOARD",
            eligibility_status="QUALIFIED",
            destination_type="ASSIGNED",
            risk_level="NONE",
        )
        current_record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=current_batch.id,
            status="ONBOARD",
            eligibility_status="QUALIFIED",
            destination_type="ASSIGNED",
            risk_level="NONE",
        )
        db.add_all([stale_record, current_record])
        db.commit()
        return {
            "studentNo": student_no,
            "staleBatchId": stale_batch.id,
            "staleRecordId": stale_record.id,
            "batchId": current_batch.id,
            "recordId": current_record.id,
        }
    finally:
        db.close()


def test_change_write_rejects_record_from_other_selected_batch(client, db_mode):
    context = _two_batch_records(db_mode)
    headers = _student_headers(context["studentNo"])
    stale = client.post(f"{BASE}/changes", headers=headers, json={
        "batchId": context["staleBatchId"],
        "internshipId": context["recordId"],
        "expectedVersion": 0,
        "changeType": "WITHDRAW_POST",
        "reason": "旧页面保留了另一个批次的实习记录",
    })
    assert stale.status_code == 409
    assert stale.json()["code"] == 409001
    assert "不属于当前实习批次" in stale.json()["message"]

    current = client.post(f"{BASE}/changes", headers=headers, json={
        "batchId": context["batchId"],
        "internshipId": context["recordId"],
        "expectedVersion": 0,
        "changeType": "WITHDRAW_POST",
        "reason": "本人申请结束当前批次的实习岗位",
    })
    assert current.status_code == 200, current.json()
    assert current.json()["data"]["status"] == "PENDING"
    assert current.json()["data"]["version"] == 0


def test_returned_process_report_requires_current_version(client, db_mode):
    context = _two_batch_records(db_mode)
    headers = _student_headers(context["studentNo"])
    payload = {
        "batchId": context["batchId"],
        "internshipId": context["recordId"],
        "expectedVersion": 0,
        "reportType": "MONTHLY",
        "periodKey": "2026-07",
        "content": "本月完成岗位实践任务并持续整理工作记录。" * 12,
    }
    created = client.post(f"{BASE}/reports", headers=headers, json=payload)
    assert created.status_code == 200, created.json()
    report_id = created.json()["data"]["id"]

    from app.db.session import get_sessionmaker
    from app.models import InternshipProcessReport

    db = get_sessionmaker()()
    try:
        report = db.get(InternshipProcessReport, int(report_id))
        report.status = "RETURNED"
        report.version = 1
        db.commit()
    finally:
        db.close()

    stale = client.post(f"{BASE}/reports", headers=headers, json={
        **payload,
        "content": "根据教师退回意见补充本月岗位实践过程和成果说明。" * 12,
        "expectedVersion": 0,
    })
    assert stale.status_code == 409
    assert stale.json()["code"] == 409001

    resubmitted = client.post(f"{BASE}/reports", headers=headers, json={
        **payload,
        "content": "根据教师退回意见补充本月岗位实践过程和成果说明。" * 12,
        "expectedVersion": 1,
    })
    assert resubmitted.status_code == 200, resubmitted.json()
    assert resubmitted.json()["data"]["status"] == "PENDING_REVIEW"
    assert resubmitted.json()["data"]["version"] == 2


def test_weekly_context_write_carries_batch_record_and_version(client, db_mode):
    context = _two_batch_records(db_mode)
    headers = _student_headers(context["studentNo"])
    response = client.post(f"{BASE}/weekly-reports", headers=headers, json={
        "batchId": context["batchId"],
        "internshipId": context["recordId"],
        "expectedVersion": 0,
        "weekNo": 3,
        "workContent": "完成本周岗位任务并整理操作流程文档",
        "harvestContent": "掌握了岗位协作方法并提升问题分析能力",
        "planContent": "下周继续完成测试与复盘",
    })
    assert response.status_code == 200, response.json()
    assert response.json()["data"]["weekNo"] == 3
    assert response.json()["data"]["version"] == 0

    duplicate = client.post(f"{BASE}/weekly-reports", headers=headers, json={
        "batchId": context["batchId"],
        "internshipId": context["recordId"],
        "expectedVersion": 0,
        "weekNo": 3,
        "workContent": "重复提交本周岗位任务与操作流程文档",
        "harvestContent": "重复提交岗位协作方法与问题分析总结",
        "planContent": "下周继续完成测试与复盘",
    })
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 409001
