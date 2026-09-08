from types import SimpleNamespace

from app.services import affairs_student_contract_security_guard as guard
from app.services.mobile_action_service import build_message_action
from app.student_portal.services.action_projection_service import build_message_action as student_pc_action
from app.services.todo_route_registry import resolve_todo_route


def test_material_notice_keeps_exact_requirement_in_producer_and_both_student_projections():
    calls = []
    outbox = SimpleNamespace(emit_message_event=lambda db, **kwargs: calls.append(kwargs))
    guard._secure_message_producers(outbox)
    outbox.emit_message_event(None, source_module='student-affairs', source_biz_type='AID',
        source_biz_id=45, action_key='student.affairs.material', action_params={'materialRequirementId':'89'})
    notice = calls[0]
    assert notice['action_key'] == 'student.affairs.material'
    item = {'actionKey':notice['action_key'], 'actionParams':notice['action_params'], 'bizType':'AID'}
    guard._canonical_message_action(item)
    assert item['actionKey'] == 'student.affairs.material'
    mini = build_message_action(item['actionKey'], item['actionParams'])
    assert mini['target']['path'] == '/pages/student/affairs/index'
    assert mini['target']['query']['materialRequirementId'] == '89'
    pc = student_pc_action(item['actionKey'], item['actionParams'])
    assert pc['target']['path'] == '/materials'
    assert pc['target']['query']['materialRequirementId'] == '89'


def test_teacher_material_todo_resolves_to_exact_requirement_in_both_clients():
    for client, path in [('pc','/admin/student-affairs/material-operations'), ('teacherMini','/pages/teacher/affairs/index')]:
        target = resolve_todo_route('MATERIAL_REVIEW','89',client=client)
        assert target['path'] == path and target['query']['recordId'] == '89'
        assert target['exact'] and target['focusMode'] == 'LIST_FOCUS'
    assert resolve_todo_route('MATERIAL_REVIEW','89',client='studentMini') is None
