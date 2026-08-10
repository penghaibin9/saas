"""init core tables — 全新安装的表基线

Revision ID: 0001_init_core_tables
Revises:
Create Date: 2026-07-04

────────────────────────────────────────────────────────────────────────────
2026-08-10 修复：不再抢建"后续迁移有正式建表脚本"的表
────────────────────────────────────────────────────────────────────────────
原实现直接 `metadata.create_all()` 把**当天 ORM 里的全部表**一次建光。后果是：

- 全新安装：0001 先按 ORM 建出 200 多张表（ORM 只有客户端 default，落库没有
  server_default，索引也按 ORM 定义），后面那些正式建表迁移一看"表已存在"就
  整段 return，它们里面写好的 `server_default` 和 `(tenant_id, xxx)` 复合索引
  **一次都没执行**；
- 老库升级：这些表当年由正式建表迁移创建，DDL 是对的。

于是老学校和新学校跑在不同结构上。实测 427 张表里 245 张不一致、3583 处差异，
例如 `t_aa_archive_batch.status` 老库有 `DEFAULT 'DRAFT'`、新库没有；索引老库是
`(tenant_id, status)`、新库退化成 `(status)`。**新装的学校拿到的才是坏结构。**

修法：0001 只负责那些"全仓没有任何正式建表脚本、只能由 ORM 生成"的表；
下面 `TABLES_OWNED_BY_LATER_MIGRATIONS` 里的表一律留给它们各自的迁移去建。

这份清单是**冻结**的，按 2026-08-10 的迁移链一次性生成，不要改成运行时扫描——
运行时扫描等于把"时间旅行"换个地方重演。新增表时：
- 有正式 op.create_table 迁移 → 加进本清单；
- 纯 ORM 表 → 不用动（0001 会建）。
门禁：scripts/check/check-migration-time-travel.py 与 CI「迁移升级路径收敛门禁」。
"""
from __future__ import annotations

from alembic import op

revision = "0001_init_core_tables"
down_revision = None
branch_labels = None
depends_on = None


