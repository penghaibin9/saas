"""Four-end leave workspace regressions on an independent MySQL database."""
from datetime import datetime

import pytest

from test_affairs_leave import TID, _seed, _hdr, _apply, _leave_action
from test_affairs_four_end_hardening import _stu_token


def test_leave_dates_accept_offsets_and_preserve_inclusive_local_day():
    from app.services.affairs_leave_date_contract import normalize_range
    from app.core.exceptions import AppException
    start, end = normalize_range('2026-09-05', '2026-09-05')
    assert start == datetime(2026, 9, 4, 16)
    assert end == datetime(2026, 9, 5, 15, 59, 59)
    assert normalize_range('2026-09-05T08:00:00+08:00', '2026-09-05T10:00:00Z') == (
        datetime(2026, 9, 5), datetime(2026, 9, 5, 10),
    )
    with pytest.raises(AppException):
        normalize_range('2026-09-05T08:00:00Z', '2026-09-05T09:00:00+08:00')
    with pytest.raises(AppException):
        normalize_range('2026-09-05 invalid', '2026-09-06')


def test_teacher_mobile_search_and_pagination_reach_later_records(client, db_mode):
    from test_affairs_leave_pending_search_contract import _seed as seed_search, TARGET_NAME
    ids = seed_search(db_mode)
    headers = _hdr(client, 'counselor01')
    path = '/api/v1/mobile/teacher/affairs/leaves/pending'
    first = client.get(path, headers=headers, params={'page': 1, 'pageSize': 20}).json()['data']
    assert first['total'] == 131
    assert len(first['list']) == 20
    last = client.get(path, headers=headers, params={'page': 7, 'pageSize': 20}).json()['data']
    assert str(ids['target_leave']) in {r['id'] for r in last['list']}
    match = client.get(path, headers=headers, params={'keyword': TARGET_NAME}).json()['data']
    assert match['total'] == 1
    assert match['list'][0]['id'] == str(ids['target_leave'])
    assert client.get(path, headers=headers, params={'pageSize': 101}).status_code == 400


def test_student_detail_and_four_end_return_extension_cancel_flow(client, db_mode):
    ids = _seed(db_mode)
    student = _stu_token('甲一', 'A001')
    other = _stu_token('乙一', 'B001')
    teacher = _hdr(client, 'counselor01')
    applied = client.post('/api/v1/portal/affairs/leave', headers=student, json={
        'leaveType': 'PERSONAL', 'startTime': '2026-10-01', 'endTime': '2026-10-01', 'reason': '回家处理家庭事务',
    })
    assert applied.status_code == 200, applied.text
    lid = applied.json()['data']['id']
    pc = f'/api/v1/portal/affairs/leave/{lid}'
    mini = f'/api/v1/mobile/affairs/leave/{lid}/detail'
    result = client.get(pc, headers=student)
    assert result.status_code == 200, result.text
    data = result.json()['data']
    assert data['startTime'] == '2026-09-30T16:00:00Z'
    assert data['handler'] == '王莉'
    assert 'auditTrail' not in data
    assert all('days=' not in t['description'] and 'wf=' not in t['description'] for t in data['timeline'])
    assert not {'APPROVE', 'PROXY_CANCEL'} & set(data['allowedActions'])
    assert client.get(mini, headers=student).json()['data']['id'] == lid
    assert client.get(pc, headers=other).status_code in (403, 404)
    assert client.get(mini, headers=teacher).status_code == 403
    current_staff = client.get(f'/api/v1/mobile/teacher/affairs/leaves/{lid}', headers=teacher).json()['data']
    assert 'APPROVE' in current_staff['allowedActions']
    # Teacher PC returns; student mini edits and resubmits using the newly saved version.
    returned = _leave_action(client, teacher, lid, 'return', {'reason': '请补充明确的请假事由'})
    assert returned.status_code == 200, returned.text
    editable = client.get(f'/api/v1/mobile/affairs/leave/{lid}/editable', headers=student).json()['data']
    edited = client.put(f'/api/v1/mobile/affairs/leave/{lid}/returned', headers=student, json={
        'version': editable['version'], 'reason': '返乡处理家中紧急事务',
    })
    assert edited.status_code == 200, edited.text
    re = client.post(f'/api/v1/mobile/affairs/leave/{lid}/resubmit', headers=student, json={'version': edited.json()['data']['version']})
    assert re.status_code == 200, re.text
    approved = _leave_action(client, teacher, lid, 'approve')
    assert approved.status_code == 200, approved.text
    version = approved.json()['data']['version']
    extended = client.post(f'/api/v1/mobile/affairs/leave/{lid}/extension', headers=student, json={
        'version': version, 'newEndTime': '2026-10-02', 'reason': '家中事务尚未处理完毕',
    })
    assert extended.status_code == 200, extended.text
    current = client.get(f'/api/v1/mobile/teacher/affairs/leaves/{lid}', headers=teacher).json()['data']
    assert current['extensions'][0]['newEndTime'] == '2026-10-02T15:59:59Z'
    review = client.post(f'/api/v1/mobile/teacher/affairs/leaves/{lid}/extension-approve', headers=teacher,
                         json={'version': current['version'], 'action': 'APPROVE'})
    assert review.status_code == 200, review.text
    current = client.get(pc, headers=student).json()['data']
    cancel = client.post(f'/api/v1/portal/affairs/leave/{lid}/cancel', headers=student,
                         json={'version': current['version'], 'proofNote': '学生本人已返校'})
    assert cancel.status_code == 200, cancel.text
    current = client.get(f'/api/v1/mobile/teacher/affairs/leaves/{lid}', headers=teacher).json()['data']
    assert current['cancelRecords'][0]['proofNote'] == '学生本人已返校'
    confirmation = client.post(f'/api/v1/mobile/teacher/affairs/leaves/{lid}/cancel-confirm', headers=teacher,
                               json={'version': current['version'], 'action': 'CONFIRM', 'note': '已见面核实学生返校'})
    assert confirmation.status_code == 200, confirmation.text
    final = client.get(pc, headers=student).json()['data']
    assert final['affairsStatus'] == 'CLOSED'
    assert final['allowedActions'] == []
    assert final['cancelRecords'][0]['status'] == 'CONFIRMED'
    assert 'confirmBy' not in final['cancelRecords'][0]
    assert len(final['timeline']) >= 6
    repeated = client.post(f'/api/v1/mobile/teacher/affairs/leaves/{lid}/cancel-confirm', headers=teacher,
                           json={'version': current['version'], 'action': 'CONFIRM'})
    assert repeated.status_code == 409


