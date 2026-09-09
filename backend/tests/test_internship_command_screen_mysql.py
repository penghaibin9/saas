"""Real MySQL aggregate boundaries; use the repository's isolated db_mode fixture."""
from datetime import date

from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.models import InternshipBatch, InternshipRecord, StudentProfile

TID = 1000000000000000001
OTHER_TID = 1000000000000000002
ENDPOINT = '/api/v1/internship/stats/command-screen'


def principal(role, user_id, tenant=TID, user_type='TEACHER'):
    return {'Authorization': 'Bearer ' + create_access_token({
        'userId': str(user_id), 'realName': '范围核验教师', 'userType': user_type,
        'tenantId': str(tenant), 'currentRoleCode': role,
        'activeContextId': 'ctx', 'clientType': 'PC', 'tid': 'screen-test',
    })}


def test_command_screen_mysql_boundaries(client, auth_headers, db_mode):
    with get_sessionmaker()() as db:
        batches = []
        for tid, number in [(TID, 'WALL-A'), (TID, 'WALL-EMPTY'), (OTHER_TID, 'WALL-OTHER')]:
            row = InternshipBatch(tenant_id=tid, batch_no=number, batch_name=number,
                                  status='DRAFT', planned_count=3)
            db.add(row)
            db.flush()
            batches.append(row.id)
        for index, (tid, bid, advisor, deleted) in enumerate([
            (TID, batches[0], 710001, False),
            (TID, batches[0], 710002, False),
            (TID, batches[0], 710001, True),
            (OTHER_TID, batches[2], 710001, False),
        ]):
            student = StudentProfile(tenant_id=tid, student_no=f'WALL-{index}',
                                     real_name='合成学生', student_status='NORMAL',
                                     status='ACTIVE', is_deleted=deleted)
            db.add(student)
            db.flush()
            db.add(InternshipRecord(tenant_id=tid, student_id=student.id, batch_id=bid,
                                    advisor_user_id=advisor, status='PREPARING',
                                    risk_level='NONE'))
        db.commit()

    def fetch(batch, headers=auth_headers):
        return client.get(ENDPOINT, params={'batchId': str(batch)}, headers=headers)

    school = fetch(batches[0])
    assert school.status_code == 200, school.json()
    data = school.json()['data']
    assert data['batchId'] == str(batches[0])
    assert data['totals']['students'] == 2  # no other tenant or deleted student
    assert data['totals']['schoolMentors'] == 2
    assert data['geography']['unlocatedStudents'] == 2
    assert len(data['attendanceDaily']) == 7
    assert len(data['riskNewDaily']) == 7
    assert len(data['employmentMonths']) == 6
    assert date.fromisoformat(data['riskNewDaily'][-1]['date'])

    mentor = fetch(batches[0], principal('INTERN_MENTOR', 710001))
    assert mentor.status_code == 200, mentor.json()
    assert mentor.json()['data']['totals']['students'] == 1
    outsider = fetch(batches[0], principal('INTERN_MENTOR', 710009))
    assert outsider.status_code == 200, outsider.json()
    assert outsider.json()['data']['totals']['students'] == 0

    empty = fetch(batches[1])
    assert empty.status_code == 200, empty.json()
    assert empty.json()['data']['totals']['students'] == 0
    assert empty.json()['data']['regions'] == []
    assert fetch(batches[0]).json()['data']['totals']['students'] == 2
    assert fetch(batches[2]).status_code in (403, 404)
    assert fetch(batches[0], principal('STUDENT', 710003, user_type='STUDENT')).status_code == 403
    # The application's validation handler normalizes missing query fields to 400.
    assert client.get(ENDPOINT, headers=auth_headers).status_code == 400
    assert fetch('not-a-batch').status_code in (400, 404, 422)
