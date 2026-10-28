from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.api.v1 import teacher_mobile_workbench as workbench
from app.core.exceptions import AppException
from app.core.timeutil import utc_now_naive
from app.modules.internship.services import internship_school_volunteer_service as volunteers


GROUP = '9007199254740993101'
BATCH = '9007199254740993102'


def message(**changes):
    return SimpleNamespace(**dict({
        'id': 41, 'action_key': 'INTERNSHIP_TEACHER_CONFIRM_ACCEPT_INTENT',
        'action_params_json': {'campaignId': '31', 'volunteerGroupId': GROUP},
        'source_biz_id': 999, 'status': 'UNREAD', 'read_at': None, 'version': 9,
        'expire_at': None, 'delivery_status': 'DELIVERED',
    }, **changes))


def setup_target(monkeypatch, row):
    queries, groups = [], []

    class Database:
        def scalar(self, query):
            queries.append(query)
            return row

        def commit(self):
            pytest.fail('读取原单不能修改消息已读状态')

    @contextmanager
    def session():
        yield Database()

    def get_group(**kwargs):
        groups.append(kwargs)
        return {'id': GROUP, 'campaignId': '31', 'batchId': BATCH}

    monkeypatch.setattr(workbench, 'session', session)
    monkeypatch.setattr(workbench, '_tid', lambda: 8900)
    monkeypatch.setattr(volunteers, 'get_group', get_group)
    return queries, groups


@pytest.mark.parametrize('action', sorted(workbench._VOLUNTEER_MESSAGE_ACTIONS))
def test_target_uses_owned_message_params_and_authoritative_group_without_read_write(monkeypatch, action):
    row = message(action_key=action)
    queries, groups = setup_target(monkeypatch, row)
    user = {'userId': 'db-811', 'activeContextId': 'mentor-context'}
    result = workbench.message_target(41, user)['data']
    assert result == {'messageId': '41', 'pageKey': 'TEACHER_INTERNSHIP_VOLUNTEERS',
                      'batchId': BATCH, 'campaignId': '31', 'groupId': GROUP}
    assert groups == [{'campaign_id': 31, 'group_id': int(GROUP), 'user': user}]
    params = set(queries[0].compile().params.values())
    assert {41, 8900, 811, 'GLOBAL', 'mentor-context', 'internship'} <= params
    sql = str(queries[0])
    assert 'receiver_user_id' in sql and 'receiver_id' in sql and 'is_deleted IS false' in sql
    assert row.status == 'UNREAD' and row.read_at is None and row.version == 9


@pytest.mark.parametrize('changes', [
    {'action_key': 'UNKNOWN_ACTION'}, {'status': 'WITHDRAWN'}, {'delivery_status': 'CANCELLED'},
    {'expire_at': utc_now_naive() - timedelta(seconds=1)}, {'action_params_json': {}},
    {'action_params_json': {'campaignId': '31', 'volunteerGroupId': 'https://other.invalid'}},
    {'action_params_json': {'campaignId': '31', 'volunteerGroupId': True}},
])
def test_unsupported_or_incomplete_message_never_guesses_from_source_business_id(monkeypatch, changes):
    _, groups = setup_target(monkeypatch, message(**changes))
    with pytest.raises(AppException):
        workbench.message_target(41, {'userId': '811'})
    assert groups == []


def test_missing_owned_message_and_revoked_group_scope_are_refused(monkeypatch):
    setup_target(monkeypatch, None)
    with pytest.raises(AppException):
        workbench.message_target(41, {'userId': '811'})
    setup_target(monkeypatch, message())

    def denied(**_):
        raise AppException('NO_PERMISSION', '当前指导范围无权查看原单', http_status=403)

    monkeypatch.setattr(volunteers, 'get_group', denied)
    with pytest.raises(AppException, match='当前指导范围'):
        workbench.message_target(41, {'userId': '811'})


def test_message_target_button_requires_current_view_permission_without_changing_message():
    row = message(rendered_content_plain='待确认志愿', content='', priority='NORMAL',
                  rendered_title='原消息', title='', created_at=None, source_module='internship',
                  require_ack=False, ack_at=None, category='TODO', message_type='TODO')
    assert workbench._msg(row)['hasBusinessTarget'] is False
    assert workbench._msg(row, can_view_target=True)['hasBusinessTarget'] is True
    assert workbench._msg(row, can_view_target=False)['hasBusinessTarget'] is False
    assert row.status == 'UNREAD' and row.read_at is None and row.version == 9
