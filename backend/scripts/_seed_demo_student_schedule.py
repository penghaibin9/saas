"""给 demo 学生张同学所在行政班(class_id=4)灌一张已发布课表(AaScheduleBatch PUBLISHED +
AaScheduleItem EFFECTIVE)，使学生 PC 门户「教务学业 · 我的课表」出真实周历。
幂等；纯 INSERT，仅 demo-school；无 DDL。
用法：cd backend && .venv/Scripts/python.exe scripts/_seed_demo_student_schedule.py
"""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta

from sqlalchemy import select
from app.services.db_service import session
import app.models as M

# 可选课程（OPEN 批次）：课程 / 教师 / 学分 / 容量 / 已选
SEL_COURSES = [
    ("大学生心理健康", "周芳", 2, 40, 30), ("摄影基础", "郑昊", 2, 40, 22),
    ("创业基础", "吴刚", 2, 40, 38), ("Python 数据分析", "赵敏", 3, 50, 41),
    ("短视频创作实务", "陈志强", 2, 45, 33), ("三维建模基础", "王建国", 3, 40, 18),
]


def seed_selection(db):
    b = db.scalars(select(M.AaSelectionBatch).where(
        M.AaSelectionBatch.tenant_id == DEMO, M.AaSelectionBatch.status == "OPEN",
        M.AaSelectionBatch.is_deleted.is_(False)).order_by(M.AaSelectionBatch.id.desc())).first()
    now = datetime.now()
    if not b:
        b = M.AaSelectionBatch(tenant_id=DEMO, term_id=20252026, batch_name="2025-2026学年第二学期公选课选课",
                               select_start_at=now - timedelta(days=1), select_end_at=now + timedelta(days=14),
                               apply_scope_json="{}", rule_json="{}", status="OPEN")
        db.add(b)
        db.flush()
        print(f"[SEL-BATCH] 新建 OPEN 选课批次 id={b.id}")
    else:
        print(f"[SEL-BATCH] 复用 OPEN 批次 id={b.id}")
    if db.scalars(select(M.AaSelectionCourse).where(
            M.AaSelectionCourse.tenant_id == DEMO, M.AaSelectionCourse.batch_id == b.id)).first():
        print("[SEL-SKIP] 该批次课程已存在，跳过")
        return
    for i, (cn, tc, cr, cap, sel) in enumerate(SEL_COURSES):
        db.add(M.AaSelectionCourse(tenant_id=DEMO, batch_id=b.id, course_id=9000 + i, course_name=cn,
                                   teacher_key=tc, teacher_name=tc, credit=cr, capacity=cap,
                                   min_capacity=5, selected_count=sel, status="OPEN"))
    print(f"[SEL-OK] 灌入 {len(SEL_COURSES)} 门可选课程")

DEMO = 1000000000000000003
CLASS_ID = 4
CLASS_NAME = "数媒2601班"

# (weekday 1..5, slot_no, 课程, 教师, 教室)  slot_no: 1/3/5/7/9 = 第1-2/3-4/5-6/7-8/9-10 节
ITEMS = [
    (1, 1, "数据结构", "王建国", "教1-301"), (1, 5, "数字图像处理", "赵敏", "实训楼302"),
    (2, 3, "交互设计基础", "陈志强", "艺术楼105"), (2, 7, "高等数学(下)", "李梅", "教2-105"),
    (3, 1, "数据结构", "王建国", "教1-301"), (3, 5, "数字图像处理", "赵敏", "实训楼302"),
    (4, 3, "交互设计基础", "陈志强", "艺术楼105"), (4, 9, "职业素养与就业指导", "孙丽", "教1-105"),
    (5, 1, "大学英语(3)", "李梅", "教2-105"), (5, 3, "体育与健康(3)", "刘洋", "操场"),
]


def main():
    with session() as db:
        b = db.scalars(select(M.AaScheduleBatch).where(
            M.AaScheduleBatch.tenant_id == DEMO, M.AaScheduleBatch.status == "PUBLISHED",
            M.AaScheduleBatch.is_deleted.is_(False)).order_by(M.AaScheduleBatch.id.desc())).first()
        if not b:
            b = M.AaScheduleBatch(tenant_id=DEMO, term_id=20252026, batch_name="2025-2026学年第二学期课表",
                                  status="PUBLISHED", publish_at=datetime.now())
            db.add(b)
            db.flush()
            print(f"[BATCH] 新建已发布课表批次 id={b.id}")
        else:
            print(f"[BATCH] 复用已发布批次 id={b.id}")
        exist = db.scalars(select(M.AaScheduleItem).where(
            M.AaScheduleItem.tenant_id == DEMO, M.AaScheduleItem.batch_id == b.id,
            M.AaScheduleItem.class_id == CLASS_ID)).first()
        if exist:
            print("[SKIP] 该班课表项已存在，跳过课表")
        else:
            for wd, slot, course, teacher, room in ITEMS:
                db.add(M.AaScheduleItem(tenant_id=DEMO, batch_id=b.id, course_name=course, class_id=CLASS_ID,
                                        class_name=CLASS_NAME, teacher_name=teacher, teacher_key=teacher,
                                        weekday=wd, slot_no=slot, start_week=1, end_week=18, week_parity="ALL",
                                        classroom_text=room, status="EFFECTIVE"))
            print(f"[OK] 已为 {CLASS_NAME}(class_id={CLASS_ID}) 灌入 {len(ITEMS)} 条课表项")
        seed_selection(db)
        db.commit()


if __name__ == "__main__":
    main()
