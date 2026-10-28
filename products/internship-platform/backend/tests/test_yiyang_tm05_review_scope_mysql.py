"""Non-cleaning MySQL checks of the real role routes, counts and child ownership."""
import os
import pytest
from sqlalchemy import func, select
from app.db.session import get_sessionmaker
from app.models import InternshipApplication, InternshipChangeRequest, InternshipRecord, StudentAccountLink, StudentProfile
from test_yiyang_plan_export_options_mysql import seed_workspace, login

MOBILE = '/api/v1/mobile/teacher/internship/context'
APPLICATIONS = '/api/v1/internship/applications'
CHANGES = '/api/v1/internship/change-requests'


def _enterprise_detail_fixture(*, approved):
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from app.models import EmpCompany, InternshipPosition
    from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
    from app.models.internship_volunteer_group import InternshipVolunteerGroup
    from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
    from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
    ws, foreign = seed_workspace(2), seed_workspace(1)
    tid, bid = int(ws['tenantId']), int(ws['batches'][0]['id'])
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        record = db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id == tid, InternshipRecord.batch_id == bid))
        other_student = db.scalar(select(StudentProfile).where(StudentProfile.tenant_id == tid, StudentProfile.id != record.student_id))
        campaign = InternshipRecruitmentCampaign(tenant_id=tid, batch_id=bid,
            campaign_code='DETAIL', campaign_name='合成企业详情读取', status='OPEN',
            enterprise_decision_start_at=now-timedelta(days=1), enterprise_decision_end_at=now+timedelta(days=1))
        company, other = EmpCompany(tenant_id=tid, name='合成详情企业'), EmpCompany(tenant_id=tid, name='合成其他企业')
        db.add_all([campaign, company, other]); db.flush()
        position = InternshipPosition(tenant_id=tid, batch_id=bid, campaign_id=campaign.id, company_id=company.id, title='合成详情岗位', status='PUBLISHED')
        group = InternshipVolunteerGroup(tenant_id=tid, record_id=record.id, student_id=record.student_id,
            batch_id=bid, campaign_id=campaign.id, status='APPROVED' if approved else 'SUBMITTED', submission_version=29)
        db.add_all([position, group]); db.flush()
        app = InternshipApplication(tenant_id=tid, record_id=record.id, student_id=record.student_id,
            batch_id=bid, campaign_id=campaign.id, position_id=position.id, application_type='POSITION',
            volunteer_no=1, status='APPROVED' if approved else 'PENDING_REVIEW', submitted_at=now)
        db.add(app); db.flush()
        for version in range(1, 30):
            snapshot = InternshipApplicationMaterialSnapshot(tenant_id=tid, volunteer_group_id=group.id,
                student_id=other_student.id if version == 4 else record.student_id,
                campaign_id=campaign.id, batch_id=bid, submission_version=version, profile_version=version,
                profile_snapshot_json={'profile': {'selfIntro': f'合成第{version}版介绍'}},
                school_fact_snapshot_json={'realName': '合成学生'}, consent_version='test', consent_at=now,
                contact_sharing_policy={'mode': 'MASKED_ONLY'}, snapshot_hash=f'{version:064x}')
            db.add(snapshot); db.flush()
            decision = InternshipEnterpriseApplicationDecision(tenant_id=int(foreign['tenantId']) if version == 1 else tid,
                application_id=app.id, volunteer_group_id=group.id, campaign_id=campaign.id,
                batch_id=int(foreign['batches'][0]['id']) if version == 2 else bid,
                company_id=other.id if version == 3 else company.id, position_id=position.id,
                material_snapshot_id=snapshot.id, submission_version=version, decision_status='ACCEPT_INTENT' if approved and version == 29 else 'INTERVIEW',
                effect_status=('CONSUMED' if approved else 'ACTIVE') if version == 29 else 'SUPERSEDED',
                decided_at=now, valid_until=now+timedelta(days=1))
            db.add(decision); db.flush()
            if version == 29:
                group.current_material_snapshot_id = app.material_snapshot_id = snapshot.id
                current_id = decision.id
            if version == 4:
                invalid_snapshot_id = snapshot.id
        db.commit()
        return SimpleNamespace(tenant_id=tid, batch_id=bid, campaign_id=campaign.id,
            company_id=company.id, member_role='HR', user_id=ws['users']['SCHOOL_ADMIN'], member_id=1, claims={}), app.id, current_id, invalid_snapshot_id, other.id


