"""Real HTTP/MySQL coverage for organization read scope and teaching ledger identity."""
from datetime import datetime

from sqlalchemy import select

from test_aa_orgs import BASE, TID, _hdr
from test_aa_orgs_tier1_r2 import _seed_scoped


def _class_only(ids):
    from app.db.session import get_sessionmaker
    from app.models import Major, TeacherStudentScope
    with get_sessionmaker()() as db:
        grant = db.scalar(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == TID, TeacherStudentScope.teacher_key == 'college_admin01'))
        grant.scope_type = 'CLASS'
        grant.ref_value = '软件2601'
        db.add(Major(tenant_id=TID, college_id=ids['colSw'], major_name='同院无授权专业', status='ACTIVE'))
        db.commit()


def test_class_scope_does_not_expand_to_sibling_classes_or_parent_write(client, db_mode):
    ids = _seed_scoped(db_mode)
    _class_only(ids)
    headers = _hdr(client, 'college_admin01')
    classes = client.get(f'{BASE}/classes', headers=headers).json()['data']['items']
    assert {row['id'] for row in classes} == {str(ids['c1'])}
    majors = client.get(f'{BASE}/majors', headers=headers).json()['data']['items']
    assert {row['id'] for row in majors} == {str(ids['majSw'])}
    tree = client.get(f'{BASE}/tree', headers=headers).json()['data']['colleges']
    assert [row['id'] for col in tree for major in col['majors'] for row in major['classes']] == [str(ids['c1'])]
    grades = client.get(f'{BASE}/grades', headers=headers).json()['data']['items']
    assert sum(row['classCount'] for row in grades) == 1
    stats = client.get(f'{BASE}/stats', headers=headers).json()['data']
    assert (stats['collegeCount'], stats['majorCount'], stats['classCount'], stats['studentCount']) == (1, 1, 1, 2)
    assert client.get(f"{BASE}/classes/{ids['c1']}/students", headers=headers).status_code == 200
    assert client.get(f"{BASE}/classes/{ids['c2']}/students", headers=headers).status_code == 403
    assert client.put(f"{BASE}/colleges/{ids['colSw']}", headers=headers,
                      json={'collegeName': '班级授权不能修改整个学院'}).status_code == 403


def test_audit_stays_in_module_and_authorized_college_including_deleted_objects(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, SchoolClass
    ids = _seed_scoped(db_mode)
    with get_sessionmaker()() as db:
        db.get(SchoolClass, ids['cEmpty']).is_deleted = True
        for kind, ref, detail in [('AA_ORG_CLASS', ids['c1'], '范围内班级'),
                                  ('AA_ORG_CLASS', ids['cWl'], '外学院班级'),
                                  ('AA_ORG_CLASS', ids['cEmpty'], '已删除的本院班级'),
                                  ('AA_ROSTER', ids['s1'], '其他模块审计')]:
            db.add(AffairsAuditTrail(tenant_id=TID, biz_type=kind, biz_id=ref,
                                    action='UPDATE', operator='验收', detail=detail, occurred_at=datetime.utcnow()))
        db.commit()
    headers = _hdr(client, 'college_admin01')
    rows = client.get(f'{BASE}/audit', headers=headers).json()['data']['items']
    assert {row['detail'] for row in rows} == {'范围内班级', '已删除的本院班级'}
    denied = client.get(f'{BASE}/audit', headers=_hdr(client, 'school_admin01'), params={'bizType': 'AA_ROSTER'})
    assert denied.status_code == 400


def _teaching_fixture(ids):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTeachingTask, AaTeachingTaskBatch, AaTeachingClass
    with get_sessionmaker()() as db:
        terms = [AaTerm(tenant_id=TID, year_code='2040-2041', term_no=n, status='DRAFT') for n in (1, 2)]
        db.add_all(terms)
        db.flush()
        batches = [AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name=f'教学验收{n}', status='DRAFT')
                   for n, term in enumerate(terms)]
        db.add_all(batches)
        db.flush()
        tasks = [AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=91000 + n, course_name=f'课程{n}',
                               class_id=ids['c1'], teaching_class_code='REUSED', teaching_class_name='历史教学班名',
                               expected_students=40, status='READY') for n, batch in enumerate(batches)]
        db.add_all(tasks)
        db.flush()
        db.add(AaTeachingClass(tenant_id=TID, teaching_task_id=tasks[0].id, term_id=terms[0].id,
                              course_id=tasks[0].course_id, class_code='FORMAL', class_name='正式教学班名',
                              capacity=35, status='ACTIVE'))
        for class_id, status, code in [(ids['cWl'], 'READY', 'OUTSIDE'), (ids['c1'], 'MERGED', 'OLD-MERGED')]:
            db.add(AaTeachingTask(tenant_id=TID, batch_id=batches[0].id, course_id=91900, course_name='不应纳入',
                                 class_id=class_id, teaching_class_code=code, teaching_class_name=code, status=status))
        db.commit()
        return [term.id for term in terms]


def test_teaching_ledger_filters_term_scope_and_prefers_existing_formal_projection(client, db_mode):
    ids = _seed_scoped(db_mode)
    term_ids = _teaching_fixture(ids)
    headers = _hdr(client, 'college_admin01')
    rows = client.get(f'{BASE}/teaching-classes', headers=headers).json()['data']['items']
    assert len(rows) == 2
    assert len({row['id'] for row in rows}) == 2
    formal = next(row for row in rows if row['termId'] == str(term_ids[0]))
    assert formal['teachingClassName'] == '正式教学班名'
    assert formal['teachingClassCode'] == 'FORMAL'
    assert formal['expectedStudents'] == 35
    filtered = client.get(f'{BASE}/teaching-classes', headers=headers,
                          params={'termCode': '2040-2041-2'}).json()['data']['items']
    assert len(filtered) == 1 and filtered[0]['termId'] == str(term_ids[1])
    filtered_id = client.get(f'{BASE}/teaching-classes', headers=headers,
                             params={'termId': str(term_ids[0])}).json()['data']['items']
    assert len(filtered_id) == 1 and filtered_id[0]['id'] == formal['id']


def test_missing_scope_cannot_read_teaching_audit_or_orphan_adjustments(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaClassAdjustmentRequest, TeacherStudentScope
    ids = _seed_scoped(db_mode)
    _teaching_fixture(ids)
    with get_sessionmaker()() as db:
        for grant in db.scalars(select(TeacherStudentScope).where(TeacherStudentScope.tenant_id == TID,
                                    TeacherStudentScope.teacher_key == 'college_admin01')):
            grant.status = 'INACTIVE'
        db.add(AaClassAdjustmentRequest(tenant_id=TID, adjust_type='SPLIT', from_class_ids='[999999]',
                                       reason='组织归属无法解析', status='DRAFT'))
        db.commit()
    headers = _hdr(client, 'college_admin01')
    for route in ('teaching-classes', 'audit', 'class-adjustment-requests'):
        response = client.get(f'{BASE}/{route}', headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()['data']['items'] == [], route
