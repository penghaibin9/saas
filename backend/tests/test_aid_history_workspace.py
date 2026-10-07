"""Actual application lifecycle history; no batch/audit/private metadata leaks."""
import json
from datetime import datetime

from test_affairs_aid import BASE, TID, _seed, _hdr, _open_batch, _apply, _review, _expire_publicity
from test_affairs_four_end_hardening import _set_ctx, _clear_ctx


def test_four_client_history_tracks_return_resubmit_publicity_and_result(client, db_mode):
    from app.api.v1.affairs_student_returned import aid_detail
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail
    from app.services import affairs_aid_service as aid

    ids = _seed(db_mode); headers = _hdr(client, 'school_admin01')
    batch = _open_batch(client, headers)
    item = _apply(client, headers, batch, ids['sa']).json()['data']
    apply_id = int(item['applyId'])
    item = _review(client, headers, item, action='RETURN', reason='请补充家庭收入变动说明')
    item = client.post(f'{BASE}/aid/applications/{apply_id}/resubmit', headers=headers,
        json={'version': item['version']}).json()['data']
    for _ in range(4): item = _review(client, headers, item)
    pending = client.get(f'{BASE}/aid/applications/{apply_id}', headers=headers).json()['data']
    assert pending['publicityEnd'] and pending['resultAt'] is None
    _expire_publicity(apply_id)
    response = client.post(f'{BASE}/aid/applications/{apply_id}/publicity-confirm', headers=headers,
        json={'version': item['version']})
    assert response.status_code == 200, response.text
    with get_sessionmaker()() as db:
        for tid, bid, namespace, action in [
            (TID, apply_id, 'AID_BATCH', 'APPLY'), (TID, apply_id, 'AID', 'BATCH_CREATE'),
            (TID, apply_id + 99, 'AID', 'RETURNED'), (TID + 99, apply_id, 'AID', 'RETURNED'),
            (TID, apply_id, 'AID', 'STUDENT_VIEW_DETAIL'),
        ]:
            db.add(AffairsAuditTrail(tenant_id=tid, biz_id=bid, biz_type=namespace, action=action,
                detail='PRIVATE_SENTINEL', occurred_at=datetime.utcnow()))
        db.commit()
    staff = client.get(f'{BASE}/aid/applications/{apply_id}', headers=headers).json()['data']
    titles = [x['title'] for x in staff['history']]
    assert titles == ['提交认定申请', '退回补正', '重新提交', '班级评议通过', '辅导员初审通过',
        '学院复审通过', '学校终审通过，进入公示', '完成困难认定']
    assert all(x['occurredAt'] for x in staff['history'])
    assert staff['history'][1]['description'] == '请补充家庭收入变动说明'
    assert staff['history'][-1]['description'] == '认定等级：困难'
    assert staff['resultAt']
    user = {'userId': 'u-A001', 'studentNo': 'A001', 'realName': '甲一',
        'userType': 'STUDENT', 'currentRoleCode': 'STUDENT', 'tenantId': str(TID)}
    _set_ctx(user)
    try:
        student = aid_detail(apply_id, user)['data']
        assert student['history'] == [{k: v for k, v in x.items() if k != 'operator'} for x in staff['history']]
        serialized = json.dumps(student['history'], ensure_ascii=False)
        assert 'PRIVATE_SENTINEL' not in serialized and 'confirmation=' not in serialized
        assert 'operator' not in serialized and 'role_name' not in serialized
        # Teacher mobile consumes the same get_application projection; list responses remain small.
        rows, _, _ = aid.list_applications(user, student_id=ids['sa'])
        assert all('history' not in row for row in rows)
    finally:
        _clear_ctx()