def test_enterprise_confirmed_detail_retains_only_owned_paged_history_and_cannot_write():
    from types import SimpleNamespace
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_enterprise_application_decision_service as service
    context, app_id, decision_id, _, other_company = _enterprise_detail_fixture(approved=True)
    with get_sessionmaker()() as db:
        before = db.get(InternshipApplication, app_id).version
        first = service.material_detail_in_tx(db, context=context, application_id=app_id)
        second = service.material_detail_in_tx(db, context=context, application_id=app_id, history_page=2)
        assert first['applicationStatus'] == first['groupStatus'] == 'APPROVED'
        assert first['volunteerNo'] == 1 and first['submittedAt'].endswith('Z')
        assert first['effectStatus'] == second['effectStatus'] == 'CONSUMED'
        assert first['allowedDecisionActions'] == second['allowedDecisionActions'] == []
        assert '学校已确认' in first['decisionDisabledReason']
        assert first['decisionHistoryTotal'] == second['decisionHistoryTotal'] == 25
        assert len(first['decisionHistory']) == 20 and len(second['decisionHistory']) == 5
        assert [row['submissionVersion'] for row in first['decisionHistory'] + second['decisionHistory']] == list(range(29, 4, -1))
        assert first['decisionHistory'][0]['id'] == str(decision_id)
        with pytest.raises(AppException) as rejected:
            service.set_decision_in_tx(db, context=context, application_id=app_id, status='REJECTED')
        assert rejected.value.code == 'DATA_CONFLICT'
        assert db.get(InternshipApplication, app_id).version == before
        wrong = SimpleNamespace(**{**vars(context), 'company_id': other_company})
        with pytest.raises(AppException) as denied:
            service.material_detail_in_tx(db, context=wrong, application_id=app_id)
        assert denied.value.http_status == 404


def test_enterprise_current_detail_actions_use_canonical_window_and_invalid_snapshot_is_denied():
    from datetime import datetime, timedelta
    from app.core.exceptions import AppException
    from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
    from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
    from app.models.internship_volunteer_group import InternshipVolunteerGroup
    from app.modules.internship.services import internship_enterprise_application_decision_service as service
    context, app_id, decision_id, invalid_snapshot_id, _ = _enterprise_detail_fixture(approved=False)
    with get_sessionmaker()() as db:
        result = service.material_detail_in_tx(db, context=context, application_id=app_id)
        assert set(result['allowedDecisionActions']) == {'ACCEPT_INTENT', 'REJECTED'}
        decision = db.get(InternshipEnterpriseApplicationDecision, decision_id)
        original = (decision.version, decision.effect_status)
        campaign = db.get(InternshipRecruitmentCampaign, context.campaign_id)
        campaign.enterprise_decision_end_at = datetime.utcnow()-timedelta(seconds=1)
        db.flush()
        assert service.material_detail_in_tx(db, context=context, application_id=app_id)['allowedDecisionActions'] == []
        assert (decision.version, decision.effect_status) == original
        campaign.status = 'FROZEN'
        decision.decision_status = 'ACCEPT_INTENT'
        group = db.scalar(select(InternshipVolunteerGroup).where(InternshipVolunteerGroup.tenant_id == context.tenant_id, InternshipVolunteerGroup.campaign_id == context.campaign_id))
        group.status, group.locked_application_id, group.teacher_confirm_deadline = 'LOCKED', app_id, datetime.utcnow()+timedelta(days=1)
        db.flush()
        assert service.material_detail_in_tx(db, context=context, application_id=app_id)['allowedDecisionActions'] == ['REJECTED']
        db.get(InternshipApplication, app_id).material_snapshot_id = invalid_snapshot_id
        db.flush()
        with pytest.raises(AppException) as denied:
            service.material_detail_in_tx(db, context=context, application_id=app_id)
        assert denied.value.http_status == 404


