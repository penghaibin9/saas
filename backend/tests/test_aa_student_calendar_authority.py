"""Student PC and mobile must consume the staff current-term authority on real MySQL."""
from datetime import datetime

import pytest

TID = 1000000000000000001
PATHS = ('/api/v1/portal/academic/calendar', '/api/v1/mobile/academic/calendar/my')


def seed_calendar():
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import AaCalendarEvent, AaTerm, StudentProfile

    with get_sessionmaker()() as db:
        db.add(StudentProfile(tenant_id=TID, student_no='CAL-AUTH-01', real_name='校历核验学生',
                              current_stage='ENROLLED', student_status='REGISTERED', status='ACTIVE'))
        terms = [AaTerm(tenant_id=TID, year_code=f'{year}-{year+1}', term_no=1,
                        start_date=datetime(year, 9, 1), end_date=datetime(year+1, 1, 20),
                        teaching_weeks=20, status='PUBLISHED', is_current=False) for year in (2096, 2097)]
        db.add_all(terms)
        db.flush()
        ids = [int(t.id) for t in terms]
        for term in terms:
            db.add(AaCalendarEvent(tenant_id=TID, term_id=term.id, event_type='HOLIDAY',
                                   start_date=term.start_date, end_date=term.start_date,
                                   remark=f'校历 {term.year_code}'))
        db.commit()
    token = create_access_token({'userId': 'u-CAL-AUTH-01', 'realName': '校历核验学生',
                                 'studentNo': 'CAL-AUTH-01', 'userType': 'STUDENT',
                                 'tenantId': str(TID), 'currentRoleCode': 'STUDENT',
                                 'activeContextId': 'ctx', 'clientType': 'PC'})
    return ids, {'Authorization': f'Bearer {token}'}


def test_both_student_ends_use_governance_even_when_legacy_flags_disagree(client, db_mode):
    from sqlalchemy import update
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    from app.services import academic_calendar_service as calendar

    (old, current), headers = seed_calendar()
    enrolled = calendar.enroll_term(current, tenant_id=TID)
    validated = calendar.transition(current, 'VALIDATED', reason='校历跨端核验',
                                     expected_version=enrolled['version'], tenant_id=TID)
    calendar.transition(current, 'ACTIVE', reason='校历跨端核验',
                        expected_version=validated['version'], tenant_id=TID)
    # Deliberate migration-era inconsistency in this isolated test schema.
    with get_sessionmaker()() as db:
        db.execute(update(AaTerm).where(AaTerm.tenant_id == TID).values(is_current=False))
        db.execute(update(AaTerm).where(AaTerm.id == old).values(is_current=True))
        db.commit()
    for path in PATHS:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()['data']
        assert result['termId'] == str(current)
        assert result['events'][0]['remark'] == '校历 2097-2098'


@pytest.mark.parametrize('current_count', [0, 1, 2])
def test_student_calendars_handle_missing_unique_and_ambiguous_legacy_terms(client, db_mode, current_count):
    from sqlalchemy import update
    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    ids, headers = seed_calendar()
    with get_sessionmaker()() as db:
        db.execute(update(AaTerm).where(AaTerm.id.in_(ids[:current_count])).values(is_current=True))
        db.commit()
    for path in PATHS:
        response = client.get(path, headers=headers)
        if current_count == 2:
            assert response.status_code == 409, response.text
        else:
            assert response.status_code == 200, response.text
            data = response.json()['data']
            assert data['hasTerm'] is bool(current_count)
            if current_count:
                assert data['termId'] == str(ids[0])
