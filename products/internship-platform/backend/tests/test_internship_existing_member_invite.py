"""Existing enterprise accounts join another round without credential or role changes."""
from datetime import datetime, timedelta
import uuid

from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import EmpCompany, Tenant, User
from app.models.internship_enterprise_portal import InternshipCampaignEnterprise, InternshipEnterpriseMember, InternshipEnterpriseAccessGrant
from tests.test_internship_student import TID, _mk_batch

SCHOOL = '/api/v1/internship/recruitment-campaigns'
PORTAL = '/api/v1/internship/enterprise-portal'


def _fixture(client, headers, *, windows=None):
    with get_sessionmaker()() as db:
        tenant = db.get(Tenant, TID)
        if tenant is None:
            tenant = Tenant(id=TID, tenant_code='existing-invite-fixture', school_name='虚构邀请验收学校', status='ACTIVE')
            db.add(tenant); db.flush()
        code = tenant.tenant_code
        company = EmpCompany(tenant_id=TID, name='虚构往期企业', credit_code=uuid.uuid4().hex[:18],
                             status='ACTIVE', coop_status='ACTIVE', qualification_status='PASSED',
                             access_valid_until=datetime.utcnow() + timedelta(days=100))
        db.add(company); db.commit(); company_id = str(company.id)
    batch = _mk_batch(client, headers)
    round_no = 0

    def campaign():
        nonlocal round_no
        round_no += 1
        now = datetime.utcnow()
        response = client.post(SCHOOL, headers=headers, json={
            'batchId': batch, 'campaignCode': uuid.uuid4().hex, 'campaignName': '虚构往期企业新轮测试', 'roundNo': round_no,
            'inviteStartAt': (now - timedelta(days=1)).isoformat() + 'Z',
            'inviteEndAt': (now + timedelta(days=5)).isoformat() + 'Z',
            'enterpriseAccessEndAt': (now + timedelta(days=10)).isoformat() + 'Z',
            **(windows or {}),
        })
        assert response.status_code == 200, response.json()
        data = response.json()['data']
        opened = client.post(f"{SCHOOL}/{data['id']}/open", headers=headers, json={'expectedVersion': data['version']})
        assert opened.status_code == 200, opened.json()
        return data['id']

    login_name = 'invite-' + uuid.uuid4().hex[:14]
    body = {'companyId': company_id, 'loginName': login_name, 'realName': '虚构联系人', 'phone': '13800001234', 'memberRole': 'HR'}
    first = campaign()
    invite = client.post(f'{SCHOOL}/{first}/enterprises/invite', headers=headers, json=body)
    assert invite.status_code == 200
    token = invite.json()['data']['inviteToken']
    password = 'Synthetic-Only-2026!'
    activate = client.post(PORTAL + '/auth/invite/accept', json={'tenantCode': code, 'token': token, 'phone': body['phone'], 'password': password})
    assert activate.status_code == 200, activate.json()
    auth = {'Authorization': 'Bearer ' + activate.json()['data']['accessToken']}
    return code, body, password, campaign, invite.json()['data']['memberId'], auth