@pytest.mark.parametrize('school_days,access_days', [(-1, 1), (1, -1), (0, 1), (1, 0), (1, 2), (2, 1), (None, None)])
def test_enterprise_accept_deadline_matches_actions_write_and_persisted_lock(monkeypatch, school_days, access_days):
    from datetime import datetime, timedelta
    from app.core.context import get_tenant, set_tenant
    from app.core.exceptions import AppException
    from app.models import AuditOutbox, InternshipAuditTrail
    from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
    from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
    from app.models.internship_volunteer_group import InternshipVolunteerGroup
    from app.modules.internship.services import internship_enterprise_application_decision_service as service
    context, app_id, decision_id, _, _ = _enterprise_detail_fixture(approved=False)
    now = datetime.utcnow().replace(microsecond=0)
    class FixedDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return now
    monkeypatch.setattr(service, 'datetime', FixedDateTime)
    previous_tenant = get_tenant()
    set_tenant(context.tenant_id)
    try:
        with get_sessionmaker()() as db:
            campaign = db.get(InternshipRecruitmentCampaign, context.campaign_id)
            campaign.school_confirm_end_at = None if school_days is None else now+timedelta(days=school_days)
            campaign.enterprise_access_end_at = None if access_days is None else now+timedelta(days=access_days)
            db.flush()
            decision = db.get(InternshipEnterpriseApplicationDecision, decision_id)
            group = db.get(InternshipVolunteerGroup, decision.volunteer_group_id)
            group_id = group.id
            before = (decision.decision_status, decision.effect_status, decision.version, decision.valid_until, group.status, group.version, group.teacher_confirm_deadline)
            audit_counts = tuple(db.scalar(select(func.count()).select_from(model).where(model.tenant_id == context.tenant_id)) for model in (InternshipAuditTrail, AuditOutbox))
            blocked = any(value is not None and value <= 0 for value in (school_days, access_days))
            result = service.material_detail_in_tx(db, context=context, application_id=app_id)
            assert set(result['allowedDecisionActions']) == ({'REJECTED'} if blocked else {'ACCEPT_INTENT', 'REJECTED'})
            if blocked:
                with pytest.raises(AppException) as rejected:
                    service.set_decision_in_tx(db, context=context, application_id=app_id, status='ACCEPT_INTENT')
                assert rejected.value.code == 'DATA_CONFLICT'
                assert (decision.decision_status, decision.effect_status, decision.version, decision.valid_until, group.status, group.version, group.teacher_confirm_deadline) == before
                assert tuple(db.scalar(select(func.count()).select_from(model).where(model.tenant_id == context.tenant_id)) for model in (InternshipAuditTrail, AuditOutbox)) == audit_counts
                return
            bounds = [now+timedelta(days=value) for value in (school_days, access_days) if value is not None]
            expected_until = min(bounds) if bounds else None
            expected_lock = min([now+timedelta(hours=campaign.teacher_confirm_sla_hours), *bounds])
            service.set_decision_in_tx(db, context=context, application_id=app_id, status='ACCEPT_INTENT')
            db.commit()
        with get_sessionmaker()() as db:
            decision = db.get(InternshipEnterpriseApplicationDecision, decision_id)
            group = db.get(InternshipVolunteerGroup, group_id)
            assert (decision.decision_status, decision.effect_status, decision.valid_until) == ('ACCEPT_INTENT', 'ACTIVE', expected_until)
            assert (group.status, group.locked_application_id, group.teacher_confirm_deadline) == ('LOCKED', app_id, expected_lock)
    finally:
        set_tenant(previous_tenant)


