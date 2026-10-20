"""Historical result links must never drift to a current round or another student."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import InternshipRecord, StudentAccountLink, User
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_student_volunteer_result_service as svc
from tests.test_internship_school_volunteers import _seed, TID, ADMIN


def own_group():
    ids = _seed()
    with get_sessionmaker()() as db:
        group = db.get(InternshipVolunteerGroup, ids['0'])
        user = User(tenant_id=TID, login_name=uuid4().hex, real_name='虚构结果读者',
                    password_hash='unused-test-account', user_type='STUDENT', status='ACTIVE')
        db.add(user); db.flush()
        db.add(StudentAccountLink(tenant_id=TID, student_id=group.student_id,
                                 user_id=user.id, link_status='ACTIVE'))
        db.commit()
        return ids, {'userId': f'db-{user.id}', 'userType': 'STUDENT'}


def test_closed_round_is_pinned_and_read_does_not_release_expired_lock(db_mode):
    ids, user = own_group()
    set_tenant({'tenantId': str(TID)})
    try:
        with get_sessionmaker()() as db:
            campaign = db.get(InternshipRecruitmentCampaign, ids['campaign'])
            campaign.status = 'CLOSED'
            db.add(InternshipRecruitmentCampaign(tenant_id=TID, batch_id=ids['batch'],
                campaign_code=uuid4().hex, campaign_name='后来开启的新招聘季', round_no=2, status='OPEN'))
            group = db.get(InternshipVolunteerGroup, ids['0'])
            group.status = 'LOCKED'
            group.teacher_confirm_deadline = datetime.utcnow() - timedelta(days=1)
            db.commit()
        result = svc.get_my_result(group_id=ids['0'], user=user)
        assert result['campaignId'] == str(ids['campaign'])
        assert result['campaignStatus'] == 'CLOSED'
        assert result['status'] == 'LOCKED' and result['lockExpired'] is True
        assert len(result['items']) == 1  # excludes legacy, campaign-null application
        assert 'reviewComment' not in result['items'][0]
        assert 'decisionHistory' not in result and 'material' not in result
        with get_sessionmaker()() as db:
            group = db.get(InternshipVolunteerGroup, ids['0'])
            assert group.status == 'LOCKED' and group.version == 0
    finally:
        set_tenant(None)


def test_result_ownership_role_and_canonical_record_fail_closed(db_mode):
    ids, user = own_group()
    set_tenant({'tenantId': str(TID)})
    try:
        for group_id, actor, expected in ((ids['1'], user, 404), (ids['0'], ADMIN, 403)):
            with pytest.raises(AppException) as error:
                svc.get_my_result(group_id=group_id, user=actor)
            assert error.value.http_status == expected
        with get_sessionmaker()() as db:
            group = db.get(InternshipVolunteerGroup, ids['0'])
            db.get(InternshipRecord, group.record_id).batch_id = ids['batch'] + 999
            db.commit()
        with pytest.raises(AppException) as error:
            svc.get_my_result(group_id=ids['0'], user=user)
        assert error.value.http_status == 404
        set_tenant({'tenantId': str(TID + 1)})
        with pytest.raises(AppException) as error:
            svc.get_my_result(group_id=ids['0'], user=user)
        assert error.value.http_status == 403
    finally:
        set_tenant(None)


@pytest.mark.parametrize('prefix', ['/api/v1/portal/internship', '/api/v1/mobile/internship'])
def test_pc_and_mobile_result_facades_ignore_unrelated_batch_selection(client, auth_headers, db_mode, prefix):
    from app.core.security import get_current_user
    ids, user = own_group()
    previous = client.app.dependency_overrides.get(get_current_user)
    client.app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get(f"{prefix}/volunteer-results/{ids['0']}",
                              headers={**auth_headers, 'X-Internship-Batch-Id': '999999'})
        assert response.status_code == 200, response.json()
        assert response.json()['data']['batchId'] == str(ids['batch'])
        denied = client.get(f"{prefix}/volunteer-results/{ids['1']}", headers=auth_headers)
        assert denied.status_code == 404, denied.json()
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_current_user, None)
        else:
            client.app.dependency_overrides[get_current_user] = previous