# 由后续迁移的正式建表脚本负责的表（冻结于 2026-08-10，共 291 张）
TABLES_OWNED_BY_LATER_MIGRATIONS = {
    "t_aa_archive_batch", "t_aa_archive_item", "t_aa_attendance_session",
    "t_aa_class_adjustment_request", "t_aa_class_time_band", "t_aa_classroom",
    "t_aa_classroom_booking", "t_aa_course_material", "t_aa_deferred_exam",
    "t_aa_effective_grade_policy", "t_aa_effective_grade_policy_bypass",
    "t_aa_effective_grade_policy_snapshot", "t_aa_equipment", "t_aa_evaluation_appeal",
    "t_aa_evaluation_batch", "t_aa_evaluation_record", "t_aa_evaluation_result",
    "t_aa_evaluation_task", "t_aa_exam_audit_trail", "t_aa_exam_batch", "t_aa_exam_course",
    "t_aa_exam_incident", "t_aa_exam_invigilator", "t_aa_exam_patrol", "t_aa_exam_room",
    "t_aa_exam_room_student", "t_aa_exam_teacher_lock", "t_aa_exemption",
    "t_aa_gpa_point_policy", "t_aa_grade_change_request", "t_aa_grade_component_score",
    "t_aa_grade_correction", "t_aa_grade_identity_head", "t_aa_grade_recheck",
    "t_aa_grade_recognition", "t_aa_grade_scheme_snapshot", "t_aa_graduation_certificate",
    "t_aa_lab_booking", "t_aa_lab_resource", "t_aa_level_exam", "t_aa_level_exam_reg",
    "t_aa_major_direction", "t_aa_major_split_batch", "t_aa_major_split_option",
    "t_aa_major_split_volunteer", "t_aa_makeup_batch", "t_aa_post_archive_correction_case",
    "t_aa_program_graduation_requirement", "t_aa_program_practice_segment",
    "t_aa_program_transition_assessment", "t_aa_quality_record", "t_aa_quality_rectification",
    "t_aa_registration_deferral", "t_aa_registration_exception", "t_aa_resource_repair",
    "t_aa_retake_apply", "t_aa_roster_consumer_snapshot", "t_aa_schedule_change",
    "t_aa_schedule_publish", "t_aa_schedule_rule", "t_aa_schedule_scope_head",
    "t_aa_selection_batch", "t_aa_selection_course", "t_aa_selection_record",
    "t_aa_selection_round", "t_aa_semester_pilot", "t_aa_semester_pilot_checkpoint",
    "t_aa_stats_snapshot", "t_aa_student_academic_fact", "t_aa_student_correction",
    "t_aa_teacher_availability", "t_aa_teaching_class", "t_aa_teaching_class_member",
    "t_aa_teaching_class_roster_version", "t_aa_teaching_class_teacher", "t_aa_textbook",
    "t_aa_textbook_distribution_batch", "t_aa_textbook_distribution_record",
    "t_aa_textbook_fee_ledger", "t_aa_textbook_order_batch", "t_aa_textbook_order_item",
    "t_aa_textbook_review_batch", "t_aa_textbook_review_batch_item",
    "t_aa_textbook_selection", "t_aa_workload_declaration", "t_academic_calendar_governance",
    "t_access_decision_trace", "t_access_review_campaign", "t_access_review_item",
    "t_affairs_activity", "t_affairs_activity_credit", "t_affairs_activity_signup",
    "t_affairs_aid_objection", "t_affairs_attachment", "t_affairs_audit_trail",
    "t_affairs_batch_job", "t_affairs_batch_job_item", "t_affairs_class_cadre",
    "t_affairs_class_material", "t_affairs_club", "t_affairs_club_annual_review",
    "t_affairs_club_member", "t_affairs_counselor_assessment",
    "t_affairs_counselor_assessment_period", "t_affairs_counselor_assignment",
    "t_affairs_counselor_eval", "t_affairs_counselor_eval_indicator",
    "t_affairs_credit_appeal", "t_affairs_credit_category", "t_affairs_discipline_appeal",
    "t_affairs_discipline_decision_version", "t_affairs_discipline_subflow_lock",
    "t_affairs_fee_reduction", "t_affairs_funding_appeal", "t_affairs_funding_disbursement",
    "t_affairs_league_dev", "t_affairs_league_dev_stage", "t_affairs_leave_cancel_record",
    "t_affairs_leave_extension", "t_affairs_material_requirement",
    "t_affairs_material_submission", "t_affairs_org_position", "t_affairs_psy_referral",
    "t_affairs_psy_survey_submission", "t_affairs_repair_job", "t_affairs_student_loan",
    "t_affairs_student_org", "t_affairs_volunteer_record", "t_affairs_work_study_monthly",
    "t_affairs_work_study_post", "t_affairs_work_study_record", "t_archive_manifest",
    "t_archive_manifest_item", "t_audit_outbox", "t_backup_evidence",
    "t_calendar_transition_event", "t_calendar_window", "t_change_execution",
    "t_change_impact", "t_change_request", "t_config_activation", "t_config_definition",
    "t_config_override", "t_custom_role_source", "t_data_center_report",
    "t_data_center_report_version", "t_data_domain", "t_data_owner", "t_data_quality_issue",
    "t_data_quality_rule", "t_data_scope_rule", "t_emergency_access_session",
    "t_excel_import_job", "t_export_job", "t_feedback", "t_file_asset", "t_file_binding",
    "t_file_job", "t_file_retention_policy", "t_file_scan_record",
    "t_file_storage_quota_reservation", "t_file_upload_session", "t_file_version",
    "t_gd_archive_record", "t_gd_audit_trail", "t_gd_batch", "t_gd_defense_delay",
    "t_gd_defense_group", "t_gd_defense_score", "t_gd_excellent_outcome", "t_gd_final",
    "t_gd_grade", "t_gd_guidance", "t_gd_material_backfill_checkpoint", "t_gd_material_item",
    "t_gd_material_rule", "t_gd_mentor", "t_gd_mentor_assignment", "t_gd_midterm",
    "t_gd_plagiarism", "t_gd_proposal", "t_gd_review", "t_gd_risk_case", "t_gd_student",
    "t_gd_student_material", "t_gd_task_book", "t_gd_template_asset_policy", "t_gd_topic",
    "t_gd_topic_change_request", "t_gd_topic_choice", "t_gd_topic_round",
    "t_idempotency_record", "t_identity_import_batch", "t_import_job", "t_import_row_error",
    "t_incident", "t_incident_tenant", "t_incident_update", "t_internship_agreement",
    "t_internship_agreement_template", "t_internship_application", "t_internship_archive",
    "t_internship_batch_participant", "t_internship_batch_plan",
    "t_internship_batch_scope_rule", "t_internship_change_request",
    "t_internship_communication_log", "t_internship_complaint",
    "t_internship_enterprise_eval", "t_internship_final_score", "t_internship_guidance",
    "t_internship_insurance", "t_internship_intention", "t_internship_leave",
    "t_internship_makeup", "t_internship_match", "t_internship_plan_ack",
    "t_internship_plan_task_progress", "t_internship_process_report",
    "t_internship_score_config", "t_internship_student_eval", "t_internship_visit",
    "t_internship_visit_plan", "t_maintenance_window", "t_master_merge_event", "t_menu_node",
    "t_message_attachment", "t_message_audience", "t_message_campaign",
    "t_message_delivery_job", "t_message_event_outbox", "t_national_major_catalog",
    "t_national_standard_document", "t_national_standard_section",
    "t_national_standard_source", "t_notification_preference", "t_org_version",
    "t_org_version_item", "t_password_reset_sms_job", "t_permission_bundle",
    "t_permission_bundle_item", "t_platform_service", "t_portal_login_otp",
    "t_portal_sign_record", "t_problem", "t_problem_postmortem", "t_provisioning_job",
    "t_provisioning_step_run", "t_renewal_task", "t_restore_drill",
    "t_role_assignment_validity", "t_role_template", "t_role_workbench_config",
    "t_sandbox_baseline", "t_school_major_standard_binding", "t_scope_policy_decision_log",
    "t_scope_policy_target", "t_security_activation", "t_security_change_item",
    "t_security_change_set", "t_service_dependency", "t_service_tenant_usage",
    "t_shared_import_batch", "t_sod_rule", "t_sod_violation", "t_staff_assignment",
    "t_student_account_link", "t_student_parent_link", "t_support_ticket", "t_sys_config",
    "t_system_business_relation_batch", "t_system_business_relation_install_item",
    "t_system_implementation_check", "t_system_implementation_project",
    "t_system_implementation_section", "t_system_json_doc", "t_system_preset_installation",
    "t_tenant_capability_setting", "t_tenant_fair_use_limit", "t_tenant_fair_use_violation",
    "t_tenant_portal_config", "t_tenant_storage_quota", "t_tenant_usage_snapshot",
    "t_training_record", "t_user_preference", "t_wildcard_retirement",
    "t_workflow_action_policy", "t_workflow_definition", "t_workflow_node_definition",
    "t_workflow_version_migration_event", "t_wx_account_binding",
}


def _tables_for_baseline(metadata):
    """0001 该建的表：ORM 全集减去"归后续迁移所有"的那批。"""
    return [
        table for table in metadata.sorted_tables
        if table.name not in TABLES_OWNED_BY_LATER_MIGRATIONS
    ]


def upgrade() -> None:
    from app.db.base import metadata
    bind = op.get_bind()
    metadata.create_all(bind=bind, tables=_tables_for_baseline(metadata), checkfirst=True)


def downgrade() -> None:
    from app.db.base import metadata
    bind = op.get_bind()
    metadata.drop_all(bind=bind, tables=_tables_for_baseline(metadata), checkfirst=True)