def test_existing_member_accepts_new_round_without_password_role_or_session_change(client, auth_headers, db_mode):
    code, body, password, campaign, member_id, existing_auth = _fixture(client, auth_headers)
    with get_sessionmaker()() as db:
        member = db.get(InternshipEnterpriseMember, int(member_id)); user = db.get(User, member.user_id)
        original = (member.member_role, member.version, user.version, user.password_hash)
    second = campaign()
    invited = client.post(f'{SCHOOL}/{second}/enterprises/invite', headers=auth_headers, json={**body, 'memberRole': 'COMPANY_ADMIN', 'inviteSource': 'REUSE'})
    assert invited.status_code == 200, invited.json()
    data = invited.json()['data']; token = data['inviteToken']
    assert data['inviteMode'] == 'EXISTING_MEMBER' and data['memberRole'] == 'HR'
    assert data['expiresAt'].endswith('Z')
    inspect = client.post(PORTAL + '/auth/invite/inspect', json={'tenantCode': code, 'token': token})
    assert inspect.status_code == 200 and inspect.json()['data']['inviteMode'] == 'EXISTING_MEMBER'
    # The existing session survives issuance; the new round is still not usable.
    assert client.get(PORTAL + '/campaigns', headers=existing_auth).status_code == 200
    assert client.get(PORTAL + '/context', headers=existing_auth, params={'campaignId': second}).status_code in {403, 409}
    reset_attempt = client.post(PORTAL + '/auth/invite/accept', json={'tenantCode': code, 'token': token, 'phone': body['phone'], 'password': 'Must-Not-Replace-2026!'})
    assert reset_attempt.status_code == 401
    accepted = client.post(PORTAL + '/auth/invite/accept-existing', headers=existing_auth, json={'tenantCode': code, 'token': token})
    assert accepted.status_code == 200, accepted.json()
    assert accepted.json()['data']['campaignId'] == second
    assert client.get(PORTAL + '/context', headers=existing_auth, params={'campaignId': second}).status_code == 200
    replay = client.post(PORTAL + '/auth/invite/accept-existing', headers=existing_auth, json={'tenantCode': code, 'token': token})
    assert replay.status_code == 401
    login = client.post(PORTAL + '/auth/login', json={'tenantCode': code, 'loginName': body['loginName'], 'password': password})
    assert login.status_code == 200
    with get_sessionmaker()() as db:
        member = db.get(InternshipEnterpriseMember, int(member_id)); user = db.get(User, member.user_id)
        assert (member.member_role, member.version, user.version, user.password_hash) == original
        grant = db.scalar(select(InternshipEnterpriseAccessGrant).where(InternshipEnterpriseAccessGrant.member_id == member.id, InternshipEnterpriseAccessGrant.campaign_id == int(second)))
        assert grant and grant.company_id == int(body['companyId']) and grant.status == 'ACTIVE'


def test_existing_invite_wrong_member_reissue_expiry_and_revocation_fail_closed(client, auth_headers, db_mode):
    code, body, _, campaign, member_id, own = _fixture(client, auth_headers)
    _, _, _, _, _, other = _fixture(client, auth_headers)
    second = campaign()
    def issue():
        response = client.post(f'{SCHOOL}/{second}/enterprises/invite', headers=auth_headers, json=body)
        assert response.status_code == 200, response.json()
        return response.json()['data']['inviteToken']
    old, token = issue(), issue()
    assert client.post(PORTAL + '/auth/invite/inspect', json={'tenantCode': code, 'token': old}).status_code == 401
    wrong = client.post(PORTAL + '/auth/invite/accept-existing', headers=other, json={'tenantCode': code, 'token': token})
    assert wrong.status_code == 401
    assert client.post(PORTAL + '/auth/invite/accept-existing', json={'tenantCode': code, 'token': token}).status_code == 401
    with get_sessionmaker()() as db:
        member = db.get(InternshipEnterpriseMember, int(member_id)); member.invite_expires_at = datetime.utcnow() - timedelta(seconds=5); db.commit()
    assert client.post(PORTAL + '/auth/invite/accept-existing', headers=own, json={'tenantCode': code, 'token': token}).status_code == 401
    token = issue()
    with get_sessionmaker()() as db:
        participation = db.scalar(select(InternshipCampaignEnterprise).where(InternshipCampaignEnterprise.campaign_id == int(second), InternshipCampaignEnterprise.company_id == int(body['companyId'])))
        participation.status = 'REVOKED'; db.commit()
    assert client.post(PORTAL + '/auth/invite/accept-existing', headers=own, json={'tenantCode': code, 'token': token}).status_code == 401


