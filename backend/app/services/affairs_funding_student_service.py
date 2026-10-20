"""Applicant-only funding result; never expose staff snapshots or third-party appeals."""
from datetime import timedelta

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import _iso, _tid, session

EVENTS = {
    'APPLY': '提交奖助申请', 'REVIEW_STEP': '评审通过', 'TO_PUBLICITY': '进入公示',
    'RETURNED': '退回补正', 'REJECTED': '申请未通过', 'GRANTED': '确认获资助',
    'STUDENT_EDIT_RETURNED': '保存补正内容', 'STUDENT_RESUBMIT': '补正后重新提交',
    'FUNDING_APPEAL_SUBMIT': '公示申诉进入复核', 'FUNDING_APPEAL_REVIEW': '公示申诉复核完成',
}


def message_application_params(action_key, params):
    """Old appeal messages used the appeal ID; navigation must target its application."""
    if action_key != 'AFFAIRS_FUNDING' or str((params or {}).get('bizType') or '').upper() != 'FUNDING_APPEAL':
        return params
    from app.models import FundingAppeal, FundingApplication
    raw = str(params.get('recordId') or '')
    if not raw.isdigit():
        raise not_found('申诉关联的申请不可查看')
    with session() as db:
        application_id = db.scalar(select(FundingApplication.id).join(FundingAppeal,
            FundingAppeal.application_id == FundingApplication.id).where(
            FundingAppeal.id == int(raw), FundingAppeal.tenant_id == _tid(),
            FundingAppeal.is_deleted.is_(False), FundingApplication.tenant_id == _tid(),
            FundingApplication.is_deleted.is_(False), FundingApplication.student_id == FundingAppeal.student_id))
        if application_id is None:
            raise not_found('申诉关联的申请不可查看')
        return {**params, 'bizType': 'FUNDING', 'recordId': str(application_id)}


def detail(user, application_id):
    from app.models import (FundingApplication, FundingBatch, FundingProject, FundingAppeal,
                            FundingDisbursement, AffairsAuditTrail)
    from app.services.mobile_affairs_service import _me
    from app.services.affairs_funding_service import L_FUND, FUND_NODES, _L_APPEAL, _L_APPEAL_RESULT, _L_BANK

    with session() as db:
        student = _me(db, user)
        if not str(application_id).isdigit():
            raise not_found('申请不存在或不可查看')
        row = db.scalar(select(FundingApplication).where(
            FundingApplication.id == int(application_id), FundingApplication.tenant_id == _tid(),
            FundingApplication.student_id == student.id, FundingApplication.is_deleted.is_(False)))
        if not row:
            raise not_found('申请不存在或不可查看')
        batch = db.scalar(select(FundingBatch).where(FundingBatch.id == row.batch_id,
            FundingBatch.tenant_id == _tid(), FundingBatch.is_deleted.is_(False)))
        project = db.scalar(select(FundingProject).where(FundingProject.id == batch.project_id,
            FundingProject.tenant_id == _tid(), FundingProject.is_deleted.is_(False))) if batch else None
        appeals = db.scalars(select(FundingAppeal).where(FundingAppeal.tenant_id == _tid(),
            FundingAppeal.application_id == row.id, FundingAppeal.student_id == student.id,
            FundingAppeal.is_deleted.is_(False)).order_by(FundingAppeal.id.desc())).all()
        pending = any(item.status == 'SUBMITTED' for item in appeals)
        payments = db.scalars(select(FundingDisbursement).where(FundingDisbursement.tenant_id == _tid(),
            FundingDisbursement.application_id == row.id, FundingDisbursement.student_id == student.id,
            FundingDisbursement.is_deleted.is_(False)).order_by(FundingDisbursement.id.desc())).all()
        trails = db.scalars(select(AffairsAuditTrail).where(AffairsAuditTrail.tenant_id == _tid(),
            AffairsAuditTrail.biz_type == 'FUNDING', AffairsAuditTrail.biz_id == row.id,
            AffairsAuditTrail.action.in_(EVENTS)).order_by(AffairsAuditTrail.occurred_at, AffairsAuditTrail.id)).all()
        history = []
        for event in trails:
            title, description = EVENTS[event.action], ''
            if event.action == 'REVIEW_STEP':
                nodes = (event.detail or '').split('->')
                if len(nodes) == 2 and all(node in FUND_NODES for node in nodes):
                    title = f'{L_FUND[nodes[0]]}通过'; description = f'进入{L_FUND[nodes[1]]}'
            elif event.action in {'RETURNED', 'REJECTED'}:
                description = event.detail or ''
            elif event.action == 'FUNDING_APPEAL_REVIEW':
                description = _L_APPEAL_RESULT.get(event.detail, '')
            history.append({'id': str(event.id), 'title': title, 'description': description, 'occurredAt': _iso(event.occurred_at)})
        days = batch.publicity_days if batch and batch.publicity_days is not None else 5
        end = row.publicity_at + timedelta(days=max(1, days)) if row.publicity_at else None
        hints = {
            'RETURNED': '请按处理意见补充申请，修改后重新提交。',
            'PUBLICITY': '申诉正在复核，学校完成复核后再确认结果。' if pending else '申请正在公示，公示期满并完成申诉复核后由学校确认结果。',
            'GRANTED': '已获得资助资格，请在下方查看学校登记的发放进度。',
            'REJECTED': '本次申请未通过，请查看处理意见和复核结果。',
            'CANCELLED': '本次申请已取消。', 'ARCHIVED': '本次申请已归档，记录可继续查看。',
        }
        money = lambda value: format(value, '.2f') if value is not None else None
        return {
            'applicationId': str(row.id), 'batchId': str(row.batch_id), 'projectType': row.project_type,
            'projectName': project.project_name if project else '历史资助项目', 'schoolYear': batch.year_code if batch else '',
            'status': row.status, 'statusLabel': L_FUND.get(row.status, '状态待确认'),
            'version': row.version, 'statement': row.statement or '', 'returnReason': row.return_reason or '',
            'requestedAmount': money(row.requested_amount), 'approvedAmount': money(row.approved_amount),
            'createdAt': _iso(row.created_at), 'publicityEnd': _iso(end), 'resultAt': _iso(row.result_at),
            'hasPendingAppeal': pending, 'progressHint': hints.get(row.status, '申请已提交，请等待负责当前节点的老师评审。'),
            'allowedActions': (['EDIT_RETURNED', 'RESUBMIT'] if row.status == 'RETURNED' else
                               ['SUBMIT_APPEAL'] if row.status == 'PUBLICITY' and not pending else []),
            'appealResults': [{'appealId': str(item.id), 'statusLabel': _L_APPEAL.get(item.status, '状态待确认'),
                'resultLabel': _L_APPEAL_RESULT.get(item.result, ''), 'reviewOpinion': item.review_opinion or '' if item.status == 'CLOSED' else '',
                'reviewedAt': _iso(item.reviewed_at)} for item in appeals],
            'disbursements': [{'disbursementId': str(item.id), 'status': item.bank_status,
                'statusLabel': _L_BANK.get(item.bank_status, '状态待确认'), 'amount': money(item.amount),
                'issuedAt': _iso(item.issued_at), 'failReason': item.fail_reason or '' if item.bank_status in {'FAILED', 'RETURNED'} else ''}
                for item in payments],
            'history': history,
        }
