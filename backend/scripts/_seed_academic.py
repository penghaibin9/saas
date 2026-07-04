"""学业过程域种子（主租户；幂等）。独立台账。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (AcademicAuditTrail, AcademicGrade, AcademicMakeup, AcademicRetake,
                        AcademicStudent, AcademicWarning)

TID = 1000000000000000001


def seed_academic(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(AcademicStudent).where(AcademicStudent.tenant_id == tenant_id)).first():
        return {"skipped": True}
    now = datetime.now()
    classes = [("CL01", "软件2301班"), ("CL02", "大数据2301班"), ("CL03", "机电2301班")]
    stus = []
    for i in range(10):
        cid, cname = classes[i % 3]
        failed = [0, 0, 1, 3, 0, 2, 0, 0, 1, 0][i]
        obt = [66, 70, 55, 40, 72, 48, 68, 74, 58, 71][i]
        wl = ["NONE", "NONE", "LOW", "HIGH", "NONE", "MEDIUM", "NONE", "NONE", "LOW", "NONE"][i]
        ast = "NORMAL" if wl == "NONE" else ("HELPING" if wl == "HIGH" else "WARNING")
        s = AcademicStudent(tenant_id=tenant_id, name=f"学业生{i + 1:02d}", student_no=f"2023{i + 1:06d}",
                            class_id=cid, class_name=cname, college_name="信息工程学院",
                            major_name="软件技术", grade="2023级", phone_encrypted=f"137{30000000 + i:08d}",
                            counselor="李敏", gpa=round(3.5 - failed * 0.4, 1), avg_score=85 - failed * 8,
                            failed_count=failed, obtained_credits=obt, required_credits=120,
                            makeup_count=1 if failed and i in (2, 3, 5) else 0,
                            warning_level=wl, warning_count=1 if wl != "NONE" else 0, academic_status=ast)
        db.add(s)
        db.flush()
        stus.append(s)
        # 成绩：每人 3 门
        for j, (cn, nat, cr) in enumerate([("Web前端开发", "REQUIRED", 4), ("高等数学", "REQUIRED", 5),
                                           ("职业素养", "ELECTIVE", 2)]):
            sc = 92 - i * 3 - j * 5
            sc = max(30, min(98, sc))
            db.add(AcademicGrade(tenant_id=tenant_id, acad_student_id=s.id, course_name=cn, term="2025-2026-2",
                                 nature=nat, credit_value=cr, score=sc,
                                 pass_status="PASSED" if sc >= 60 else "FAILED", exam_type="FINAL"))

    # 补考 3 条
    for idx in (2, 3, 5):
        db.add(AcademicMakeup(tenant_id=tenant_id, acad_student_id=stus[idx].id, course_name="高等数学",
                              term="2025-2026-2", origin_score=52, exam_date="2026-09-06 09:00 · 实训楼A302",
                              status="PENDING_EXAM"))
    # 重修 1 条
    db.add(AcademicRetake(tenant_id=tenant_id, acad_student_id=stus[3].id, course_name="高等数学",
                          retake_term="2026-2027-1", reason="补考未通过，转入重修", status="STUDYING"))
    # 预警：学生3(HIGH,已升级帮扶)、学生5(MEDIUM,待处理)、学生2/8(LOW)
    db.add_all([
        AcademicWarning(tenant_id=tenant_id, code="AW-2026-0001", acad_student_id=stus[3].id,
                        warn_type="MULTI_FAIL", level="HIGH",
                        reason="本学期 3 门必修未通过，累计挂科（规则 ACAD-R03）",
                        source_rule="ACAD-R03 · 多门挂科自动预警", owner="学院学业帮扶专班",
                        status="ESCALATED", trigger_time=now - timedelta(days=8), deadline="2026-07-10"),
        AcademicWarning(tenant_id=tenant_id, code="AW-2026-0002", acad_student_id=stus[5].id,
                        warn_type="CREDIT_GAP", level="MEDIUM",
                        reason="已获学分 48，距中期应达 60 存在缺口（规则 ACAD-R05）",
                        source_rule="ACAD-R05 · 学分不足预警", owner="李敏（辅导员）",
                        status="PENDING_HANDLE", trigger_time=now - timedelta(days=3), deadline="2026-07-15"),
        AcademicWarning(tenant_id=tenant_id, code="AW-2026-0003", acad_student_id=stus[2].id,
                        warn_type="GRADE_DROP", level="LOW", reason="本学期均分较上学期下滑 12 分",
                        source_rule="ACAD-R08 · 成绩下滑预警", owner="李敏（辅导员）",
                        status="PROCESSING", trigger_time=now - timedelta(days=5)),
    ])
    db.add(AcademicAuditTrail(tenant_id=tenant_id, biz_type="RECORD", biz_id=str(stus[0].id),
                              action="导入学业台账", operator="系统", detail="批量导入 10 名学业学生",
                              occurred_at=now - timedelta(days=6)))
    db.commit()
    return {"students": len(stus), "grades": 30, "makeups": 3, "retakes": 1, "warnings": 3}
