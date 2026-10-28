"""Campaign choices mirror member-specific authority without losing collaboration handoff."""
from datetime import datetime, timedelta
import pytest

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise, InternshipEnterpriseAccessGrant, InternshipRecruitmentCampaign,
)
from tests.test_internship_existing_member_invite import _fixture, PORTAL


def test_campaign_list_matches_recruitment_and_independent_collaboration_access(client, auth_headers, db_mode):
    _, body, _, _, member_id, auth = _fixture(client, auth_headers)
    with get_sessionmaker()() as db:
        grant = db.scalar(select(InternshipEnterpriseAccessGrant).where(InternshipEnterpriseAccessGrant.member_id == int(member_id)))
        grant_id, campaign_id, batch_id, tenant_id = grant.id, grant.campaign_id, grant.batch_id, grant.tenant_id

    def check(access_status, allowed, collab=False):
        response = client.get(PORTAL + '/campaigns', headers=auth)
        assert response.status_code == 200
        row = next(item for item in response.json()['data'] if int(item['id']) == campaign_id)
        assert row['recruitmentAccessStatus'] == access_status
        assert row['recruitmentAvailable'] is allowed
        assert row['collaborationAvailable'] is collab
        context = client.get(PORTAL + '/context', params={'campaignId': campaign_id}, headers=auth)
        assert context.status_code == (200 if allowed else 403)
        return row

    check('ACTIVE', True)
    with get_sessionmaker()() as db:
        db.get(InternshipRecruitmentCampaign, campaign_id).status = 'CLOSED'; db.commit()
    assert check('ACTIVE', True)['status'] == 'CLOSED'
    now = datetime.utcnow()
    for status, start, end, deleted, expected in [
        ('ACTIVE', now + timedelta(days=1), now + timedelta(days=2), False, 'NOT_STARTED'),
        ('ACTIVE', now - timedelta(days=2), now - timedelta(days=1), False, 'EXPIRED'),
        ('REVOKED', now - timedelta(days=1), now + timedelta(days=2), False, 'REVOKED'),
        ('ACTIVE', now - timedelta(days=1), now + timedelta(days=2), True, 'MISSING'),
    ]:
        with get_sessionmaker()() as db:
            grant = db.get(InternshipEnterpriseAccessGrant, grant_id)
            grant.status, grant.valid_from, grant.valid_until, grant.is_deleted = status, start, end, deleted
            db.commit()
        check(expected, False)

    # A grant for another member cannot make this account's company participation enterable.
    _, _, _, _, other_member, _ = _fixture(client, auth_headers)
    with get_sessionmaker()() as db:
        grant = db.get(InternshipEnterpriseAccessGrant, grant_id)
        grant.is_deleted = False; grant.member_id = int(other_member); db.commit()
    check('MISSING', False)
    with get_sessionmaker()() as db:
        grant = db.get(InternshipEnterpriseAccessGrant, grant_id)
        grant.member_id = int(member_id); grant.batch_id = None; db.commit()
    check('MISSING', False)

    with get_sessionmaker()() as db:
        grant = db.get(InternshipEnterpriseAccessGrant, grant_id); grant.batch_id = batch_id
        participation = db.scalar(select(InternshipCampaignEnterprise).where(
            InternshipCampaignEnterprise.campaign_id == campaign_id,
            InternshipCampaignEnterprise.company_id == int(body['companyId']),
        ))
        participation.status = 'REVOKED'
        collab = InternshipEnterpriseAccessGrant(tenant_id=tenant_id, member_id=int(member_id),
            company_id=int(body['companyId']), grant_type='INTERNSHIP_COLLAB', batch_id=batch_id,
            valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=2), status='ACTIVE')
        db.add(collab); db.commit(); collab_id = collab.id
    check('ACTIVE', False, True)
    context = client.get(PORTAL + '/collaboration-context', headers=auth, params={'batchId': batch_id})
    assert context.status_code == 200
    assert context.json()['data']['capabilities'] == {'recruitmentWrite': False, 'internshipCollab': True}
    with get_sessionmaker()() as db:
        db.get(InternshipEnterpriseAccessGrant, collab_id).status = 'REVOKED'; db.commit()
    check('ACTIVE', False, False)
    assert client.get(PORTAL + '/collaboration-context', headers=auth, params={'batchId': batch_id}).status_code == 403


