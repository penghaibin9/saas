"""Orientation completion and the student's next action must follow canonical facts."""
import pytest

from app.student_portal.services import home_projection_service as home


@pytest.mark.parametrize('status,expected', [
    ('CHECKED_IN', 'IN_PROGRESS'), ('REPORTED', 'IN_PROGRESS'),
    ('DONE', 'IN_PROGRESS'), ('COLLEGE_CONFIRMED', 'COMPLETED'),
])
def test_orientation_completion_requires_college_confirmation(status, expected):
    assert home._lifecycle_status('orientation', True, status) == expected


def test_home_keeps_unfinished_orientation_visible_without_inventing_todo(monkeypatch):
    orientation = {
        'hasData': True, 'orientationStudentId': '9007199254740999',
        'reportStatus': 'CHECKED_IN', 'stage': 'ORIENTATION',
        'qualification': {'blockers': [{'code': 'MATERIAL_MISSING'}]},
    }
    base = {'hasData': True, 'orientation': orientation, 'domains': [
        {'key': 'orientation', 'hasData': True, 'status': 'CHECKED_IN'},
    ]}
    monkeypatch.setattr(home.stu, 'me_overview', lambda *a, **kw: base)
    monkeypatch.setattr(home, '_todo_items', lambda *a: ([], 0))
    monkeypatch.setattr(home, '_notice_items', lambda *a: ([], {'unread': 0}))
    monkeypatch.setattr(home, '_tid', lambda: 1000000000000000001)
    monkeypatch.setattr(home.portal_cfg, 'get_config', lambda *a: {'modules': {'orientation': True}})
    monkeypatch.setattr(home.freshness, 'projection_version', lambda *a: 'v1')
    result = home.build_home_v2({})
    assert result['summary']['todoCount'] == 0 and result['todos'] == []
    assert result['lifecycle'][0]['status'] == 'IN_PROGRESS'
    assert result['alerts'][0]['domain'] == 'orientation'
    assert result['nextAction']['target']['path'] == '/orientation'
    assert result['nextAction']['recordId'] == '9007199254740999'
    assert result['nextAction']['allowedActions'] == ['OPEN']

    # Other urgent sections must not display an orientation button under their warning.
    base['alerts'] = [{'domain': 'academic', 'title': '学业事项待跟进'}]
    result = home.build_home_v2({})
    assert result['alerts'] == base['alerts'] and result['nextAction'] is None
    base['alerts'] = []
    other_action = {'target': {'path': '/campus-service'}, 'label': '办理请假'}
    monkeypatch.setattr(home, '_todo_items', lambda *a: ([{'module': 'leave', 'action': other_action}], 1))
    result = home.build_home_v2({})
    assert result['nextAction'] == other_action and result['alerts'] == []
    base['alerts'] = [{'domain': 'orientation', 'title': '迎新材料待补正'}]
    result = home.build_home_v2({})
    assert result['nextAction']['target']['path'] == '/orientation'
    assert result['todos'][0]['action'] == other_action
    base['alerts'] = []
    monkeypatch.setattr(home, '_todo_items', lambda *a: ([], 0))

    orientation['reportStatus'] = 'COLLEGE_CONFIRMED'
    base['domains'][0]['status'] = 'COLLEGE_CONFIRMED'
    result = home.build_home_v2({})
    assert result['lifecycle'][0]['status'] == 'COMPLETED'
    assert result['alerts'] == [] and result['nextAction'] is None


def test_orientation_followup_respects_module_visibility_and_stopped_state():
    base = {'orientation': {'hasData': True, 'reportStatus': 'CHECKED_IN'}}
    assert home._orientation_followup(base, []) == (None, None)
    enabled = home._quick_services({'orientation': True})
    base['orientation']['stage'] = 'CANCELLED'
    assert home._orientation_followup(base, enabled) == (None, None)
    base['orientation']['stage'] = 'DEFERRED'
    alert, action = home._orientation_followup(base, enabled)
    assert '延期' in alert['title'] and action['target']['path'] == '/orientation'


def test_student_steps_only_show_enabled_frozen_flow(client, db_mode):
    from test_orientation_o3_self_service import _seed_o3, _token, TID
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent, OrientationBatch, OrientationFlowStep
    from app.services.orientation_flow_service import ensure_student_steps
    ids = _seed_o3(db_mode)
    with get_sessionmaker()() as db:
        student = db.get(OrientationStudent, ids['orientationId'])
        batch = db.get(OrientationBatch, student.batch_id)
        db.add(OrientationFlowStep(
            tenant_id=TID, flow_version_id=batch.flow_version_id, step_key='FINANCE',
            step_name='财务核验', enabled=False, required=False, sort_order=99,
        ))
        db.flush()
        ensure_student_steps(db, student, status_source='PROCESS_FACT')
        db.commit()
    headers = _token(user_id=ids['userId'], student_id=ids['profileId'],
                     student_no=ids['studentNo'], name=ids['name'])
    for prefix in ('/api/v1/portal', '/api/v1/mobile'):
        response = client.get(prefix + '/orientation/my', headers=headers)
        assert response.status_code == 200, response.text
        mine = response.json()['data']
        assert mine['orientationStudentId'] == str(ids['orientationId'])
        assert [step['key'] for step in mine['steps']] == ['INFO', 'MATERIAL', 'CHECKIN']
        assert [step['label'] for step in mine['steps']] == ['信息采集', '材料上传', '现场报到']
        assert all(step['status'] for step in mine['steps'])