def data(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['code'] == 0, body
    return body['data']


@pytest.fixture(scope='module')
def workspace():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    ws, foreign = seed_workspace(2), seed_workspace(1)
    tid, batch = int(ws['tenantId']), int(ws['batches'][0]['id'])
    with get_sessionmaker()() as db:
        first = db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id == tid, InternshipRecord.batch_id == batch))
        first_student = db.get(StudentProfile, first.student_id)
        db.add(StudentAccountLink(tenant_id=tid, student_id=first.student_id, user_id=ws['users']['STUDENT'], link_status='ACTIVE', source='IDENTITY_IMPORT', bound_student_no=first_student.student_no, bound_login_name='student'))
        records = [first]
        for index in range(1, 23):
            student = StudentProfile(tenant_id=tid, student_no=f'TM05-{index:02}', real_name=f'合成审核学生{index}', current_stage='ENROLLED', student_status='NORMAL', status='ACTIVE')
            db.add(student); db.flush()
            record = InternshipRecord(tenant_id=tid, student_id=student.id, batch_id=batch, status='READY', destination_type='NONE', advisor_user_id=ws['users']['INTERN_MENTOR'] if index < 22 else ws['users']['SCHOOL_ADMIN'], advisor_name='合成指导教师')
            db.add(record); db.flush(); records.append(record)
        deleted = StudentProfile(tenant_id=tid, student_no='TM05-DELETED', real_name='已删除合成学生', is_deleted=True)
        db.add(deleted); db.flush()
        foreign_student = db.scalar(select(StudentProfile).where(StudentProfile.tenant_id == int(foreign['tenantId'])))
        absent = int(db.scalar(select(func.max(StudentProfile.id))) or 0) + 1000000000000
        for sid in [deleted.id, absent, foreign_student.id]:
            db.add(InternshipRecord(tenant_id=tid, student_id=sid, batch_id=batch, status='READY', advisor_user_id=ws['users']['INTERN_MENTOR']))
        apps = []
        for record in [first, records[-1]]:
            app = InternshipApplication(tenant_id=tid, record_id=record.id, student_id=record.student_id, batch_id=None if record is first else batch, application_type='SELF_ARRANGED', volunteer_no=0, status='PENDING_REVIEW', company_name='合成申请单位')
            db.add(app); db.flush(); apps.append(str(app.id))
        bad_apps = []
        for number, sid, bid in [(1, records[1].student_id, batch), (2, first.student_id, int(ws['batches'][1]['id'])), (3, foreign_student.id, batch)]:
            app = InternshipApplication(tenant_id=tid, record_id=first.id, student_id=sid, batch_id=bid, application_type='POSITION', volunteer_no=number, status='PENDING_REVIEW')
            db.add(app); db.flush(); bad_apps.append(str(app.id))
        bad = InternshipChangeRequest(tenant_id=tid, internship_id=first.id, student_id=records[1].student_id, change_type='WITHDRAW_POST', reason='合成坏关联读取前置', status='PENDING', record_version_snapshot=first.version)
        db.add(bad); db.flush()
        for record in records[1:]:
            db.add(InternshipChangeRequest(tenant_id=tid, internship_id=record.id, student_id=record.student_id, change_type='WITHDRAW_POST', reason='合成只读队列前置', status='PENDING', record_version_snapshot=record.version))
        for status, record in [('APPROVED', records[1]), ('REJECTED', records[2])]:
            db.add(InternshipChangeRequest(tenant_id=tid, internship_id=record.id, student_id=record.student_id, change_type='WITHDRAW_POST', reason='合成已审历史前置', status=status, review_comment='合成历史审核意见', record_version_snapshot=record.version))
        db.commit()
        ws.update(batch=str(batch), records=[str(r.id) for r in records], apps=apps, badApps=bad_apps, badChange=str(bad.id), foreign=foreign)
    return ws


