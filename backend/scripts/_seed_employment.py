"""就业服务域种子（主租户；幂等）。独立台账。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (EmpAuditTrail, EmpCompany, EmpFollowup, EmpJob, EmpMaterial, EmpStudent)

TID = 1000000000000000001


def seed_employment(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(EmpStudent).where(EmpStudent.tenant_id == tenant_id)).first():
        return {"skipped": True}
    now = datetime.now()
    classes = [("CL01", "软件2301班"), ("CL02", "大数据2301班")]
    dests = ["SIGNED", "SIGNED", "FLEXIBLE", "UNEMPLOYED", "FURTHER_STUDY", "UNEMPLOYED",
             "SIGNED", "STARTUP", "UNEMPLOYED", "SIGNED"]
    stus = []
    for i in range(10):
        cid, cname = classes[i % 2]
        dest = dests[i]
        help_lvl = "KEY_HELP" if dest == "UNEMPLOYED" and i in (3, 8) else "NORMAL"
        risk = "HIGH" if help_lvl == "KEY_HELP" else ("MEDIUM" if dest == "UNEMPLOYED" else "LOW")
        s = EmpStudent(tenant_id=tenant_id, name=f"毕业生{i + 1:02d}", student_no=f"2023{i + 1:06d}",
                       gender="男" if i % 2 == 0 else "女", grade="2026届", college_name="信息工程学院",
                       major_name="软件技术", class_id=cid, class_name=cname,
                       phone_encrypted=f"138{50000000 + i:08d}", id_card_encrypted=f"3301022004{i:08d}",
                       destination_type=dest,
                       company_name="杭州云启科技有限公司" if dest == "SIGNED" else None,
                       job_title="前端开发工程师" if dest == "SIGNED" else None,
                       salary_range="6k-8k" if dest == "SIGNED" else None,
                       sign_date="2026-05-12" if dest == "SIGNED" else None,
                       is_match_major=dest == "SIGNED", from_internship=i in (0, 6),
                       verify_status="VERIFIED" if dest == "SIGNED" else "PENDING_VERIFY",
                       material_status="APPROVED" if dest == "SIGNED" else "SUBMITTED",
                       help_level=help_lvl, risk_level=risk, counselor="李辅导",
                       employment_teacher="王就业" if help_lvl == "KEY_HELP" else None,
                       unemployed_reason="求职意向未明确" if dest == "UNEMPLOYED" else None,
                       last_follow_up_time=now - timedelta(days=3) if dest == "UNEMPLOYED" else None,
                       follow_up_count=2 if dest == "UNEMPLOYED" else 0)
        db.add(s)
        db.flush()
        stus.append(s)

    # 材料：待审 3 + 通过 2
    for idx, (sid_idx, mtype, st) in enumerate([
        (2, "OFFER", "SUBMITTED"), (4, "STUDY_PROOF", "SUBMITTED"), (7, "STARTUP_PROOF", "SUBMITTED"),
        (0, "AGREEMENT", "APPROVED"), (6, "AGREEMENT", "APPROVED")]):
        db.add(EmpMaterial(tenant_id=tenant_id, emp_student_id=stus[sid_idx].id, material_type=mtype,
                           file_name=f"{mtype}-材料.pdf", submit_time=now - timedelta(days=idx + 1),
                           status=st, reviewer="王就业" if st == "APPROVED" else None,
                           review_time=now - timedelta(days=idx) if st == "APPROVED" else None))

    # 跟进（未就业学生）
    for idx in (3, 5, 8):
        db.add(EmpFollowup(tenant_id=tenant_id, emp_student_id=stus[idx].id, way="PHONE",
                           content="电话沟通求职意向，推荐 2 个岗位", result="同意投递",
                           next_plan="一周后回访面试进展", operator="王就业", status="OPEN",
                           follow_time=now - timedelta(days=3)))

    # 企业 3 + 岗位 4
    comps = []
    for ci, (cname, cc, coop) in enumerate([
        ("杭州云启科技有限公司", "91330100MA27K1XX0A", "深度合作"),
        ("星辰网络技术有限公司", "91330100MA28K2YY1B", "常规合作"),
        ("华信智能科技有限公司", "91330100MA29K3ZZ2C", "深度合作")]):
        c = EmpCompany(tenant_id=tenant_id, name=cname, credit_code=cc, industry="软件和信息技术服务业",
                       nature="民营企业", city="杭州", contact_person="沈经理",
                       contact_phone_encrypted="13900112233", cooperation_level=coop, status="ACTIVE",
                       hired_count=3 if ci == 0 else 1)
        db.add(c)
        db.flush()
        comps.append(c)
    for ji, (comp_idx, title, hc) in enumerate([
        (0, "前端开发工程师", 5), (0, "测试工程师", 3), (1, "运维工程师", 2), (2, "算法实习生", 4)]):
        db.add(EmpJob(tenant_id=tenant_id, company_id=comps[comp_idx].id, company_name=comps[comp_idx].name,
                      title=title, category="软件开发", salary_range="6k-9k", headcount=hc,
                      signed_count=2 if ji == 0 else 0, status="OPEN", publish_time="2026-03-01"))

    db.add(EmpAuditTrail(tenant_id=tenant_id, biz_type="RECORD", biz_id=str(stus[0].id),
                         action="导入就业台账", operator="系统", detail="批量导入 10 名毕业生",
                         occurred_at=now - timedelta(days=30)))
    db.commit()
    return {"students": len(stus), "materials": 5, "followups": 3, "companies": 3, "jobs": 4}
