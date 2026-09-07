"""Real router/DB checks for the newly reachable term detail workflow."""
from test_aa_term import BASE, _hdr, _term


def test_create_rejects_invalid_calendar_fields_before_writing(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    for change in ({'yearCode': '2026-2029'}, {'startDate': 'not-a-date'},
                   {'startDate': '2027-02-01', 'endDate': '2026-09-01'},
                   {'teachingWeeks': 0}, {'teachingWeeks': True},
                   {'teachingWeeks': 18, 'examWeekStart': 19}):
        response = client.post(f'{BASE}/terms', headers=headers, json={'yearCode': '2026-2027', 'termNo': 1, **change})
        assert response.status_code in (400, 422), response.text
    assert client.get(f'{BASE}/terms', headers=headers).json()['data']['total'] == 0


def test_detail_preview_save_version_and_state_guards(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    path = f'{BASE}/terms/{term_id}'
    detail = client.get(path + '/workspace', headers=headers)
    assert detail.status_code == 200, detail.text
    before = detail.json()['data']
    change = {'termName': '开学条件验收学期', 'teachingWeeks': 20, 'examWeekStart': 19}
    preview = client.post(path + '/impact-preview', headers=headers, json=change)
    assert preview.status_code == 200, preview.text
    assert preview.json()['data']['canSave'] is True
    updated = client.put(path, headers=headers, json={**change, 'expectedVersion': before['version']})
    assert updated.status_code == 200, updated.text
    after = updated.json()['data']
    assert after['termName'] == change['termName']
    assert after['teachingWeeks'] == 20 and after['examWeekStart'] == 19
    assert after['version'] == before['version'] + 1
    assert any(row['action'] == 'UPDATE_BASIC' for row in after['timeline'])
    stale = client.put(path, headers=headers, json={'termName': '旧版本覆盖', 'expectedVersion': before['version']})
    assert stale.status_code == 409
    assert client.post(path + '/publish', headers=headers).status_code == 200
    assert client.put(path, headers=headers, json={'teachingWeeks': 21}).status_code == 409
    assert client.put(path, headers=headers, json={'termName': '更正显示名称'}).status_code == 200
    assert client.post(path + '/freeze', headers=headers).status_code == 200
    assert client.post(path + '/unfreeze', headers=headers, json={'reason': '短'}).status_code == 400
    assert client.post(path + '/unfreeze', headers=headers, json={'reason': '恢复本学期业务办理'}).status_code == 200
    final = client.get(path + '/workspace', headers=headers).json()['data']
    assert final['status'] == 'PUBLISHED'
    assert {row['action'] for row in final['timeline']} >= {'CREATE', 'UPDATE_BASIC', 'PUBLISH', 'FREEZE', 'UNFREEZE'}


def test_optional_fields_clear_without_silently_restoring_the_previous_value(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    path = f'{BASE}/terms/{term_id}'
    change = {'termName': '', 'teachingWeeks': None, 'examWeekStart': None}
    preview = client.post(path + '/impact-preview', headers=headers, json=change).json()['data']
    assert any(row['field'] == 'teachingWeeks' and row['after'] is None for row in preview['changes'])
    saved = client.put(path, headers=headers, json=change)
    assert saved.status_code == 200, saved.text
    assert saved.json()['data']['teachingWeeks'] is None
    assert saved.json()['data']['termName'] == ''


def test_term_workspace_rejects_invalid_week_values_as_validation_errors(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    for value in (0, 31, 17.5, 'bad', True):
        response = client.post(f'{BASE}/terms/{term_id}/impact-preview', headers=headers, json={'teachingWeeks': value})
        assert response.status_code in (400, 422), (value, response.text)


def test_student_cannot_read_or_modify_staff_term_workspace(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    student = _hdr(client, 'student01')
    path = f'{BASE}/terms/{term_id}'
    assert client.get(path + '/workspace', headers=student).status_code == 403
    assert client.post(path + '/impact-preview', headers=student, json={}).status_code == 403
    assert client.put(path, headers=student, json={'termName': '越权修改'}).status_code == 403


def test_teaching_week_configuration_clears_exam_week_and_invalidates_stale_detail(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    path = f'{BASE}/terms/{term_id}'
    before = client.get(path + '/workspace', headers=headers).json()['data']
    assert client.put(path + '/teaching-weeks', headers=headers, json={'teachingWeeks': 20, 'examWeekStart': 19}).status_code == 200
    cleared = client.put(path + '/teaching-weeks', headers=headers, json={'teachingWeeks': 20, 'examWeekStart': None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()['data']['examWeekStart'] is None
    conflict = client.put(path, headers=headers, json={'termName': '过期草稿', 'expectedVersion': before['version']})
    assert conflict.status_code == 409


def test_teaching_week_shortcut_checks_existing_schedule_impacts(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaScheduleItem

    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    with get_sessionmaker()() as db:
        batch = AaScheduleBatch(tenant_id=1000000000000000001, term_id=int(term_id), batch_name='周次关联校验')
        db.add(batch)
        db.flush()
        db.add(AaScheduleItem(tenant_id=1000000000000000001, batch_id=batch.id, weekday=1, slot_no=1, start_week=1, end_week=18))
        db.commit()
    response = client.put(f'{BASE}/terms/{term_id}/teaching-weeks', headers=headers, json={'teachingWeeks': 12})
    assert response.status_code == 409, response.text
    assert client.get(f'{BASE}/terms/{term_id}/workspace', headers=headers).json()['data']['teachingWeeks'] == 18


def test_switch_log_includes_governance_activation_but_not_definition_publication(client, db_mode):
    from app.services import academic_calendar_service as calendar

    headers = _hdr(client, 'school_admin01')
    current = _term(client, headers).json()['data']['termId']
    draft = _term(client, headers, no=2).json()['data']['termId']
    tenant_id = 1000000000000000001
    enrolled = calendar.enroll_term(int(current), tenant_id=tenant_id)
    validated = calendar.transition(int(current), 'VALIDATED', reason='学期记录验收', expected_version=enrolled['version'], tenant_id=tenant_id)
    calendar.transition(int(current), 'ACTIVE', reason='学期记录验收', expected_version=validated['version'], tenant_id=tenant_id)
    published = client.post(f'{BASE}/terms/{draft}/publish', headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()['data']['isCurrent'] is False
    log = client.get(f'{BASE}/terms/switch-log', headers=headers)
    assert log.status_code == 200, log.text
    rows = log.json()['data']['items']
    assert any(r['action'] == 'ACTIVATE' and r['toTermId'] == current for r in rows)
    assert all(r['toTermId'] != draft for r in rows)
