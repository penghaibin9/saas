"""Per-application material counts/page boundaries must match on PC and mobile."""
from test_affairs_aid import TID, _seed, _hdr, _open_batch, _apply
from test_affairs_four_end_hardening import _set_ctx, _clear_ctx


def test_aid_material_context_uses_readable_levels():
    from types import SimpleNamespace
    from app.modules.student_affairs.services.affairs_material_center_service import _biz_subtitle_and_period
    assert _biz_subtitle_and_period('AID', SimpleNamespace(final_level='SPECIAL', apply_level='GENERAL')) == ('特别困难', '')
    assert _biz_subtitle_and_period('AID', SimpleNamespace(apply_level='GENERAL')) == ('一般困难', '')
    assert _biz_subtitle_and_period('AID', SimpleNamespace(apply_level='INTERNAL_UNKNOWN')) == ('等级待确认', '')


def test_material_center_scopes_business_before_paging_and_counting(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models.affairs_operations import AffairsMaterialRequirement
    from app.modules.student_affairs.services import affairs_material_center_service as center
    ids = _seed(db_mode); headers = _hdr(client, 'school_admin01')
    batch = _open_batch(client, headers)
    apply_id = int(_apply(client, headers, batch, ids['sa']).json()['data']['applyId'])
    other_id = int(_apply(client, headers, batch, ids['sb']).json()['data']['applyId'])
    with get_sessionmaker()() as db:
        for biz, biz_id, student_id, count in [('AID', apply_id, ids['sa'], 25), ('AID', other_id, ids['sb'], 3), ('LEAVE', apply_id, ids['sa'], 2)]:
            for index in range(count):
                db.add(AffairsMaterialRequirement(tenant_id=TID, student_id=student_id,
                    biz_type=biz, biz_id=biz_id, item_code=f'CONTEXT_{index}', item_name=f'验收材料{index}',
                    status='MISSING', sensitivity_level='HIGHLY_SENSITIVE' if biz == 'AID' else 'PERSONAL',
                    material_scope='AID_RESTRICTED' if biz == 'AID' else 'STUDENT_SELF'))
        db.commit()
    found = []
    for page, count in [(1, 20), (2, 5)]:
        response = client.get('/api/v1/student-affairs/material-center', headers=headers,
            params={'bizType': 'AID', 'bizId': apply_id, 'page': page, 'pageSize': 20})
        assert response.status_code == 200, response.text
        data = response.json()['data']
        assert data['total'] == data['summary']['total'] == data['summary']['missing'] == 25
        assert len(data['items']) == count
        assert all(x['bizType'] == 'AID' and int(x['bizId']) == apply_id for x in data['items'])
        found.extend(x['requirementId'] for x in data['items'])
    assert len(set(found)) == 25
    focused = client.get('/api/v1/student-affairs/material-requirements', headers=headers,
        params={'requirementId':found[-1], 'page':1, 'pageSize':20}).json()['data']
    assert focused['total'] == 1
    assert focused['items'][0]['requirementId'] == found[-1]
    mobile = client.get('/api/v1/student-affairs/material-requirements', headers=headers,
        params={'bizType': 'AID', 'bizId': apply_id, 'page': 2, 'pageSize': 20}).json()['data']
    assert mobile['total'] == 25 and len(mobile['items']) == 5
    user = {'userId': 'u-A001', 'studentNo': 'A001', 'realName': '甲一',
        'userType': 'STUDENT', 'currentRoleCode': 'STUDENT', 'tenantId': str(TID)}
    _set_ctx(user)
    try:
        rows, total = center.list_my_requirements(user, biz_type='AID', biz_id=apply_id, page=2, page_size=20)
        assert total == 25 and len(rows) == 5
        rows, total = center.list_my_requirements(user, biz_type='AID', biz_id=other_id)
        assert rows == [] and total == 0
    finally:
        _clear_ctx()
