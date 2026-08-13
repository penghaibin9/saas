"""20K 售前沙箱轻量故事线恢复。

全量 20K 是部署级数据包，不应该通过普通 HTTP 请求反复删除/重建几十万行。
现场销售演示只恢复三条可操作故事线，保留 20K 背景主数据和历史事实：
- 李体验（2026S0001）：迎新材料复核 + 学生待办 + 辅导员待办；
- 陈思雨（2025S0001）：学生事务服务工单 + 辅导员待办；
- 周启航（2024S0001）：实习周报重新置为待批阅 + 指导教师待办。

所有新增行都有 SALES_STORY 标识，下一次恢复只清这些小量行，不触碰背景数据。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select

STORY_BIZ_TYPE = "SALES_STORY"
STORY_REMARK = "SALES_STORY_RESET"
EXPECTED_STANDARD_STUDENTS = 20_000


def _student(db, tenant_id: int, student_no: str):
    from app.models import StudentProfile
    row = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.student_no == student_no,
        StudentProfile.is_deleted.is_(False),
    )).first()
    if row is None:
        raise RuntimeError(f"销售故事学生不存在: {student_no}")
    return row


def is_standard_20k_sandbox(db, tenant_id: int) -> bool:
    from app.models import StudentProfile
    count = int(db.scalar(select(func.count()).select_from(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    )) or 0)
    return count == EXPECTED_STANDARD_STUDENTS


def restore_sales_storylines(db, tenant_id: int) -> dict:
    from app.models import (
        CsServiceStudent,
        CsWorkOrder,
        InternshipRecord,
        OrientationException,
        OrientationMaterial,
        OrientationStudent,
        SchoolClass,
        StudentAccountLink,
        UnifiedMessage,
        UnifiedTodo,
        User,
        WeeklyReport,
    )

    if not is_standard_20k_sandbox(db, tenant_id):
        raise RuntimeError("当前 sandbox 不是 standard-20k，拒绝执行轻量故事线恢复")

    li = _student(db, tenant_id, "2026S0001")
    chen = _student(db, tenant_id, "2025S0001")
    zhou = _student(db, tenant_id, "2024S0001")

    # 先删上一次轻量恢复产生的独立行；背景 20K 事实不动。
    db.execute(delete(UnifiedTodo).where(
        UnifiedTodo.tenant_id == tenant_id,
        UnifiedTodo.source_biz_type == STORY_BIZ_TYPE,
    ))
    db.execute(delete(UnifiedMessage).where(
        UnifiedMessage.tenant_id == tenant_id,
        UnifiedMessage.remark == STORY_REMARK,
    ))

    ori = db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == tenant_id,
        OrientationStudent.student_id == li.id,
        OrientationStudent.is_deleted.is_(False),
    )).one()
    # 只删除明确属于销售故事的材料/异常，绝不删真实比例背景行。
    story_materials = list(db.scalars(select(OrientationMaterial.id).where(
        OrientationMaterial.tenant_id == tenant_id,
        OrientationMaterial.ori_student_id == ori.id,
        OrientationMaterial.file_name.like("SALES-STORY-%"),
    )))
    if story_materials:
        db.execute(delete(OrientationMaterial).where(OrientationMaterial.id.in_(story_materials)))
    story_exceptions = list(db.scalars(select(OrientationException.id).where(
        OrientationException.tenant_id == tenant_id,
        OrientationException.ori_student_id == ori.id,
        OrientationException.description.like("SALES-STORY:%"),
    )))
    if story_exceptions:
        db.execute(delete(OrientationException).where(OrientationException.id.in_(story_exceptions)))

    # 陈思雨的销售故事工单同样用明确 code 前缀清理。
    cs_chen = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == tenant_id,
        CsServiceStudent.student_id == chen.id,
        CsServiceStudent.is_deleted.is_(False),
    )).one()
    old_workorders = list(db.scalars(select(CsWorkOrder.id).where(
        CsWorkOrder.tenant_id == tenant_id,
        CsWorkOrder.cs_student_id == cs_chen.id,
        CsWorkOrder.code.like("SALES-%"),
    )))
    if old_workorders:
        db.execute(delete(CsWorkOrder).where(CsWorkOrder.id.in_(old_workorders)))
    db.flush()

    # ── 故事线 A：李体验 / 新生迎新材料待复核 ──
    material = OrientationMaterial(
        tenant_id=tenant_id,
        ori_student_id=ori.id,
        material_type="ADMISSION_LETTER",
        file_name="SALES-STORY-2026S0001-录取通知书.pdf",
        submit_time=datetime(2026, 8, 13, 8, 20),
        status="UPLOADED",
    )
    exception = OrientationException(
        tenant_id=tenant_id,
        ori_student_id=ori.id,
        exception_type="MATERIAL",
        description="SALES-STORY: 录取通知书扫描件清晰度待辅导员人工复核",
        risk_level="MEDIUM",
        status="OPEN",
    )
    db.add_all([material, exception])
    db.flush()

    teacher2 = db.scalars(select(User).where(
        User.tenant_id == tenant_id,
        User.login_name == "teacher2",
        User.is_deleted.is_(False),
    )).one()
    student2 = db.scalars(select(User).join(
        StudentAccountLink,
        StudentAccountLink.user_id == User.id,
    ).where(
        User.tenant_id == tenant_id,
        StudentAccountLink.tenant_id == tenant_id,
        StudentAccountLink.student_id == li.id,
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
        User.is_deleted.is_(False),
    )).one()
    db.add(UnifiedTodo(
        tenant_id=tenant_id,
        source_module="orientation",
        source_biz_type=STORY_BIZ_TYPE,
        source_biz_id=exception.id,
        todo_type="ORIENTATION_MATERIAL_REVIEW",
        assignee_id=teacher2.id,
        student_id=li.id,
        title="复核李体验的新生报到材料",
        status="PENDING",
        due_at=datetime(2026, 8, 15, 18, 0),
        remark=STORY_REMARK,
    ))
    db.add(UnifiedTodo(
        tenant_id=tenant_id,
        source_module="orientation",
        source_biz_type=STORY_BIZ_TYPE,
        source_biz_id=material.id,
        todo_type="ORIENTATION_PRECHECK",
        assignee_id=student2.id,
        student_id=li.id,
        title="确认报到材料并完成预报到信息核对",
        status="PENDING",
        due_at=datetime(2026, 9, 3, 18, 0),
        remark=STORY_REMARK,
    ))
    db.add(UnifiedMessage(
        tenant_id=tenant_id,
        receiver_id=student2.id,
        receiver_user_id=student2.id,
        receiver_type="STUDENT",
        receiver_context_key="GLOBAL",
        source_module="orientation",
        source_biz_id=exception.id,
        title="报到材料正在复核",
        content="你的录取通知书材料已提交，辅导员正在复核。请留意处理结果与后续报到提醒。",
        message_type="BUSINESS",
        status="UNREAD",
        priority="NORMAL",
        category="BUSINESS",
        delivered_at=datetime(2026, 8, 13, 8, 30),
        delivery_status="DELIVERED",
        rendered_title="报到材料正在复核",
        rendered_content_plain="你的录取通知书材料已提交，辅导员正在复核。请留意处理结果与后续报到提醒。",
        sender_org_name_snapshot="信息工程学院",
        remark=STORY_REMARK,
    ))

    # ── 故事线 B：陈思雨 / 学生事务服务工单 ──
    workorder = CsWorkOrder(
        tenant_id=tenant_id,
        code="SALES-WO-2025S0001",
        cs_student_id=cs_chen.id,
        title="开具在读证明",
        wo_type="CERT",
        priority="MEDIUM",
        handler=chen.real_name,
        status="PENDING_HANDLE",
        detail="学生申请用于暑期实践单位资格审核的在读证明。",
    )
    db.add(workorder)
    db.flush()
    chen_class = db.get(SchoolClass, chen.class_id)
    if chen_class is None or not chen_class.counselor_id:
        raise RuntimeError("陈思雨班级缺少辅导员")
    db.add(UnifiedTodo(
        tenant_id=tenant_id,
        source_module="campus-service",
        source_biz_type=STORY_BIZ_TYPE,
        source_biz_id=workorder.id,
        todo_type="SERVICE_WORKORDER",
        assignee_id=chen_class.counselor_id,
        student_id=chen.id,
        title="处理陈思雨的在读证明申请",
        status="PENDING",
        due_at=datetime(2026, 8, 14, 18, 0),
        remark=STORY_REMARK,
    ))

    # ── 故事线 C：周启航 / 实习周报待教师批阅 ──
    internship = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.student_id == zhou.id,
        InternshipRecord.is_deleted.is_(False),
    )).one()
    weekly = db.scalars(select(WeeklyReport).where(
        WeeklyReport.tenant_id == tenant_id,
        WeeklyReport.internship_id == internship.id,
        WeeklyReport.week_number == 1,
        WeeklyReport.is_deleted.is_(False),
    )).one()
    weekly.status = "PENDING_REVIEW"
    weekly.review_action = None
    weekly.review_comment = None
    weekly.reviewed_by_name = None
    weekly.reviewed_at = None
    weekly.submitted_at = datetime(2026, 8, 9, 20, 0)
    if not internship.advisor_user_id:
        raise RuntimeError("周启航实习记录缺少真实指导教师 user_id")
    db.add(UnifiedTodo(
        tenant_id=tenant_id,
        source_module="internship",
        source_biz_type=STORY_BIZ_TYPE,
        source_biz_id=weekly.id,
        todo_type="WEEKLY_REVIEW",
        assignee_id=internship.advisor_user_id,
        student_id=zhou.id,
        title="批阅周启航第1周岗位实习周报",
        status="PENDING",
        due_at=datetime(2026, 8, 15, 18, 0),
        remark=STORY_REMARK,
    ))

    db.commit()
    story_todos = int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(
        UnifiedTodo.tenant_id == tenant_id,
        UnifiedTodo.source_biz_type == STORY_BIZ_TYPE,
        UnifiedTodo.is_deleted.is_(False),
    )) or 0)
    return {
        "mode": "storyline",
        "preservedStudents": EXPECTED_STANDARD_STUDENTS,
        "stories": ["2026S0001-迎新", "2025S0001-学生事务", "2024S0001-岗位实习"],
        "storyTodos": story_todos,
        "fullRebuild": False,
    }
