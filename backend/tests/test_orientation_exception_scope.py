"""All exception entrypoints enforce the same real student-scope context."""
from test_orientation_o3_self_service import _seed_o3, TID


def test_exception_scope_filters_before_paging_and_guards_all_commands(client, db_mode, auth_headers, monkeypatch):
    from app.core import affairs_security as security
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent, OrientationException, OrientationExceptionFollowup
    ids = _seed_o3(db_mode)
    with get_sessionmaker()() as db:
        own = db.get(OrientationStudent, ids['orientationId'])
        profile_id, batch_id = own.student_id, own.batch_id
        other = OrientationStudent(tenant_id=TID, batch_id=batch_id,
            student_id=ids['otherProfileId'], name='范围外新生', admission_no='SCOPE-OTHER',
            source_type='MANUAL', source_record_id='SCOPE-OTHER', identity_status='LINKED', record_status='ACTIVE')
        unlinked = OrientationStudent(tenant_id=TID, batch_id=batch_id, name='未关联新生',
            admission_no='SCOPE-UNLINKED', source_type='MANUAL', source_record_id='SCOPE-UNLINKED',
            identity_status='UNLINKED', record_status='ACTIVE')
        db.add_all([other, unlinked]); db.flush()
        rows = [OrientationException(tenant_id=TID, ori_student_id=student.id,
                exception_type='DORM', description='宿舍安排待核实', status='OPEN')
                for student in [own, other, unlinked]]
        db.add_all(rows); db.flush()
        exception_ids = [row.id for row in rows]
        foreign_students = [other.id, unlinked.id]
        db.commit()
    # Real scope implementation, with only the authenticated scope resolution supplied by fixture.
    ctx = security.StudentAffairsSecurityContext(user_id='scope-review', login_name='scope-review',
        tenant_id=TID, role_codes={'COUNSELOR'}, permission_codes={'orientation.*'},
        sensitive_permissions=set(), scope_type='STUDENT', student_ids={profile_id})
    monkeypatch.setattr(security, 'build_affairs_context', lambda user, db=None: ctx)
    base = '/api/v1/orientation/exceptions'
    result = client.get(base, headers=auth_headers, params={'batchId':batch_id, 'pageSize':1})
    assert result.status_code == 200, result.text
    assert result.json()['data']['total'] == 1
    assert result.json()['data']['items'][0]['id'] == str(exception_ids[0])
    for eid in exception_ids[1:]:
        detail = client.get(f'{base}/{eid}', headers=auth_headers)
        assert detail.status_code == 403, detail.text
        for action, payload in [('followup', {'content':'已电话核实住宿安排', 'way':'PHONE'}),
                                ('resolve', {'note':'已经处理完成'}),
                                ('escalate', {'reason':'需要上级协调处理住宿'})]:
            response = client.post(f'{base}/{eid}/{action}', headers=auth_headers, json=payload)
            assert response.status_code == 403, response.text
    for sid in foreign_students:
        response = client.post(base, headers=auth_headers, json={'studentId':str(sid),
            'exceptionType':'DORM', 'description':'该学生宿舍安排待核实', 'riskLevel':'MEDIUM'})
        assert response.status_code == 403, response.text
    with get_sessionmaker()() as db:
        assert all(db.get(OrientationException, eid).status == 'OPEN' for eid in exception_ids[1:])
        assert db.query(OrientationExceptionFollowup).filter(
            OrientationExceptionFollowup.exception_id.in_(exception_ids[1:])).count() == 0
    assert client.get(f'{base}/{exception_ids[0]}', headers=auth_headers).status_code == 200
    allowed = client.post(f'{base}/{exception_ids[0]}/followup', headers=auth_headers,
                         json={'content':'已核实本人负责学生住宿', 'way':'PHONE'})
    assert allowed.status_code == 200, allowed.text
    ctx.student_ids = set()
    empty = client.get(base, headers=auth_headers).json()['data']
    assert empty['total'] == 0
    assert client.get(f'{base}/{exception_ids[0]}', headers=auth_headers).status_code == 403
