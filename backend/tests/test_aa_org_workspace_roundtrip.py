"""Academic organization edit roundtrips through formal HTTP and real MySQL."""
from test_aa_orgs import BASE, TID, _hdr, _mk_college, _mk_major, _mk_class


def test_same_parent_edit_roundtrip_and_version_conflict(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    college = _mk_college(client, headers)
    major = _mk_major(client, headers, college['id'], code='ROUND_MAJOR')
    row = _mk_class(client, headers, major['id'], code='ROUND_CLASS')
    # This is the body currently sent by the editor, including unchanged parent.
    result = client.put(f"{BASE}/classes/{row['id']}", headers=headers,
                        json={**row, 'className': '软件2601更名'})
    assert result.status_code == 200, result.text
    updated = result.json()['data']
    assert 'version' in row and updated['version'] == row['version'] + 1
    conflict = client.put(f"{BASE}/classes/{row['id']}", headers=headers,
                          json={'className': '旧页面覆盖', 'expectedVersion': row['version']})
    assert conflict.status_code == 409, conflict.text


def test_partial_updates_preserve_codes_and_optional_fields(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    college = client.post(f'{BASE}/colleges', headers=headers, json={'collegeName': '编码学院', 'code': 'ROUND_COL'}).json()['data']
    updated = client.put(f"{BASE}/colleges/{college['id']}", headers=headers, json={'shortName': '简称'}).json()['data']
    assert updated['code'] == 'ROUND_COL'
    major = _mk_major(client, headers, college['id'], code='ROUND_MAJOR')
    updated = client.put(f"{BASE}/majors/{major['id']}", headers=headers, json={'majorName': '软件技术更名'}).json()['data']
    assert updated['code'] == 'ROUND_MAJOR'
    assert updated['trainingLevel'] == 'HIGHER' and updated['direction'] == 'Web方向'
    row = _mk_class(client, headers, major['id'], code='ROUND_CLASS')
    updated = client.put(f"{BASE}/classes/{row['id']}", headers=headers, json={'className': '班级更名'}).json()['data']
    assert updated['classCode'] == 'ROUND_CLASS' and updated['capacity'] == row['capacity']
    cleared = client.put(f"{BASE}/classes/{row['id']}", headers=headers, json={'capacity': None, 'classCode': ''}).json()['data']
    assert cleared['capacity'] is None and cleared['classCode'] is None


def test_parent_change_requires_reason_and_both_college_scopes(client, db_mode):
    from test_aa_orgs_tier1_r2 import _seed_scoped
    ids = _seed_scoped(db_mode)
    scoped = _hdr(client, 'college_admin01')
    response = client.put(f"{BASE}/majors/{ids['majSw']}", headers=scoped,
                          json={'collegeId': str(ids['colWl']), 'reason': '学院组织归属调整'})
    assert response.status_code == 403, response.text
    school = _hdr(client, 'school_admin01')
    empty_major = _mk_major(client, school, str(ids['colSw']), name='未开班专业', code='MOVE_EMPTY')
    assert client.put(f"{BASE}/majors/{empty_major['id']}", headers=school,
                      json={'collegeId': str(ids['colWl'])}).status_code == 400
    response = client.put(f"{BASE}/majors/{empty_major['id']}", headers=school,
                          json={'collegeId': str(ids['colWl']), 'reason': '学院组织归属调整'})
    assert response.status_code == 200, response.text
    assert response.json()['data']['collegeId'] == str(ids['colWl'])


def test_counselor_omission_preserves_binding_and_null_revokes_scope(client, db_mode):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import TeacherStudentScope, User
    headers = _hdr(client, 'school_admin01')
    college = _mk_college(client, headers)
    major = _mk_major(client, headers, college['id'])
    row = _mk_class(client, headers, major['id'])
    with get_sessionmaker()() as db:
        user = User(tenant_id=TID, login_name='org_roundtrip_counselor', real_name='组织验收辅导员',
                    password_hash='x', user_type='TEACHER', status='ACTIVE')
        db.add(user); db.commit(); user_id = str(user.id)
    assert client.put(f"{BASE}/classes/{row['id']}", headers=headers, json={'counselorId': user_id}).status_code == 200
    renamed = client.put(f"{BASE}/classes/{row['id']}", headers=headers, json={'className': '更名后的班级'}).json()['data']
    assert renamed['counselorId'] == user_id
    cleared = client.put(f"{BASE}/classes/{row['id']}", headers=headers, json={'counselorId': None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()['data']['counselorId'] is None
    with get_sessionmaker()() as db:
        scopes = db.scalars(select(TeacherStudentScope).where(TeacherStudentScope.tenant_id == TID,
            TeacherStudentScope.teacher_key == 'org_roundtrip_counselor', TeacherStudentScope.scope_type == 'CLASS')).all()
        assert scopes and all(scope.status == 'INACTIVE' for scope in scopes)


def test_creating_class_with_counselor_establishes_the_same_scope_as_editing(client, db_mode):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import TeacherStudentScope, User
    headers = _hdr(client, 'school_admin01')
    college = _mk_college(client, headers)
    major = _mk_major(client, headers, college['id'])
    with get_sessionmaker()() as db:
        user = User(tenant_id=TID, login_name='org_create_counselor', real_name='新班辅导员',
                    password_hash='x', user_type='TEACHER', status='ACTIVE')
        db.add(user); db.commit(); user_id = str(user.id)
    created = client.post(f'{BASE}/classes', headers=headers, json={
        'majorId': major['id'], 'className': '新建绑定班级', 'counselorId': user_id,
    })
    assert created.status_code == 200, created.text
    with get_sessionmaker()() as db:
        scope = db.scalar(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == TID, TeacherStudentScope.teacher_key == 'org_create_counselor',
            TeacherStudentScope.ref_value == '新建绑定班级', TeacherStudentScope.status == 'ACTIVE',
            TeacherStudentScope.is_deleted.is_(False)))
        assert scope is not None