def test_same_name_legacy_leave_never_grants_ownership(client, db_mode):
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import CsLeave, CsServiceStudent, StudentProfile
    with get_sessionmaker()() as db:
        other = db.get(StudentProfile, ids['sb'])
        own = db.get(StudentProfile, ids['sa'])
        cs = CsServiceStudent(tenant_id=TID, student_id=other.id, student_no=other.student_no, name=own.real_name)
        db.add(cs); db.flush()
        old = CsLeave(tenant_id=TID, cs_student_id=cs.id, reason='仅供他人查看的请假说明', status='APPROVED')
        db.add(old); db.commit(); foreign_id = str(old.id)
        cross_tenant = CsLeave(tenant_id=TID + 1, student_id=own.id, reason='另一学校请假说明', status='APPROVED')
        db.add(cross_tenant); db.commit(); cross_tenant_id = str(cross_tenant.id)
    headers = _stu_token('甲一', 'A001')
    rows = client.get('/api/v1/mobile/affairs/leave/my', headers=headers).json()['data']['items']
    assert foreign_id not in {r['leaveId'] for r in rows}
    assert client.get(f'/api/v1/portal/affairs/leave/{foreign_id}', headers=headers).status_code in (403, 404)
    assert client.get(f'/api/v1/mobile/affairs/leave/{cross_tenant_id}/detail', headers=headers).status_code in (403, 404)


def test_date_filter_includes_last_local_day_and_material_link_keeps_scope(client, db_mode):
    ids = _seed(db_mode)
    teacher = _hdr(client, 'counselor01')
    lid = _apply(client, teacher, ids['sa'], '2026-10-01T16:00:00+08:00', '2026-10-01T23:00:00+08:00').json()['data']['id']
    listed = client.get('/api/v1/student-affairs/leave', headers=teacher,
                        params={'dateStart': '2026-10-01', 'dateEnd': '2026-10-01'}).json()['data']
    assert listed['total'] == 1
    material = client.post('/api/v1/student-affairs/material-requirements', headers=teacher, json={
        'bizType': 'LEAVE', 'bizId': lid, 'itemCode': 'LEAVE_PROOF', 'itemName': '请假证明', 'requirementReason': '请补充必要的证明材料',
    })
    assert material.status_code == 200, material.text
    filters = {'bizType': 'LEAVE', 'bizId': lid}
    own = client.get('/api/v1/mobile/affairs/material-requirements', headers=_stu_token('甲一', 'A001'), params=filters).json()['data']
    assert own['total'] == 1
    staff = client.get('/api/v1/student-affairs/material-requirements', headers=teacher, params=filters).json()['data']
    assert staff['total'] == 1
    other = client.get('/api/v1/mobile/affairs/material-requirements', headers=_stu_token('乙一', 'B001'), params=filters).json()['data']
    assert other['total'] == 0
