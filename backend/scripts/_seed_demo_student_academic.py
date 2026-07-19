"""把 demo 学生「张同学」(StudentProfile id=23, no 2026D0006, tenant demo-school)的
教务台账(AcademicStudent id=4)正确链到 StudentProfile，并补齐成绩/预警，
使学生 PC 门户「教务学业」页出真实数据。幂等：按 (课程,学期) 去重。

只影响 demo-school 张同学，纯 INSERT/UPDATE（无 DDL），可安全重跑。
用法：cd backend && .venv/Scripts/python.exe scripts/_seed_demo_student_academic.py
"""
from __future__ import annotations
import os
import sys
# 只把 backend 加进 path（不导入 _dev_env，那会强制 SQLite）；DB 走 backend/.env 的 MySQL。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from app.services.db_service import session
import app.models as M

DEMO = 1000000000000000003
PROFILE_ID = 23            # 张同学 StudentProfile.id
NO = "2026D0006"

GRADES = [
    # (课程, 学期, 性质, 学分, 分数)
    ("数据结构", "2025-2026-1", "REQUIRED", 4, 92),
    ("操作系统", "2025-2026-1", "REQUIRED", 3, 85),
    ("Web 前端开发", "2025-2026-1", "REQUIRED", 3, 88),
    ("大学英语(3)", "2025-2026-1", "REQUIRED", 3, 79),
    ("体育与健康(3)", "2025-2026-1", "REQUIRED", 1, 90),
    ("数字图像处理", "2025-2026-2", "REQUIRED", 4, 87),
    ("交互设计基础", "2025-2026-2", "REQUIRED", 3, 91),
    ("高等数学(下)", "2025-2026-2", "REQUIRED", 5, 76),
    ("职业素养与就业指导", "2025-2026-2", "ELECTIVE", 2, 94),
    ("摄影基础", "2025-2026-2", "ELECTIVE", 2, 89),
]


def main():
    with session() as db:
        acad = db.scalars(select(M.AcademicStudent).where(
            M.AcademicStudent.tenant_id == DEMO, M.AcademicStudent.student_no == NO)).first()
        if not acad:
            print("[FAIL] 未找到张同学教务台账")
            return
        # 1) 链接台账 → StudentProfile
        if acad.student_id != PROFILE_ID:
            acad.student_id = PROFILE_ID
            print(f"[LINK] AcademicStudent id={acad.id}.student_id -> {PROFILE_ID}")
        # 2) 补齐成绩（按 课程+学期 去重）；transcript 仅显示 record_status=ACTIVE
        cur = db.scalars(select(M.AcademicGrade).where(M.AcademicGrade.acad_student_id == acad.id)).all()
        for g in cur:
            if g.record_status != "ACTIVE":
                g.record_status = "ACTIVE"
        exist = {(g.course_name, g.term) for g in cur}
        added = 0
        for cn, term, nat, cr, sc in GRADES:
            if (cn, term) in exist:
                continue
            db.add(M.AcademicGrade(tenant_id=DEMO, acad_student_id=acad.id, course_name=cn, term=term,
                                   nature=nat, credit_value=cr, score=sc,
                                   pass_status="PASSED" if sc >= 60 else "FAILED",
                                   exam_type="FINAL", source="PUBLISH", record_status="ACTIVE"))
            added += 1
        # 3) 刷新台账汇总
        gs = db.scalars(select(M.AcademicGrade).where(M.AcademicGrade.acad_student_id == acad.id)).all()
        total_credit = sum(float(g.credit_value or 0) for g in gs if (g.pass_status == "PASSED"))
        avg = round(sum(float(g.score or 0) for g in gs) / len(gs), 1) if gs else 0
        acad.obtained_credits = total_credit
        acad.avg_score = avg
        acad.failed_count = sum(1 for g in gs if g.pass_status == "FAILED")
        # 4) 一条学业预警（毕业自查/首页预警可见），去重
        w = db.scalars(select(M.AcademicWarning).where(
            M.AcademicWarning.tenant_id == DEMO, M.AcademicWarning.acad_student_id == acad.id)).first()
        if not w:
            db.add(M.AcademicWarning(tenant_id=DEMO, code="AW-2026-D0006", acad_student_id=acad.id,
                                     warn_type="CREDIT_GAP", level="LOW",
                                     reason="选修学分距毕业要求尚有缺口，请关注第二课堂与公选课",
                                     source_rule="ACAD-R05 · 学分不足预警", owner="辅导员",
                                     status="PROCESSING"))
            print("[WARN] 新增 1 条学业预警")
        db.commit()
        print(f"[OK] 成绩已补 {added} 条 · 台账合计成绩 {len(gs)} 门 · 已获学分 {total_credit} · 均分 {avg}")


if __name__ == "__main__":
    main()
