"""Single-student transfer through the public org facade, MySQL and real readers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select

from test_aa_orgs import BASE, TID, _hdr
from test_aa_orgs_tier1_r2 import _seed_scoped


def _move(client, headers, student, target, **extra):
    return client.post(f'{BASE}/class-adjustments', headers=headers,
                       json={'studentId': str(student), 'targetClassId': str(target), **extra})


def _preview(client, headers, student, target):
    return client.post(f'{BASE}/class-adjustments/preview', headers=headers,
                       json={'studentId': str(student), 'targetClassId': str(target)})


def test_inactive_target_and_parent_are_rejected_without_fact_switch(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, StudentAcademicFact
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    for model, key, attribute, bad, original in [
        (SchoolClass, 'c2', 'class_status', 'DISBANDED', 'NORMAL'),
        (SchoolClass, 'c2', 'status', 'INACTIVE', 'ACTIVE'),
        (Major, 'majSw', 'status', 'INACTIVE', 'ACTIVE'),
        (College, 'colSw', 'status', 'INACTIVE', 'ACTIVE'),
    ]:
        with get_sessionmaker()() as db:
            setattr(db.get(model, ids[key]), attribute, bad); db.commit()
        result = _move(client, headers, ids['s1'], ids['c2'])
        assert result.status_code == 400, result.text
        with get_sessionmaker()() as db:
            assert db.get(StudentProfile, ids['s1']).class_id == ids['c1']
            assert db.scalar(select(func.count()).select_from(StudentAcademicFact).where(StudentAcademicFact.student_id == ids['s1'], StudentAcademicFact.tenant_id == TID)) == 1
            setattr(db.get(model, ids[key]), attribute, original); db.commit()


def test_unassigned_student_still_requires_source_college_scope(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'college_admin01')
    with get_sessionmaker()() as db:
        student = StudentProfile(tenant_id=TID, student_no='ORG-NO-CLASS', real_name='未分班学生',
            college_id=ids['colWl'], major_id=ids['majWl'], student_status='REGISTERED', status='ACTIVE')
        db.add(student); db.commit(); sid = student.id
    result = _move(client, headers, sid, ids['c2'])
    assert result.status_code == 403, result.text
    assert _preview(client, headers, sid, ids['c2']).status_code == 403
    with get_sessionmaker()() as db:
        assert db.get(StudentProfile, sid).class_id is None


def test_stale_student_confirmation_cannot_overwrite_newer_state(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        version = int(db.get(StudentProfile, ids['s1']).version or 0)
    result = _move(client, headers, ids['s1'], ids['c2'], expectedVersion=version + 1)
    assert result.status_code == 409, result.text
    listed = client.get(f"{BASE}/classes/{ids['c1']}/students", headers=headers).json()['data']['items']
    assert next(row for row in listed if row['id'] == str(ids['s1']))['version'] == version


def test_preview_is_read_only_and_capacity_is_a_warning_then_fact_and_readers_follow(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, StudentAcademicFact, AffairsAuditTrail, User
    from test_portal_profile import _stu_token
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        # The mock transport uses a legacy string id; back it with a real account
        # so the fact's numeric author field can resolve the authenticated login.
        if not db.scalar(select(User.id).where(User.tenant_id == TID, User.login_name == 'school_admin01')):
            db.add(User(tenant_id=TID, login_name='school_admin01', real_name='验收管理员', password_hash='x', user_type='TEACHER', status='ACTIVE'))
        db.get(SchoolClass, ids['c2']).capacity = 0
        db.commit()
    preview = _preview(client, headers, ids['s1'], ids['c2'])
    assert preview.status_code == 200, preview.text
    data = preview.json()['data']
    assert data['target']['studentCount'] == 0 and data['target']['afterStudentCount'] == 1
    assert data['target']['capacity'] == 0 and data['warnings']
    with get_sessionmaker()() as db:
        assert db.get(StudentProfile, ids['s1']).class_id == ids['c1']
        assert db.scalar(select(func.count()).select_from(StudentAcademicFact).where(StudentAcademicFact.student_id == ids['s1'], StudentAcademicFact.tenant_id == TID)) == 1
    result = _move(client, headers, ids['s1'], ids['c2'], expectedVersion=data['student']['version'], expectedTargetVersion=data['target']['version'], reason='同专业班级名册调整验收')
    assert result.status_code == 200, result.text
    receipt = result.json()['data']
    assert receipt['toClassName'] == '软件2602' and receipt['studentVersion'] == data['student']['version'] + 1
    with get_sessionmaker()() as db:
        facts = db.scalars(select(StudentAcademicFact).where(StudentAcademicFact.student_id == ids['s1'], StudentAcademicFact.tenant_id == TID).order_by(StudentAcademicFact.version_no)).all()
        assert len(facts) == 2 and facts[0].valid_to == facts[1].valid_from
        assert facts[1].valid_to is None and facts[1].class_id == ids['c2']
        assert facts[1].created_by is not None
        student = db.get(StudentProfile, ids['s1'])
        assert student.major_id == facts[1].major_id and student.college_id == facts[1].college_id
        assert student.grade == facts[0].grade
        audit = db.scalar(select(AffairsAuditTrail).where(AffairsAuditTrail.tenant_id == TID, AffairsAuditTrail.biz_type == 'AA_ORG_CLASS_ADJUST', AffairsAuditTrail.biz_id == ids['s1']))
        assert '同专业班级名册调整验收' in audit.detail
    source = client.get(f"{BASE}/classes/{ids['c1']}/students", headers=headers).json()['data']['items']
    target = client.get(f"{BASE}/classes/{ids['c2']}/students", headers=headers).json()['data']['items']
    assert all(row['id'] != str(ids['s1']) for row in source)
    assert any(row['id'] == str(ids['s1']) for row in target)
    portal = client.get('/api/v1/portal/profile/enrollment', headers=_stu_token('方向甲', 'ORG601'))
    assert portal.status_code == 200 and portal.json()['data']['className'] == '软件2602', portal.text
    mobile = client.get('/api/v1/mobile/me/profile', headers=_stu_token('方向甲', 'ORG601'))
    assert mobile.status_code == 200 and mobile.json()['data']['className'] == '软件2602', mobile.text
    teacher = client.get(f"/api/v1/teacher-mobile/students?classId={ids['c2']}&pageSize=20", headers=headers)
    assert teacher.status_code == 200, teacher.text
    assert any(row['studentId'] == str(ids['s1']) and row['className'] == '软件2602' for row in teacher.json()['data']['items'])


def test_two_stale_confirmations_only_switch_the_student_once(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, StudentAcademicFact
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        version = int(db.get(StudentProfile, ids['s1']).version or 0)
    barrier = Barrier(2)
    def transfer(target):
        barrier.wait(timeout=20)
        return _move(client, headers, ids['s1'], target, expectedVersion=version)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transfer, [ids['c2'], ids['cEmpty']]))
    assert sorted(row.status_code for row in results) == [200, 409], [row.text for row in results]
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(StudentAcademicFact).where(StudentAcademicFact.student_id == ids['s1'], StudentAcademicFact.tenant_id == TID)) == 2


def test_terminal_student_is_not_reassigned_by_ordinary_transfer(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        student = StudentProfile(tenant_id=TID, student_no='ORG-GRADUATE', real_name='毕业归档学生',
            college_id=ids['colSw'], major_id=ids['majSw'], class_id=ids['c1'], student_status='GRADUATED', status='ACTIVE')
        db.add(student); db.commit(); sid = student.id
    result = _move(client, headers, sid, ids['c2'])
    assert result.status_code == 400, result.text


def test_target_changed_after_preview_requires_a_fresh_confirmation(client, db_mode):
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    result = _preview(client, headers, ids['s1'], ids['c2'])
    assert result.status_code == 200, result.text
    data = result.json()['data']
    assert client.put(f"{BASE}/classes/{ids['c2']}", headers=headers, json={'className': '改名后的目标班'}).status_code == 200
    result = _move(client, headers, ids['s1'], ids['c2'], expectedVersion=data['student']['version'], expectedTargetVersion=data['target']['version'])
    assert result.status_code == 409, result.text


def test_preview_denies_read_only_and_cross_tenant_requests(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    ids = _seed_scoped(db_mode)
    assert _preview(client, _hdr(client, 'student01'), ids['s1'], ids['c2']).status_code == 403
    with get_sessionmaker()() as db:
        foreign = SchoolClass(tenant_id=TID + 700, major_id=ids['majSw'], class_name='异校班', status='ACTIVE', class_status='NORMAL')
        db.add(foreign); db.commit(); foreign_id = foreign.id
    headers = _hdr(client, 'school_admin01')
    assert _move(client, headers, ids['s1'], foreign_id).status_code == 404
    assert _preview(client, headers, ids['s1'], foreign_id).status_code == 404


def test_target_membership_change_invalidates_the_preview_without_class_version_change(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    data = _preview(client, headers, ids['s1'], ids['c2']).json()['data']
    with get_sessionmaker()() as db:
        db.add(StudentProfile(tenant_id=TID, student_no='ORG-TARGET-NEW', real_name='核对后新转入',
            college_id=ids['colSw'], major_id=ids['majSw'], class_id=ids['c2'], student_status='REGISTERED', status='ACTIVE'))
        db.commit()
    response = _move(client, headers, ids['s1'], ids['c2'], expectedVersion=data['student']['version'],
        expectedTargetVersion=data['target']['version'], expectedSnapshotHash=data['snapshotHash'])
    assert response.status_code == 409, response.text


def test_preview_rejects_projection_drift_and_audit_failure_rolls_back_the_entire_transfer(client, db_mode, monkeypatch):
    import pytest
    from sqlalchemy import update
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, StudentAcademicFact
    import importlib
    legacy = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        original_grade = db.get(StudentProfile, ids['s1']).grade
        db.execute(update(StudentProfile).where(StudentProfile.id == ids['s1']).values(grade='1999')); db.commit()
    assert _preview(client, headers, ids['s1'], ids['c2']).status_code == 409
    with get_sessionmaker()() as db:
        db.execute(update(StudentProfile).where(StudentProfile.id == ids['s1']).values(grade=original_grade)); db.commit()
    def broken_audit(*args, **kwargs):
        raise RuntimeError('Synthetic audit write failure')
    monkeypatch.setattr(legacy, '_audit', broken_audit)
    with pytest.raises(RuntimeError, match='Synthetic audit'):
        _move(client, headers, ids['s1'], ids['c2'])
    with get_sessionmaker()() as db:
        assert db.get(StudentProfile, ids['s1']).class_id == ids['c1']
        assert db.scalar(select(func.count()).select_from(StudentAcademicFact).where(StudentAcademicFact.student_id == ids['s1'], StudentAcademicFact.tenant_id == TID)) == 1
