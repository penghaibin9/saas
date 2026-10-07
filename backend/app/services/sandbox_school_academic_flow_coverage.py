"""AA-001～024 演示业务流程覆盖审计。

与“表非空”不同，每个组件都要求至少存在一条具有业务含义的成功/终态事实。
跨表引用正确性仍由 sandbox_school_relationship_closure 的 P0/P1 检查负责。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text


@dataclass(frozen=True)
class FlowComponent:
    code: str
    title: str
    sql: str


def _count(table: str, where: str = "1=1") -> str:
    return f"SELECT COUNT(*) FROM {table} WHERE tenant_id=:tenant_id AND is_deleted=0 AND {where}"


FLOWS: dict[str, tuple[FlowComponent, ...]] = {
    "AA-001": (
        FlowComponent("CURRENT_TERM", "当前已发布学期", _count("t_aa_term", "is_current=1 AND status='PUBLISHED'")),
        FlowComponent("CALENDAR", "当前学期校历", """SELECT COUNT(*) FROM t_aa_calendar_event e JOIN t_aa_term t ON t.id=e.term_id AND t.tenant_id=e.tenant_id AND t.is_current=1 WHERE e.tenant_id=:tenant_id AND e.is_deleted=0"""),
        FlowComponent("TIME_SLOTS", "启用节次", _count("t_aa_time_slot", "status='ENABLED'")),
    ),
    "AA-002": (
        FlowComponent("REGISTERED", "学期注册成功", """SELECT COUNT(*) FROM t_aa_registration r JOIN t_aa_registration_batch b ON b.id=r.batch_id AND b.tenant_id=r.tenant_id WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND b.is_deleted=0 AND r.status='REGISTERED'"""),
        FlowComponent("REG_EXCEPTION", "注册异常", _count("t_aa_registration_exception")),
        FlowComponent("DEFERRAL", "暂缓注册已审批", _count("t_aa_registration_deferral", "status IN ('APPROVED','REJECTED')")),
        FlowComponent("CORRECTION_APPLIED", "学籍信息更正已生效", """SELECT COUNT(*) FROM t_aa_student_correction c JOIN t_student_profile s ON s.id=c.student_id AND s.tenant_id=c.tenant_id JOIN t_affairs_audit_trail a ON a.biz_type='AA_STUDENT_CORRECTION' AND a.biz_id=c.id AND a.tenant_id=c.tenant_id AND a.action='APPROVE' WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND c.status='APPROVED' AND s.is_deleted=0 AND ((c.field_key='REAL_NAME' AND s.real_name=c.new_value) OR (c.field_key='STUDENT_NO' AND s.student_no=c.new_value) OR (c.field_key='GENDER' AND s.gender=c.new_value) OR (c.field_key='GRADE' AND s.grade=c.new_value) OR c.field_key='ID_CARD')"""),
    ),
    "AA-003": (
        FlowComponent("EFFECTIVE_CHANGE", "学籍异动审批生效", """SELECT COUNT(*) FROM t_aa_status_change c JOIN t_workflow_instance w ON w.id=c.workflow_instance_id AND w.tenant_id=c.tenant_id AND w.status='APPROVED' WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND c.status='EFFECTIVE'"""),
        FlowComponent("CHANGE_FACT", "异动追加式学籍事实", """SELECT COUNT(*) FROM t_aa_student_academic_fact f JOIN t_aa_status_change c ON c.id=f.source_ref_id AND c.tenant_id=f.tenant_id WHERE f.tenant_id=:tenant_id AND f.source_type='STATUS_CHANGE' AND c.status='EFFECTIVE'"""),
        FlowComponent("CHANGE_MESSAGE", "异动结果消息事件", """SELECT COUNT(*) FROM t_message_event_outbox m JOIN t_aa_status_change c ON c.id=m.source_biz_id AND c.tenant_id=m.tenant_id WHERE m.tenant_id=:tenant_id AND m.is_deleted=0 AND m.source_biz_type='AA_STATUS_CHANGE' AND m.event_code='STATUS_CHANGE.RESULT' AND c.status='EFFECTIVE'"""),
    ),
    "AA-004": (
        FlowComponent("SPLIT_CONFIRMED", "分流批次确认", _count("t_aa_major_split_batch", "status='CONFIRMED'")),
        FlowComponent("SPLIT_FACT", "分流结果回写学籍事实", """SELECT COUNT(*) FROM t_aa_major_split_volunteer v JOIN t_aa_major_split_batch b ON b.id=v.batch_id AND b.tenant_id=v.tenant_id JOIN t_aa_student_academic_fact f ON f.student_id=v.student_id AND f.tenant_id=v.tenant_id AND f.source_type='MAJOR_SPLIT' AND f.source_ref_id=b.id WHERE v.tenant_id=:tenant_id AND v.is_deleted=0 AND v.status='CONFIRMED' AND b.status='CONFIRMED'"""),
    ),
    "AA-005": (
        FlowComponent("PROGRAM_ACTIVE", "已发布启用方案", _count("t_aa_program", "status IN ('PUBLISHED','ENABLED','FROZEN')")),
        FlowComponent("PROGRAM_VERSION", "培养方案版本链", """SELECT COUNT(*) FROM t_aa_program n JOIN t_aa_program p ON p.id=n.prev_version_id AND p.tenant_id=n.tenant_id WHERE n.tenant_id=:tenant_id AND n.is_deleted=0 AND p.is_deleted=0 AND n.version=p.version+1 AND n.series_key=p.series_key"""),
        FlowComponent("PROGRAM_BINDING", "方案绑定年级/班级", """SELECT COUNT(*) FROM t_aa_program_binding b JOIN t_aa_program p ON p.id=b.program_id AND p.tenant_id=b.tenant_id WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status='ACTIVE' AND p.status IN ('PUBLISHED','ENABLED','FROZEN')"""),
    ),
    "AA-006": (
        FlowComponent("COURSE_MATERIAL", "有效课程及教学材料", """SELECT COUNT(*) FROM t_aa_course_material m JOIN t_aa_course c ON c.id=m.course_id AND c.tenant_id=m.tenant_id WHERE m.tenant_id=:tenant_id AND m.is_deleted=0 AND m.status='ACTIVE' AND c.status='ENABLED'"""),
        FlowComponent("COURSE_TO_TASK", "有效课程进入开课任务", """SELECT COUNT(*) FROM t_aa_teaching_task t JOIN t_aa_course c ON c.id=t.course_id AND c.tenant_id=t.tenant_id JOIN t_aa_teaching_task_batch b ON b.id=t.batch_id AND b.tenant_id=t.tenant_id WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND c.status='ENABLED' AND b.status='APPROVED' AND t.status='READY'"""),
    ),
    "AA-007": (
        FlowComponent("LOCKED_ROSTER", "教学任务形成锁定教学班名单", """SELECT COUNT(*) FROM t_aa_teaching_task t JOIN t_aa_teaching_class c ON c.teaching_task_id=t.id AND c.tenant_id=t.tenant_id JOIN t_aa_teaching_class_roster_version v ON v.id=c.current_roster_version_id AND v.tenant_id=c.tenant_id WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND t.status='READY' AND c.is_deleted=0 AND c.status='ACTIVE' AND v.is_deleted=0 AND v.status='LOCKED'"""),
        FlowComponent("ROSTER_CONSUMERS", "名单被考勤/考务/成绩消费", """SELECT COUNT(*) FROM (SELECT teaching_task_id FROM t_aa_roster_consumer_snapshot WHERE tenant_id=:tenant_id AND is_deleted=0 AND consumer_type IN ('ATTENDANCE_SESSION','EXAM_COURSE','GRADE_TASK') GROUP BY teaching_task_id HAVING COUNT(DISTINCT consumer_type)=3) x"""),
    ),
    "AA-008": (
        FlowComponent("PUBLISHED_SCHEDULE", "ScopeHead 正式课表", """SELECT COUNT(*) FROM t_aa_schedule_scope_head h JOIN t_aa_schedule_batch b ON b.id=h.active_batch_id AND b.tenant_id=h.tenant_id WHERE h.tenant_id=:tenant_id AND h.is_deleted=0 AND b.is_deleted=0 AND b.status='PUBLISHED'"""),
        FlowComponent("SCHEDULE_LEDGER", "课表发布流水", """SELECT COUNT(*) FROM t_aa_schedule_publish p JOIN t_aa_schedule_batch b ON b.id=p.batch_id AND b.tenant_id=p.tenant_id WHERE p.tenant_id=:tenant_id AND p.is_deleted=0 AND b.status='PUBLISHED'"""),
    ),
    "AA-009": (
        FlowComponent("CHANGE_APPLIED", "调停课审批应用", """SELECT COUNT(*) FROM t_aa_schedule_change c JOIN t_aa_schedule_item i ON i.id=c.new_item_id AND i.tenant_id=c.tenant_id AND i.change_id=c.id WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND c.status='APPLIED' AND i.is_deleted=0 AND i.status='EFFECTIVE'"""),
        FlowComponent("CHANGE_ATTENDANCE", "变更课位进入课堂执行", """SELECT COUNT(*) FROM t_aa_attendance_session a JOIN t_aa_schedule_item i ON a.occurrence_identity LIKE CONCAT(i.batch_id, ':', i.id, ':%') AND i.tenant_id=a.tenant_id JOIN t_aa_schedule_change c ON c.id=i.change_id AND c.tenant_id=i.tenant_id WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND a.status='SUBMITTED' AND i.is_deleted=0 AND i.status='EFFECTIVE' AND c.status='APPLIED'"""),
    ),
    "AA-010": (
        FlowComponent("ATTENDANCE_SUBMITTED", "正式课堂点名提交", _count("t_aa_attendance_session", "status='SUBMITTED' AND source_type='FORMAL_TEACHING' AND total_count>0")),
        FlowComponent("ATTENDANCE_WARNING", "考勤/成绩预警及跟进", """SELECT COUNT(*) FROM t_acad_warning w JOIN t_acad_intervention i ON i.warning_id=w.id AND i.tenant_id=w.tenant_id WHERE w.tenant_id=:tenant_id AND w.is_deleted=0 AND i.is_deleted=0"""),
    ),
    "AA-011": (
        FlowComponent("SELECTION_STATES", "选中/退选/候补状态", """SELECT COUNT(*) FROM (SELECT batch_id FROM t_aa_selection_record WHERE tenant_id=:tenant_id AND is_deleted=0 GROUP BY batch_id HAVING COUNT(DISTINCT status)>=3) x"""),
        FlowComponent("SELECTION_ROSTER", "已选学生进入锁定教学班名单", """SELECT COUNT(*) FROM t_aa_selection_record r JOIN t_aa_selection_course sc ON sc.id=r.selection_course_id AND sc.tenant_id=r.tenant_id JOIN t_aa_teaching_class tc ON tc.teaching_task_id=sc.teaching_task_id AND tc.tenant_id=r.tenant_id JOIN t_aa_teaching_class_roster_version v ON v.id=tc.current_roster_version_id AND v.tenant_id=tc.tenant_id AND v.status='LOCKED' JOIN t_aa_teaching_class_member m ON m.teaching_class_id=tc.id AND m.roster_version_id=v.id AND m.student_id=r.student_id AND m.tenant_id=r.tenant_id WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND r.status='SELECTED' AND m.is_deleted=0 AND m.status='ACTIVE'"""),
    ),
    "AA-012": (
        FlowComponent("EXAM_PUBLISHED", "考试编排座位监考", """SELECT COUNT(*) FROM t_aa_exam_batch b JOIN t_aa_exam_course c ON c.batch_id=b.id AND c.tenant_id=b.tenant_id JOIN t_aa_exam_room r ON r.exam_course_id=c.id AND r.tenant_id=c.tenant_id JOIN t_aa_exam_room_student s ON s.exam_room_id=r.id AND s.tenant_id=r.tenant_id JOIN t_aa_exam_invigilator i ON i.exam_room_id=r.id AND i.tenant_id=r.tenant_id WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status IN ('PUBLISHED','FINISHED')"""),
        FlowComponent("EXAM_INCIDENT", "考试事件", _count("t_aa_exam_incident")),
    ),
    "AA-013": (
        FlowComponent("DEFERRED", "缓考已审批", _count("t_aa_deferred_exam", "status='APPROVED'")),
        FlowComponent("MAKEUP", "补考成绩完成", """SELECT COUNT(*) FROM t_acad_makeup m JOIN t_aa_makeup_batch b ON b.id=m.batch_id AND b.tenant_id=m.tenant_id WHERE m.tenant_id=:tenant_id AND m.is_deleted=0 AND m.status='FINISHED' AND b.status='FINISHED'"""),
        FlowComponent("RETAKE", "重修已编班", _count("t_aa_retake_apply", "status='ENROLLED' AND teaching_task_ref IS NOT NULL")),
        FlowComponent("EXEMPTION", "免修审批终态", _count("t_aa_exemption", "status IN ('APPROVED','REJECTED')")),
    ),
    "AA-014": (
        FlowComponent("GRADE_PUBLISHED", "成绩任务发布到正式成绩", """SELECT COUNT(*) FROM t_aa_grade_task t JOIN t_aa_grade_record r ON r.task_id=t.id AND r.tenant_id=t.tenant_id JOIN t_acad_grade g ON g.id=r.acad_grade_id AND g.tenant_id=r.tenant_id WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND t.status='PUBLISHED' AND r.is_deleted=0 AND g.is_deleted=0 AND g.record_status='ACTIVE'"""),
        FlowComponent("GRADE_SCHEME", "成绩方案锁定", _count("t_aa_grade_scheme_snapshot", "status='LOCKED'")),
    ),
    "AA-015": (
        FlowComponent("GRADE_CORRECTION", "成绩更正形成追加事实", """SELECT COUNT(*) FROM t_aa_grade_change_request q JOIN t_aa_grade_correction c ON c.source_type='CHANGE_REQUEST' AND c.source_ref_id=q.id AND c.tenant_id=q.tenant_id WHERE q.tenant_id=:tenant_id AND q.is_deleted=0 AND q.status='APPROVED' AND c.is_deleted=0 AND c.status='ACTIVE'"""),
        FlowComponent("GRADE_RECHECK", "成绩复查终态", _count("t_aa_grade_recheck", "status IN ('UPHELD','ADJUSTED','REJECTED')")),
        FlowComponent("GRADE_RECOGNITION", "成绩认定终态", _count("t_aa_grade_recognition", "status IN ('APPROVED','REJECTED')")),
    ),
    "AA-016": (
        FlowComponent("WARNING_CLOSED", "预警跟进关闭", """SELECT COUNT(*) FROM t_acad_warning w JOIN t_acad_intervention i ON i.warning_id=w.id AND i.tenant_id=w.tenant_id WHERE w.tenant_id=:tenant_id AND w.is_deleted=0 AND w.status='CLOSED' AND i.is_deleted=0 AND i.status='CLOSED'"""),
        FlowComponent("WARNING_PENDING", "待处理预警", _count("t_acad_warning", "status='PENDING_HANDLE'")),
    ),
    "AA-017": (
        FlowComponent("TEXTBOOK_CHAIN", "教材选用到发放费用", """SELECT COUNT(*) FROM t_aa_textbook_distribution_record d JOIN t_aa_textbook_fee_ledger f ON f.distribution_record_id=d.id AND f.tenant_id=d.tenant_id JOIN t_aa_textbook t ON t.id=d.textbook_id AND t.tenant_id=d.tenant_id WHERE d.tenant_id=:tenant_id AND d.is_deleted=0 AND d.status='RECEIVED' AND f.is_deleted=0 AND f.status='PAID' AND t.is_deleted=0"""),
        FlowComponent("TEXTBOOK_ORDER", "教材审核征订到货", """SELECT COUNT(*) FROM t_aa_textbook_order_batch b JOIN t_aa_textbook_order_item i ON i.order_batch_id=b.id AND i.tenant_id=b.tenant_id WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status IN ('PARTIALLY_ARRIVED','ARRIVED','ARCHIVED') AND i.is_deleted=0 AND i.arrived_qty>0"""),
    ),
    "AA-018": (
        FlowComponent("CLASSROOM_BOOKING", "教室预约通过", _count("t_aa_classroom_booking", "status='APPROVED'")),
        FlowComponent("LAB_BOOKING", "实训室预约通过", _count("t_aa_lab_booking", "status='APPROVED'")),
        FlowComponent("RESOURCE_REPAIR", "资源维修闭环", _count("t_aa_resource_repair", "status='DONE'")),
    ),
    "AA-019": (
        FlowComponent("EVALUATION_SUBMITTED", "匿名评教提交并汇总", """SELECT COUNT(*) FROM t_aa_evaluation_task t JOIN t_aa_evaluation_record r ON r.task_id=t.id AND r.tenant_id=t.tenant_id JOIN t_aa_evaluation_result s ON s.batch_id=t.batch_id AND s.teaching_task_id=t.teaching_task_id AND s.tenant_id=t.tenant_id WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND t.status='SUBMITTED' AND r.is_deleted=0 AND s.is_deleted=0 AND s.student_count>0"""),
        FlowComponent("EVALUATION_APPEAL", "评教申诉复核", _count("t_aa_evaluation_appeal", "status='RESOLVED'")),
    ),
    "AA-020": (
        FlowComponent("QUALITY_CLOSED", "质量问题整改复查关闭", """SELECT COUNT(*) FROM t_aa_quality_record q JOIN t_aa_quality_rectification r ON r.source_record_id=q.id AND r.tenant_id=q.tenant_id WHERE q.tenant_id=:tenant_id AND q.is_deleted=0 AND q.status IN ('CONFIRMED','CLOSED') AND r.is_deleted=0 AND r.status='CLOSED'"""),
        FlowComponent("QUALITY_ACTIVE", "在办质量整改", _count("t_aa_quality_rectification", "status IN ('SUBMITTED','IN_PROGRESS')")),
    ),
    "AA-021": (
        FlowComponent("GRAD_DELAYED", "毕业审核延期案例", _count("t_aa_graduation_audit_result", "status='DELAYED'")),
        FlowComponent("GRAD_PASSED", "毕业审核通过决定", """SELECT COUNT(*) FROM t_aa_graduation_audit_result r JOIN t_aa_graduation_decision_fact d ON d.result_id=r.id AND d.tenant_id=r.tenant_id WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND r.status IN ('PASSED','GRADUATED') AND d.conclusion IN ('PASSED','GRADUATED')"""),
        FlowComponent("CERT_ISSUED", "毕业证书签发", _count("t_aa_graduation_certificate", "status='ISSUED'")),
    ),
    "AA-022": (
        FlowComponent("ARCHIVE_MANIFEST", "归档及不可变清单", """SELECT COUNT(*) FROM t_aa_archive_batch b JOIN t_aa_archive_manifest m ON m.archive_batch_id=b.id AND m.tenant_id=b.tenant_id WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status='ARCHIVED'"""),
        FlowComponent("ARCHIVE_CORRECTION", "归档后纠错通过与拒绝", """SELECT COUNT(*) FROM (SELECT archive_batch_id FROM t_aa_post_archive_correction_case WHERE tenant_id=:tenant_id AND is_deleted=0 GROUP BY archive_batch_id HAVING SUM(status='APPLIED')>0 AND SUM(status='REJECTED')>0) x"""),
    ),
    "AA-023": (
        FlowComponent("STATS_FROZEN", "统计快照冻结", _count("t_aa_stats_snapshot", "status='FROZEN'")),
        FlowComponent("WORKLOAD_APPROVED", "教师工作量审核", _count("t_aa_workload_declaration", "status='APPROVED'")),
    ),
    "AA-024": (
        FlowComponent("ACADEMIC_IMPORT", "教务导入确认", _count("t_import_job", "module_code='ACADEMIC_AFFAIRS' AND status='SUCCEEDED'")),
        FlowComponent("IMPORT_ERROR", "教务导入错误行", """SELECT COUNT(*) FROM t_import_row_error e JOIN t_import_job j ON j.id=e.import_job_id AND j.tenant_id=e.tenant_id WHERE e.tenant_id=:tenant_id AND e.is_deleted=0 AND j.module_code='ACADEMIC_AFFAIRS'"""),
        FlowComponent("ACADEMIC_EXPORT", "教务导出文件", """SELECT COUNT(*) FROM t_export_job e JOIN t_file_object f ON f.id=e.file_object_id AND f.tenant_id=e.tenant_id WHERE e.tenant_id=:tenant_id AND e.is_deleted=0 AND e.module_code='ACADEMIC_AFFAIRS' AND e.status='SUCCEEDED' AND f.is_deleted=0 AND f.status='AVAILABLE'"""),
    ),
}


def audit_academic_flow_coverage(db, tenant_id: int) -> dict:
    flows = []
    for flow_code, components in FLOWS.items():
        evidence = []
        for component in components:
            count = int(db.execute(text(component.sql), {"tenant_id": tenant_id}).scalar() or 0)
            evidence.append({
                "code": component.code,
                "title": component.title,
                "count": count,
                "passed": count > 0,
            })
        flows.append({
            "flowCode": flow_code,
            "passed": all(item["passed"] for item in evidence),
            "components": evidence,
        })
    failed = [flow for flow in flows if not flow["passed"]]
    return {
        "tenantId": str(tenant_id),
        "summary": {
            "flows": len(flows),
            "passed": len(flows) - len(failed),
            "failed": len(failed),
            "fullCoveragePassed": not failed,
        },
        "flows": flows,
        "failures": failed,
    }