@pytest.mark.parametrize('campaign_status', ['FROZEN', 'CLOSED', 'ARCHIVED'])
def test_historical_position_reads_remain_available_but_all_enterprise_writes_are_rejected(client, auth_headers, db_mode, campaign_status):
    _, _, _, _, member_id, auth = _fixture(client, auth_headers)
    with get_sessionmaker()() as db:
        grant = db.scalar(select(InternshipEnterpriseAccessGrant).where(InternshipEnterpriseAccessGrant.member_id == int(member_id)))
        campaign_id = grant.campaign_id
        campaign = db.get(InternshipRecruitmentCampaign, campaign_id)
        campaign.position_submit_start_at = datetime.utcnow() - timedelta(days=1)
        campaign.position_submit_end_at = datetime.utcnow() + timedelta(days=1)
        db.commit()
    params = {'campaignId': campaign_id}
    payload = {'title': '虚构历史只读岗位', 'headcount': 2, 'workLocation': '虚构园区',
               'workAddress': '虚构园区1号', 'workContent': '设备调试辅助', 'weeklyHours': 40, 'salaryRange': '3000元/月'}
    draft_response = client.post(PORTAL + '/positions', headers=auth, params=params, json=payload)
    assert draft_response.status_code == 200, draft_response.json()
    draft = draft_response.json()['data']
    pending = client.post(PORTAL + '/positions', headers=auth, params=params, json=payload).json()['data']
    submitted = client.post(f"{PORTAL}/positions/{pending['id']}/submit", headers=auth, params=params, json={'expectedVersion': pending['version']})
    assert submitted.status_code == 200, submitted.json()
    pending = submitted.json()['data']
    with get_sessionmaker()() as db:
        db.get(InternshipRecruitmentCampaign, campaign_id).status = campaign_status; db.commit()
    context = client.get(PORTAL + '/context', headers=auth, params=params)
    assert context.status_code == 200 and context.json()['data']['capabilities']['recruitmentWrite'] is False
    dashboard = client.get(PORTAL + '/dashboard', headers=auth, params=params)
    assert dashboard.status_code == 200
    assert not any(task['objectId'] == draft['id'] for task in dashboard.json()['data']['tasks']
                   if task['objectType'] == 'INTERNSHIP_POSITION')
    assert client.post(PORTAL + '/positions', headers=auth, params=params, json=payload).status_code == 409
    assert client.put(f"{PORTAL}/positions/{draft['id']}", headers=auth, params=params,
                      json={'title': '禁止覆盖', 'expectedVersion': draft['version']}).status_code == 409
    assert client.post(f"{PORTAL}/positions/{draft['id']}/submit", headers=auth, params=params,
                       json={'expectedVersion': draft['version']}).status_code == 409
    assert client.post(f"{PORTAL}/positions/{pending['id']}/withdraw", headers=auth, params=params,
                       json={'expectedVersion': pending['version']}).status_code == 409
    # School correction must not reopen enterprise work in a historical campaign.
    assert client.post(f"/api/v1/internship/positions/{pending['id']}/status", headers=auth_headers,
                       json={'action': 'RETURN', 'expectedVersion': pending['version'],
                             'reason': '历史招聘季不可退回补正'}).status_code == 409
    for original in (draft, pending):
        detail = client.get(f"{PORTAL}/positions/{original['id']}", headers=auth, params=params)
        assert detail.status_code == 200
        actual = detail.json()['data']
        assert (actual['title'], actual['version'], actual['status']) == (original['title'], original['version'], original['status'])