def test_summary_matches_all_pages_of_valid_students(workspace):
    with login(workspace) as client:
        params = {'batchId': workspace['batch']}
        summary = data(client.get(MOBILE+'/applications/summary', params=params))
        assert (summary['totalStudents'], summary['filledStudents'], summary['unfilledStudents']) == (23, 2, 21)
        assert summary['pendingReviewApplications'] == 2
        seen = {}
        for state, expected in [('FILLED', 2), ('UNFILLED', 21)]:
            rows = []
            for page in range(1, (expected + 9)//10 + 1):
                result = data(client.get(MOBILE+'/applications/students', params={**params, 'state': state, 'page': page, 'pageSize': 10}))
                assert result['total'] == expected and len(result['items']) <= 10
                rows += result['items']
            seen[state] = {item['recordId'] for item in rows}
            assert len(seen[state]) == expected
        assert not seen['FILLED'] & seen['UNFILLED']
        assert seen['FILLED'] | seen['UNFILLED'] == set(workspace['records'])


def test_application_queue_and_detail_allow_owned_null_batch_only(workspace):
    with login(workspace) as client:
        items = data(client.get(APPLICATIONS, params={'batchId': workspace['batch'], 'status': 'ALL'}))
        assert {item['id'] for item in items['items']} == set(workspace['apps'])
        assert data(client.get(APPLICATIONS+'/'+workspace['apps'][0]))['recordId'] == workspace['records'][0]
        for aid in workspace['badApps']:
            assert client.get(APPLICATIONS+'/'+aid).status_code == 404
            denied = client.post(MOBILE+'/applications/'+aid+'/review', params={'batchId': workspace['batch']}, json={'action': 'REJECT', 'comment': '合成拒绝坏关联申请', 'expectedVersion': 0, 'recordExpectedVersion': 0})
            assert denied.status_code == 404, denied.text
    with login(workspace, 'STUDENT') as client:
        result = data(client.get('/api/v1/portal/internship/context/applications', params={'batchId': workspace['batch'], 'internshipId': workspace['records'][0]}))
        assert {item['id'] for item in result} == {workspace['apps'][0]}
    with get_sessionmaker()() as db:
        for aid in workspace['badApps']:
            app = db.get(InternshipApplication, int(aid)); assert app.status == 'PENDING_REVIEW' and app.version == 0
        record = db.get(InternshipRecord, int(workspace['records'][0])); assert not record.current_application_id and record.destination_type in ('NONE', '')


def test_changes_are_full_counted_classified_and_bad_owner_is_rejected(workspace):
    with login(workspace) as client:
        pending = data(client.get(MOBILE+'/changes', params={'batchId': workspace['batch'], 'pageSize': 20}))
        assert pending['total'] == 22 and len(pending['items']) == 20 and pending['hasMore']
        second = data(client.get(MOBILE+'/changes', params={'batchId': workspace['batch'], 'page': 2, 'pageSize': 20}))
        assert second['total'] == 22 and len(second['items']) == 2
        reviewed = data(client.get(MOBILE+'/changes', params={'batchId': workspace['batch'], 'status': 'REVIEWED'}))
        assert reviewed['total'] == 2 and {r['status'] for r in reviewed['items']} == {'APPROVED', 'REJECTED'}
        assert all(r['reviewComment'] == '合成历史审核意见' for r in reviewed['items'])
        assert client.get(CHANGES+'/'+workspace['badChange']).status_code == 404
        denied = client.post(MOBILE+'/changes/'+workspace['badChange']+'/review', params={'batchId': workspace['batch']}, json={'action': 'REJECT', 'comment': '合成拒绝坏关联变更', 'expectedVersion': 0, 'recordExpectedVersion': 0})
        assert denied.status_code == 404, denied.text
        assert client.get(MOBILE+'/changes', params={'batchId': workspace['batch'], 'status': 'BAD_STATE'}).status_code == 400
    with get_sessionmaker()() as db:
        bad = db.get(InternshipChangeRequest, int(workspace['badChange'])); assert bad.status == 'PENDING' and bad.version == 0


def test_normal_teacher_scope_is_shared_by_counts_and_queues(workspace):
    with login(workspace, 'INTERN_MENTOR') as client:
        params = {'batchId': workspace['batch']}
        summary = data(client.get(MOBILE+'/applications/summary', params=params))
        assert (summary['totalStudents'], summary['filledStudents']) == (22, 1)
        assert data(client.get(APPLICATIONS, params=params))['total'] == 1
        assert data(client.get(MOBILE+'/changes', params=params))['total'] == 21
        assert client.get(APPLICATIONS+'/'+workspace['apps'][-1]).status_code == 403
        denied = client.post(MOBILE+'/applications/'+workspace['apps'][-1]+'/review', params=params, json={'action': 'REJECT', 'comment': '合成范围之外拒绝', 'expectedVersion': 0})
        assert denied.status_code == 403, denied.text
        for aid in workspace['badApps']:
            assert client.get(APPLICATIONS+'/'+aid).status_code == 404
        assert client.get(CHANGES+'/'+workspace['badChange']).status_code == 404
    with login(workspace['foreign']) as client:
        assert client.get(APPLICATIONS+'/'+workspace['apps'][0]).status_code == 404
    with login(workspace, 'STUDENT') as client:
        assert client.get(MOBILE+'/changes', params={'batchId': workspace['batch']}).status_code == 403


def test_coverage_unifies_owned_volunteers_without_reusing_legacy_review(workspace):
    """Read-only synthetic facts cover both authorities; no business terminal state is claimed."""
    from app.models import EmpCompany, InternshipPosition
    from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
    from app.models.internship_volunteer_group import InternshipVolunteerGroup
    from app.models import InternshipAuditTrail
    from datetime import datetime
    ws = seed_workspace(1)
    tid, batch = int(ws['tenantId']), int(ws['batches'][0]['id'])
    with get_sessionmaker()() as db:
        first = db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id == tid))
        records = [first]
        for index in range(1, 10):
            student = StudentProfile(tenant_id=tid, student_no=f'COVER-{index:02}', real_name=f'合成填报学生{index}', current_stage='ENROLLED', student_status='NORMAL', status='ACTIVE')
            db.add(student); db.flush()
            record = InternshipRecord(tenant_id=tid, student_id=student.id, batch_id=batch, status='READY', advisor_user_id=ws['users']['INTERN_MENTOR'] if index < 9 else ws['users']['SCHOOL_ADMIN'])
            db.add(record); db.flush(); records.append(record)
        campaigns = []
        for index in range(1, 4):
            campaign = InternshipRecruitmentCampaign(tenant_id=tid, batch_id=batch, campaign_code=f'COVER-{index}', campaign_name=f'合成招聘季{index}', round_no=index, status='OPEN', is_deleted=index == 3)
            db.add(campaign); db.flush(); campaigns.append(campaign)
        company = EmpCompany(tenant_id=tid, name='合成统计企业', coop_status='ACTIVE')
        db.add(company); db.flush()
        positions = []
        for index, campaign in enumerate(campaigns):
            position = InternshipPosition(tenant_id=tid, company_id=company.id, campaign_id=campaign.id, title=f'合成岗位{index}', status='PUBLISHED', headcount=100)
            db.add(position); db.flush(); positions.append(position)
        for record in (records[0], records[9]):
            db.add(InternshipApplication(tenant_id=tid, record_id=record.id, student_id=record.student_id, batch_id=batch, application_type='SELF_ARRANGED', volunteer_no=0, status='DRAFT', company_name='合成自主单位'))
        campaign_apps = []
        def group(index, campaign_index, status, app_status, *, empty=False, wrong_student=False):
            record, campaign = records[index], campaigns[campaign_index]
            row = InternshipVolunteerGroup(tenant_id=tid, record_id=record.id, student_id=records[6].student_id if wrong_student else record.student_id, batch_id=batch, campaign_id=campaign.id, status=status)
            db.add(row); db.flush()
            if not empty:
                for slot in (1, 2, 3):
                    application = InternshipApplication(tenant_id=tid, record_id=record.id, student_id=record.student_id, batch_id=batch, campaign_id=campaign.id, application_type='POSITION', volunteer_no=slot, position_id=positions[campaign_index].id, status='CANCELLED' if status == 'APPROVED' and slot > 1 else app_status)
                    db.add(application); db.flush(); campaign_apps.append(str(application.id))
            return row
        group(0, 0, 'SUBMITTED', 'PENDING_REVIEW')
        group(0, 1, 'LOCKED', 'PENDING_REVIEW')
        group(1, 0, 'DRAFT', 'DRAFT')
        school_revision = group(2, 0, 'NEEDS_REVISION', 'PENDING_REVIEW')
        group(3, 0, 'APPROVED', 'APPROVED')
        auto_revision = group(4, 0, 'NEEDS_REVISION', 'DRAFT', empty=True)
        enterprise_revision = group(5, 0, 'NEEDS_REVISION', 'CANCELLED')
        group(5, 1, 'CLOSED', 'CANCELLED')
        group(6, 0, 'SUBMITTED', 'WITHDRAWN')
        group(7, 0, 'SUBMITTED', 'PENDING_REVIEW', wrong_student=True)
        group(8, 2, 'SUBMITTED', 'PENDING_REVIEW')
        for row, histories in ((school_revision, [('REQUEST_VOLUNTEER_REVISION', 'ENTERPRISE_HR'), ('REQUEST_VOLUNTEER_REVISION', 'INTERN_MENTOR')]),
                               (auto_revision, [('REQUEST_VOLUNTEER_REVISION', 'INTERN_MENTOR'), ('AUTO_RELEASE_ENTERPRISE_CONFIRM_LOCK', '')]),
                               (enterprise_revision, [('REQUEST_VOLUNTEER_REVISION', 'INTERN_MENTOR'), ('REQUEST_VOLUNTEER_REVISION', 'ENTERPRISE_HR')])):
            for action, role in histories:
                db.add(InternshipAuditTrail(tenant_id=tid, target_type='INTERNSHIP_VOLUNTEER_GROUP', target_id=row.id, action=action, operator_name='合成读取前置', detail_json={'actorRole': role, 'newVersion': 0}, occurred_at=datetime.utcnow()))
                db.flush()
        db.commit()
        expected_filled = {str(records[index].id) for index in (0, 1, 2, 3, 9)}
        all_records = {str(row.id) for row in records}
    with login(ws) as client:
        params = {'batchId': str(batch)}
        summary = data(client.get(MOBILE+'/applications/summary', params=params))
        assert (summary['totalStudents'], summary['filledStudents'], summary['unfilledStudents']) == (10, 5, 5)
        assert summary['filledRate'] == 50
        assert (summary['legacyFilledStudents'], summary['recruitmentFilledStudents'], summary['pendingRecruitmentGroups']) == (2, 4, 3)
        assert summary['pendingReviewApplications'] == 0 and summary['draftApplications'] == 2
        assert {row['campaignId'] for row in summary['recruitmentCampaigns']} == {str(campaigns[0].id), str(campaigns[1].id)}
        seen = {}
        for state in ('FILLED', 'UNFILLED'):
            rows = []
            for page in range(1, 4):
                result = data(client.get(MOBILE+'/applications/students', params={**params, 'state': state, 'page': page, 'pageSize': 2}))
                assert result['total'] == 5
                rows += result['items']
            seen[state] = {item['recordId'] for item in rows}
        assert seen['FILLED'] == expected_filled
        assert seen['UNFILLED'] == all_records - expected_filled
        assert not data(client.get(APPLICATIONS, params={**params, 'status': 'PENDING_REVIEW'}))['items']
        reviewed = data(client.get(MOBILE+'/volunteer-groups', params={**params, 'campaignId': str(campaigns[0].id), 'status': 'REVIEWED'}))
        assert reviewed['total'] == 2 and {row['status'] for row in reviewed['items']} == {'NEEDS_REVISION', 'APPROVED'}
        assert sum(data(client.get(MOBILE+'/volunteer-groups', params={**params, 'campaignId': str(campaign.id), 'status': 'PENDING'}))['total'] for campaign in campaigns[:2]) == summary['pendingRecruitmentGroups']
        assert data(client.get(MOBILE+'/applications/students', params={**params, 'state': 'FILLED', 'keyword': '%'}))['total'] == 0
        for aid in campaign_apps[:3]:
            assert client.get(APPLICATIONS+'/'+aid).status_code == 404
            assert client.post(MOBILE+'/applications/'+aid+'/review', params=params, json={'action': 'APPROVE', 'expectedVersion': 0}).status_code == 404
    with login(ws, 'INTERN_MENTOR') as client:
        summary = data(client.get(MOBILE+'/applications/summary', params={'batchId': str(batch)}))
        assert (summary['totalStudents'], summary['filledStudents'], summary['unfilledStudents']) == (9, 4, 5)
    with login(workspace['foreign']) as client:
        assert client.get(MOBILE+'/applications/summary', params={'batchId': str(batch)}).status_code == 404
    with get_sessionmaker()() as db:
        assert all(db.get(InternshipApplication, int(aid)).version == 0 for aid in campaign_apps)
