"""在校服务域种子（主租户；幂等）。独立台账。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (CsAuditTrail, CsDiscipline, CsDormException, CsDormRecord, CsGrant, CsLeave,
                        CsMentalRecord, CsServiceStudent, CsWorkOrder)

TID = 1000000000000000001


def seed_campus_service(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(CsServiceStudent).where(CsServiceStudent.tenant_id == tenant_id)).first():
        return {"skipped": True}
    now = datetime.now()
    classes = [("CL01", "软件2401班"), ("CL02", "大数据2401班"), ("CL03", "机电2401班")]
    care = ["NORMAL", "NORMAL", "FOCUS", "NORMAL", "KEY_CARE", "NORMAL", "FOCUS", "NORMAL", "NORMAL", "NORMAL"]
    risk = ["LOW", "LOW", "MEDIUM", "LOW", "HIGH", "LOW", "MEDIUM", "LOW", "LOW", "LOW"]
    stus = []
    for i in range(10):
        cid, cname = classes[i % 3]
        s = CsServiceStudent(tenant_id=tenant_id, name=f"在校生{i + 1:02d}", student_no=f"2024{i + 1:06d}",
                             gender="男" if i % 2 == 0 else "女", college_name="信息工程学院",
                             major_name="软件技术", class_id=cid, class_name=cname, grade="2024级",
                             phone_encrypted=f"139{20000000 + i:08d}", id_card_encrypted=f"3301022006{i:08d}",
                             counselor="李辅导", building=f"B{3 + (i % 3) * 2}", room=f"{310 + i}-{(i % 4) + 1}",
                             care_level=care[i], risk_level=risk[i], mental_flag=(i == 4 or i == 6))
        db.add(s)
        db.flush()
        stus.append(s)
        db.add(CsDormRecord(tenant_id=tenant_id, cs_student_id=s.id, building=s.building, room=s.room,
                            bed=str((i % 4) + 1), checkin_date=datetime(2024, 9, 1), status="IN"))

    # 请假（3 待审 + 1 已批）
    db.add_all([
        CsLeave(tenant_id=tenant_id, code="LV-2026-0812", cs_student_id=stus[2].id, leave_type="SICK",
                start_time=now, end_time=now + timedelta(days=2), duration="2 天", reason="感冒发烧就医",
                status="PENDING_REVIEW", apply_time=now - timedelta(hours=2)),
        CsLeave(tenant_id=tenant_id, code="LV-2026-0813", cs_student_id=stus[5].id, leave_type="PERSONAL",
                start_time=now, end_time=now + timedelta(days=1), duration="1 天", reason="家中有事",
                status="PENDING_REVIEW", apply_time=now - timedelta(hours=1)),
        CsLeave(tenant_id=tenant_id, code="LV-2026-0810", cs_student_id=stus[0].id, leave_type="GOOUT",
                start_time=now - timedelta(days=2), end_time=now - timedelta(days=1), duration="1 天",
                reason="校外实践", status="APPROVED", apply_time=now - timedelta(days=3),
                reviewer="李辅导", review_time=now - timedelta(days=2)),
    ])
    # 资助（2 待审 + 1 审核中）
    db.add_all([
        CsGrant(tenant_id=tenant_id, code="GR-2026-0231", cs_student_id=stus[4].id, grant_type="NATIONAL_GRANT",
                amount=3300, apply_reason="家庭经济困难", material_sensitive=True, status="REVIEWING",
                apply_time=now - timedelta(days=3), current_node="资助老师审核"),
        CsGrant(tenant_id=tenant_id, code="GR-2026-0232", cs_student_id=stus[6].id, grant_type="HARDSHIP",
                amount=1500, apply_reason="突发困难", material_sensitive=True, status="PENDING_REVIEW",
                apply_time=now - timedelta(days=1), current_node="待资助老师领取"),
    ])
    # 宿舍异常（2）
    db.add_all([
        CsDormException(tenant_id=tenant_id, code="DE-2026-0092", cs_student_id=stus[2].id,
                        exc_type="NIGHT_OUT", happen_time=now - timedelta(hours=8), detail="超过晚归时间 30 分钟",
                        status="PENDING_HANDLE", handler="宿管王老师"),
        CsDormException(tenant_id=tenant_id, code="DE-2026-0093", cs_student_id=stus[4].id,
                        exc_type="NO_RETURN", happen_time=now - timedelta(days=1), detail="夜不归宿未报备",
                        status="PROCESSING", handler="李辅导", handle_note="已联系家长核实",
                        handle_time=now - timedelta(hours=12)),
    ])
    # 违纪（1）
    db.add(CsDiscipline(tenant_id=tenant_id, code="DIS-2026-0012", cs_student_id=stus[4].id,
                        disc_type="WARNING", reason="夜不归宿且屡教不改，给予警告处分",
                        decide_date=now - timedelta(days=5), doc_no="学字〔2026〕12 号", status="EFFECTIVE"))
    # 工单（3：待处理/处理中/办结）
    db.add_all([
        CsWorkOrder(tenant_id=tenant_id, code="WO-2026-1102", cs_student_id=stus[9].id,
                    title="申请在读证明（英文版）", wo_type="CERT", priority="MEDIUM", status="PENDING_HANDLE",
                    detail="用于签证申请", trail_json=[{"title": "工单创建", "desc": "学生提交",
                    "time": (now - timedelta(days=1)).isoformat(timespec="seconds"), "tone": "processing"}]),
        CsWorkOrder(tenant_id=tenant_id, code="WO-2026-1103", cs_student_id=stus[1].id,
                    title="宿舍空调报修", wo_type="REPAIR", priority="HIGH", status="PROCESSING",
                    handler="后勤张师傅", detail="空调不制冷"),
        CsWorkOrder(tenant_id=tenant_id, code="WO-2026-1100", cs_student_id=stus[0].id,
                    title="校园卡挂失", wo_type="CONSULT", priority="LOW", status="COMPLETED",
                    handler="王学工", close_time=now - timedelta(days=1)),
    ])
    # 心理关怀（涉密，2）
    db.add_all([
        CsMentalRecord(tenant_id=tenant_id, cs_student_id=stus[4].id, level="FOCUS",
                       last_follow_time=now - timedelta(days=4), next_follow_time=now + timedelta(days=6),
                       summary="情绪波动，需持续关注", counselor_note="[涉密] 家庭变故导致情绪低落，已安排每周谈话",
                       operator="周心理", status="PROCESSING"),
        CsMentalRecord(tenant_id=tenant_id, cs_student_id=stus[6].id, level="NORMAL",
                       last_follow_time=now - timedelta(days=10), summary="适应良好",
                       counselor_note="[涉密] 常规关注", operator="周心理", status="COMPLETED"),
    ])
    db.add(CsAuditTrail(tenant_id=tenant_id, biz_type="RECORD", biz_id=str(stus[0].id),
                        action="导入服务台账", operator="系统", detail="批量导入 10 名在校生",
                        occurred_at=now - timedelta(days=6)))
    db.commit()
    return {"students": len(stus), "leaves": 3, "grants": 2, "dormExc": 2, "disc": 1, "workOrders": 3}
