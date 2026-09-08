from test_orientation_o4_qualification import _seed, _student_headers, TID


def test_student_orientation_uses_linked_profile_class(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, OrientationStudent
    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        school_class = SchoolClass(tenant_id=TID, major_id=1, class_name='主档实际班级', grade='2026', status='ACTIVE')
        db.add(school_class)
        db.flush()
        profile = db.get(StudentProfile, ids['profile'])
        profile.class_id = school_class.id
        orientation = db.get(OrientationStudent, ids['orientation'])
        orientation.class_id = None
        orientation.class_name = '导入旧班级'
        orientation.grade = '旧年级'
        db.commit()
    response = client.get('/api/v1/mobile/orientation/my', headers=_student_headers(ids['user'], ids['profile'], ids['studentNo'], ids['name']))
    assert response.status_code == 200, response.text
    assert response.json()['data']['className'] == '主档实际班级'
    assert response.json()['data']['grade'] == '2026'