def test_existing_account_cannot_be_reactivated_or_bound_to_another_company_by_password_reset(client, auth_headers, db_mode):
    code, body, _, campaign, member_id, _ = _fixture(client, auth_headers)
    _, other_body, _, other_campaign, _, _ = _fixture(client, auth_headers)
    foreign_round = other_campaign()
    wrong_membership = client.post(f'{SCHOOL}/{foreign_round}/enterprises/invite', headers=auth_headers,
                                  json={**body, 'companyId': other_body['companyId']})
    assert wrong_membership.status_code == 409
    second = campaign()
    issued = client.post(f'{SCHOOL}/{second}/enterprises/invite', headers=auth_headers, json=body).json()['data']
    with get_sessionmaker()() as db:
        member = db.get(InternshipEnterpriseMember, int(member_id)); original = db.get(User, member.user_id).password_hash
        member.status = 'INVITED'; db.commit()  # Historical pending member pointing at an already active user.
    reset_attempt = client.post(PORTAL + '/auth/invite/accept', json={
        'tenantCode': code, 'token': issued['inviteToken'], 'phone': body['phone'], 'password': 'Do-Not-Change-2026!',
    })
    assert reset_attempt.status_code == 401
    with get_sessionmaker()() as db:
        member = db.get(InternshipEnterpriseMember, int(member_id))
        assert db.get(User, member.user_id).password_hash == original


def test_campaign_duplicate_round_and_code_return_correctable_validation_errors(client, auth_headers, db_mode):
    batch = _mk_batch(client, auth_headers)
    body = {'batchId': batch, 'campaignCode': uuid.uuid4().hex, 'campaignName': '虚构唯一约束验收', 'roundNo': 1}
    first = client.post(SCHOOL, headers=auth_headers, json=body)
    assert first.status_code == 200
    duplicate_round = client.post(SCHOOL, headers=auth_headers, json={**body, 'campaignCode': uuid.uuid4().hex})
    assert duplicate_round.status_code == 400 and '轮次' in duplicate_round.json()['message']
    duplicate_code = client.post(SCHOOL, headers=auth_headers, json={**body, 'roundNo': 2})
    assert duplicate_code.status_code == 400 and '编码' in duplicate_code.json()['message']
    second = client.post(SCHOOL, headers=auth_headers, json={**body, 'roundNo': 2, 'campaignCode': uuid.uuid4().hex}).json()['data']
    update = client.put(f"{SCHOOL}/{second['id']}", headers=auth_headers, json={'expectedVersion': second['version'], 'roundNo': 1})
    assert update.status_code == 400
    reread = client.get(f"{SCHOOL}/{second['id']}", headers=auth_headers).json()['data']
    assert reread['roundNo'] == 2 and reread['version'] == second['version']


def test_concurrent_invite_reissue_and_accept_leave_one_consistent_participation(client, auth_headers, db_mode):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    code, body, _, campaign, member_id, own = _fixture(client, auth_headers)
    second = campaign()
    issued = client.post(f'{SCHOOL}/{second}/enterprises/invite', headers=auth_headers, json=body).json()['data']
    barrier = Barrier(2)
    def accept():
        barrier.wait(timeout=10)
        return client.post(PORTAL + '/auth/invite/accept-existing', headers=own, json={'tenantCode': code, 'token': issued['inviteToken']})
    def reissue():
        barrier.wait(timeout=10)
        return client.post(f'{SCHOOL}/{second}/enterprises/invite', headers=auth_headers, json=body)
    with ThreadPoolExecutor(max_workers=2) as executor:
        accepting, reissuing = executor.submit(accept), executor.submit(reissue)
        accept_result, reissue_result = accepting.result(timeout=30), reissuing.result(timeout=30)
    assert (accept_result.status_code, reissue_result.status_code) in {(200, 409), (401, 200)}
    with get_sessionmaker()() as db:
        participation = db.scalar(select(InternshipCampaignEnterprise).where(InternshipCampaignEnterprise.campaign_id == int(second), InternshipCampaignEnterprise.company_id == int(body['companyId'])))
        grants = db.scalars(select(InternshipEnterpriseAccessGrant).where(InternshipEnterpriseAccessGrant.campaign_id == int(second), InternshipEnterpriseAccessGrant.member_id == int(member_id))).all()
        assert participation.status == ('ACCEPTED' if accept_result.status_code == 200 else 'INVITED')
        assert len(grants) == (1 if accept_result.status_code == 200 else 0)
