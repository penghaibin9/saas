"""Single-application history projection, called only after the owning detail scope check."""
from datetime import timedelta

from sqlalchemy import select

from app.services.db_service import _iso, _tid


def publicity_window(row, batch, *, now=None):
    """Read and command paths use the same recorded batch duration and UTC boundary."""
    from app.core.timeutil import utc_now_naive
    end = (row.publicity_at + timedelta(days=max(1, int(batch.publicity_days if batch.publicity_days is not None else 5)))) if row.publicity_at and batch else None
    ready = bool(row.status == 'PUBLICITY' and end and end <= (now or utc_now_naive()))
    hint = ''
    if row.status == 'PUBLICITY':
        hint = ('公示期限信息不完整，请核对认定批次' if not end else
                '公示期已满，完成异议复核后可确认认定结果' if ready else
                '公示期尚未结束，到期后刷新进度再确认')
    return {'publicityEnd': _iso(end), 'publicityReady': ready, 'publicityHint': hint}

EVENTS = {
    'APPLY': '提交认定申请', 'REVIEW_STEP': '评审通过', 'TO_PUBLICITY': '学校终审通过，进入公示',
    'RETURNED': '退回补正', 'REJECTED': '认定未通过', 'RESUBMIT': '重新提交',
    'STUDENT_RESUBMIT': '补正后重新提交', 'STUDENT_EDIT_RETURNED': '保存补正内容',
    'APPROVED': '完成困难认定', 'ADJUST_SUBMIT': '发起等级调整',
    'ADJUST_APPROVED': '等级调整通过', 'ADJUST_REJECTED': '等级调整未通过',
    'AID_OBJECTION_SUBMIT': '公示异议进入复核', 'AID_OBJECTION_REVIEW': '公示异议复核完成',
}


def detail_context(db, row, *, student_view=False):
    from app.models import AidBatch, AffairsAuditTrail
    from app.services.affairs_aid_service import AID_NODES, LEVELS, L_AID, _L_OBJ_RESULT

    batch = db.scalar(select(AidBatch).where(AidBatch.id == row.batch_id,
        AidBatch.tenant_id == _tid(), AidBatch.is_deleted.is_(False)))
    trails = db.scalars(select(AffairsAuditTrail).where(
        AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == 'AID',
        AffairsAuditTrail.biz_id == row.id, AffairsAuditTrail.action.in_(EVENTS),
    ).order_by(AffairsAuditTrail.occurred_at, AffairsAuditTrail.id)).all()
    history = []
    for event in trails:
        title, description = EVENTS[event.action], ''
        raw = event.detail or ''
        if event.action == 'REVIEW_STEP':
            parts = raw.split('->')
            if len(parts) == 2 and all(part in AID_NODES for part in parts):
                title = f'{L_AID[parts[0]]}通过'
                description = f'进入{L_AID[parts[1]]}'
        elif event.action in {'RETURNED', 'REJECTED', 'ADJUST_REJECTED'}:
            description = raw  # Already delivered to this student by the canonical result notice.
        elif event.action in {'TO_PUBLICITY', 'APPROVED'}:
            level = raw.removeprefix('final=')
            if level in LEVELS:
                description = ('拟认定等级：' if event.action == 'TO_PUBLICITY' else '认定等级：') + LEVELS[level]
        elif event.action == 'ADJUST_APPROVED':
            parts = raw.split('->')
            if len(parts) == 2 and all(part in LEVELS for part in parts):
                description = f'{LEVELS[parts[0]]} → {LEVELS[parts[1]]}'
        elif event.action == 'AID_OBJECTION_REVIEW':
            description = _L_OBJ_RESULT.get(raw, '')
        item = {'id': str(event.id), 'title': title, 'description': description, 'occurredAt': _iso(event.occurred_at)}
        if not student_view:
            item['operator'] = event.operator or '系统'
        history.append(item)
    return {
        'adjustment': ({
            'fromLevel': row.final_level, 'fromLabel': LEVELS.get(row.final_level, '等级待确认'),
            'targetLevel': row.suggest_level, 'targetLabel': LEVELS.get(row.suggest_level, '等级待确认'),
            **({'reason': next((event.detail.split(': ', 1)[1] for event in reversed(trails)
                if event.action == 'ADJUST_SUBMIT' and ': ' in (event.detail or '')), '')} if not student_view else {}),
        } if row.status == 'ADJUST_REVIEW' else None),
        'history': history, 'batchName': batch.batch_name if batch else '历史认定批次',
        'schoolYear': batch.year_code if batch else '', 'createdAt': _iso(row.created_at),
        'publicityAt': _iso(row.publicity_at), 'resultAt': _iso(row.result_at),
        **publicity_window(row, batch),
    }
