"""School volunteer results use the same transaction and durable inbox as position notices."""
from sqlalchemy import select

from app.models import InternshipApplication, StudentAccountLink
from app.modules.internship.services.internship_position_notification_service import _recipient_refs
from app.services.message_action_registry import validate_action
from app.services.message_event_outbox_service import emit_message_event


def emit_school_result_in_tx(db, *, group, record, selected_application_id=None):
    approved = group.status == 'APPROVED'
    title = '实习岗位已确认' if approved else '岗位志愿已退回修订'
    event_code = 'INTERNSHIP.VOLUNTEER.SCHOOL_RESULT'
    prefix = f'VOLUNTEER_RESULT:{group.id}:v{int(group.version or 0)}'
    outbox_ids = []

    def emit(recipients, content, suffix, action_key=None, params=None):
        if not recipients:
            return
        key, cleaned = validate_action(action_key, params)
        event = emit_message_event(db, event_code=event_code, source_module='internship',
            source_biz_type='INTERNSHIP_VOLUNTEER_GROUP', source_biz_id=group.id,
            recipient_refs=recipients, title=title, content=content,
            action_key=key, action_params=cleaned, dedup_key=f'{prefix}:{suffix}')
        outbox_ids.append(int(event.id))

    student_user_id = db.scalar(select(StudentAccountLink.user_id).where(
        StudentAccountLink.tenant_id == group.tenant_id, StudentAccountLink.student_id == group.student_id,
        StudentAccountLink.link_status == 'ACTIVE', StudentAccountLink.is_deleted.is_(False)))
    if student_user_id:
        content = (f'学校已确认你的岗位：{record.enterprise_name} · {record.position_name}。'
                   '请继续办理协议、保险和上岗核验；岗位确认不等于已经可以上岗。') if approved else (
                   f'学校已退回你第 {group.submission_version} 次投递的志愿。补正意见：{group.revision_reason or "请核对学校意见"}。'
                   '请在实习选岗中核对当前招聘季，修改后重新提交。')
        emit([{'userId':int(student_user_id),'receiverType':'STUDENT'}],content,'STUDENT',
            'student.internship.volunteer-result', {'groupId':str(group.id),'groupVersion':str(int(group.version or 0))})

    from app.models import InternshipPosition
    applications = db.execute(select(InternshipApplication, InternshipPosition.company_id).join(
        InternshipPosition, InternshipPosition.id == InternshipApplication.position_id,
    ).where(InternshipApplication.tenant_id == group.tenant_id,
        InternshipApplication.record_id == group.record_id, InternshipApplication.student_id == group.student_id,
        InternshipApplication.batch_id == group.batch_id, InternshipApplication.campaign_id == group.campaign_id,
        InternshipApplication.material_snapshot_id == group.current_material_snapshot_id,
        InternshipApplication.is_deleted.is_(False), InternshipPosition.tenant_id == group.tenant_id,
        InternshipPosition.campaign_id == group.campaign_id,
    ).order_by(InternshipApplication.id))
    for application, company_id in applications:
        recipients = _recipient_refs(db,tenant_id=group.tenant_id,company_id=company_id,campaign_id=group.campaign_id)
        if approved:
            content = '学校已确认本岗位申请，请查看学生申请及后续安排。' if application.id == selected_application_id else (
                '学校已确认该学生的其他志愿，本岗位申请已关闭；本企业此前处理意见作为历史保留。')
        else:
            content = '学校已退回该学生的本次投递；本企业基于旧投递的处理意见已失效，请等待学生重新提交。'
        # Never disclose another company's selected position or the student's private correction reason.
        emit(recipients,content,f'APP:{application.id}','enterprise.internship.application',
            {'applicationId':str(application.id),'campaignId':str(group.campaign_id)})
    return outbox_ids
