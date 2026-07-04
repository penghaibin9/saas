"""数字迎新域种子（主租户；幂等：已有迎新学生则跳过）。独立台账，不动 t_student_profile。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (GreenChannelApplication, OrientationAuditTrail, OrientationException,
                        OrientationExceptionFollowup, OrientationMaterial, OrientationStudent)

TID = 1000000000000000001
ALL_DONE = {"ACTIVATE": "DONE", "INFO": "DONE", "MATERIAL": "DONE", "PAYMENT": "DONE",
            "DORM": "DONE", "CHECKIN": "DONE", "CONFIRM": "DONE"}


def seed_orientation(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(OrientationStudent).where(OrientationStudent.tenant_id == tenant_id)).first():
        return {"skipped": True}
    now = datetime.now()
    colleges = ["信息工程学院", "机电学院"]
    majors = ["软件技术", "大数据技术", "机电一体化", "工业机器人"]
    classes = [("NCL01", "软件2601班"), ("NCL02", "大数据2601班"), ("NCL03", "机电2601班")]
    counselors = ["李辅导", "钱辅导", "周辅导"]

    students = []
    for i in range(12):
        cid, cname = classes[i % 3]
        # 构造多样化状态
        if i < 6:
            rp, pay, mat, dorm, risk, steps, bstep, breason = ("CHECKED_IN", "PAID", "APPROVED",
                "CHECKED_IN", "LOW", dict(ALL_DONE), None, None)
        elif i < 9:
            rp, pay, mat, dorm, risk = "PREPARED", "UNPAID", "UPLOADED", "ASSIGNED", "MEDIUM"
            steps = {**ALL_DONE, "PAYMENT": "BLOCKED", "DORM": "DOING", "CHECKIN": "TODO", "CONFIRM": "TODO"}
            bstep, breason = "PAYMENT", "学费未缴且未申请绿色通道"
        else:
            rp, pay, mat, dorm, risk = "NOT_REPORTED", "UNPAID", "NOT_UPLOADED", "UNASSIGNED", "HIGH"
            steps = {**{k: "TODO" for k in ALL_DONE}, "ACTIVATE": "BLOCKED"}
            bstep, breason = "ACTIVATE", "账号未激活，报到日未到校"
        s = OrientationStudent(
            tenant_id=tenant_id, name=f"新生{i + 1:02d}", admission_no=f"LQ2026{i + 1:06d}",
            gender="男" if i % 2 == 0 else "女", college_name=colleges[i % 2], major_name=majors[i % 4],
            class_id=cid, class_name=cname, grade="2026级",
            phone_encrypted=f"138{10000000 + i:08d}", id_card_encrypted=f"3301022008{i:08d}",
            origin=["浙江杭州", "江苏南京", "安徽合肥"][i % 3], stage="ADMITTED",
            report_status=rp, payment_status=pay, green_channel_status="NOT_APPLIED",
            material_status=mat, dorm_status=dorm, building="梧桐苑1号楼" if dorm != "UNASSIGNED" else None,
            room=f"1-{300 + i}-{(i % 4) + 1}" if dorm != "UNASSIGNED" else None, risk_level=risk,
            counselor=counselors[i % 3], steps_json=steps, blocked_step=bstep, blocked_reason=breason,
            payable_amount=8600, paid_amount=8600 if pay == "PAID" else (5000 if i == 6 else 0),
            checkin_time=now - timedelta(days=1) if rp == "CHECKED_IN" else None)
        db.add(s)
        db.flush()
        students.append(s)

    # 绿色通道申请（学生 7、8 申请）
    db.add_all([
        GreenChannelApplication(tenant_id=tenant_id, ori_student_id=students[6].id,
                                apply_type="生源地助学贷款", apply_amount=8600,
                                submit_time=now - timedelta(days=3), status="REVIEWING",
                                remark="贷款回执已上传"),
        GreenChannelApplication(tenant_id=tenant_id, ori_student_id=students[7].id,
                                apply_type="学费缓缴", apply_amount=8600,
                                submit_time=now - timedelta(days=2), status="SUBMITTED"),
    ])
    # 材料审核（学生 7 待审 2 份）
    db.add_all([
        OrientationMaterial(tenant_id=tenant_id, ori_student_id=students[6].id, material_type="AID_PROOF",
                            file_name="家庭经济困难认定表.pdf", submit_time=now - timedelta(days=3),
                            status="UPLOADED"),
        OrientationMaterial(tenant_id=tenant_id, ori_student_id=students[7].id, material_type="PHOTO",
                            file_name="证件照.jpg", submit_time=now - timedelta(days=2), status="UPLOADED"),
        OrientationMaterial(tenant_id=tenant_id, ori_student_id=students[0].id, material_type="ID_CARD",
                            file_name="身份证.pdf", submit_time=now - timedelta(days=5), status="APPROVED",
                            reviewer="学院迎新老师", review_time=now - timedelta(days=4)),
    ])
    db.flush()
    # 异常（学生 9、10、11 未到校/身份）
    for idx, (etype, desc, risk, st) in enumerate([
        ("NO_SHOW", "报到日未到校，电话未接通", "HIGH", "OPEN"),
        ("IDENTITY", "身份证信息与录取名单不一致", "MEDIUM", "PROCESSING"),
        ("PAYMENT", "缴费异常，银行流水未到账", "MEDIUM", "OPEN"),
    ]):
        e = OrientationException(tenant_id=tenant_id, ori_student_id=students[9 + idx].id,
                                 exception_type=etype, description=desc, risk_level=risk, status=st,
                                 handler=counselors[idx % 3],
                                 last_follow_time=now - timedelta(hours=6) if st == "PROCESSING" else None)
        db.add(e)
        db.flush()
        if st == "PROCESSING":
            db.add(OrientationExceptionFollowup(tenant_id=tenant_id, exception_id=e.id, way="PHONE",
                                                content="已电话联系家长核实身份信息", operator=counselors[idx % 3],
                                                status="ACTIVE", follow_time=now - timedelta(hours=6)))
    db.add(OrientationAuditTrail(tenant_id=tenant_id, biz_type="STUDENT", biz_id=str(students[0].id),
                                 action="导入新生名单", operator="系统", detail="批量导入 12 名新生",
                                 occurred_at=now - timedelta(days=6)))
    db.commit()
    return {"students": len(students), "greenChannels": 2, "materials": 3, "exceptions": 3}
