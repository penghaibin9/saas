"""Non-cleaning MySQL checks through current student/teacher role routes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
import os

import pytest
from sqlalchemy import func, select
from app.db.session import get_sessionmaker
from app.models import (EmpCompany, InternshipAuditTrail, InternshipBatch, InternshipChangeRequest,
    InternshipPosition, InternshipRecord, StudentAccountLink, StudentProfile, UnifiedTodo)
from test_yiyang_plan_export_options_mysql import seed_workspace, login
from test_yiyang_gap09_minimum_age import encrypted_student

PC = '/api/v1/portal/internship/context/changes'
MOBILE = '/api/v1/mobile/internship/context/changes'
REVIEW = '/api/v1/internship/change-requests'


def data(response):
    assert response.status_code == 200, response.text
    assert response.json()['code'] == 0, response.json()
    return response.json()['data']


@pytest.fixture
def story():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    ws = seed_workspace(2)
    tid, bid = int(ws['tenantId']), int(ws['batches'][0]['id'])
    with get_sessionmaker()() as db:
        record = db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id == tid, InternshipRecord.batch_id == bid))
        student = db.get(StudentProfile, record.student_id)
        student.id_card_encrypted = encrypted_student(date(2000, 1, 1)).id_card_encrypted
        db.add(StudentAccountLink(tenant_id=tid, student_id=student.id, user_id=ws['users']['STUDENT'],
            link_status='ACTIVE', source='IDENTITY_IMPORT', bound_student_no=student.student_no, bound_login_name='student'))
        batch = db.get(InternshipBatch, bid)
        batch.rules_config = {'compliance': {'workRights': {'requireEnterpriseAccess': False}}}
        companies = [EmpCompany(tenant_id=tid, name=name, status='ACTIVE', coop_status='ACTIVE',
            qualification_status='PASSED', blacklist=False) for name in ['合成原企业', '合成目标企业']]
        db.add_all(companies); db.flush()
        positions = [InternshipPosition(tenant_id=tid, batch_id=bid, company_id=company.id,
            company_name=company.name, title='合成岗位'+str(index), work_location='合成实训地点',
            work_address='合成实训地点', work_content='软件测试与质量记录', daily_hours=8, weekly_hours=40,
            night_shift=False, overtime_allowed=False, rest_days_per_week=2, remuneration_type='UNPAID',
            accommodation_provided=False, meal_provided=False, hazardous_flag=False,
            headcount=3, allocated_count=1 if index == 0 else 0, status='PUBLISHED')
            for index, company in enumerate(companies)]
        db.add_all(positions); db.flush()
        record.position_id, record.enterprise_id = positions[0].id, companies[0].id
        record.position_name, record.enterprise_name = positions[0].title, companies[0].name
        record.eligibility_status, record.destination_type = 'QUALIFIED', 'ASSIGNED'
        db.commit()
        ws.update(ctx={'batchId': str(bid), 'internshipId': str(record.id)},
            recordId=record.id, studentId=student.id, oldPosition=positions[0].id,
            targetPosition=positions[1].id, targetCompany=companies[1].id)
    return ws


def apply_payload(ws, **extra):
    return {**ws['ctx'], 'expectedVersion': 0, 'changeType': 'CHANGE_ENTERPRISE',
        'reason': '调整岗位方向并申请更换实习企业', 'targetPositionId': str(ws['targetPosition']), **extra}


def reject(ws, item):
    with login(ws, 'INTERN_MENTOR') as teacher:
        return data(teacher.post(REVIEW+'/'+item['id']+'/review', json={
            'action': 'REJECT', 'comment': '请补充调整岗位原因及沟通情况', 'expectedVersion': item['version']}))


def todo(ws, cid):
    with get_sessionmaker()() as db:
        rows = db.scalars(select(UnifiedTodo).where(UnifiedTodo.tenant_id == int(ws['tenantId']),
            UnifiedTodo.source_biz_type == 'INTERN_CHANGE', UnifiedTodo.source_biz_id == int(cid))).all()
        return [(r.status, r.assignee_id, r.todo_type) for r in rows]


def test_same_change_pc_submit_teacher_return_mobile_resubmit_approve(story):
    with login(story, 'STUDENT') as student:
        targets = data(student.get(PC+'/target-positions', params={**story['ctx'], 'changeType': 'CHANGE_ENTERPRISE'}))
        assert [p['positionId'] for p in targets['items']] == [str(story['targetPosition'])]
        assert targets['items'][0]['canSelect'] is True
        created = data(student.post(PC, json=apply_payload(story)))
        cid = created['id']
        assert created['targetPositionId'] == str(story['targetPosition'])
        assert todo(story, cid) == [('PENDING', story['users']['INTERN_MENTOR'], 'INTERN_ENTERPRISE_CHANGE')]
        with login(story, 'INTERN_MENTOR') as teacher:
            focused=data(teacher.get('/api/v1/mobile/teacher/internship/context/changes',params={
                'batchId':story['ctx']['batchId'],'status':'ALL','changeId':cid}))
            assert focused['total']==1 and [item['id'] for item in focused['items']]==[cid]
            todos=data(teacher.get('/api/v1/teacher-mobile/internship/workbench/todos',params={'group':'CHANGE'}))['items']
            assert next(item for item in todos if item['sourceBizId']==cid)['actionPath']==f'/pages/teacher-internship/internship-change/index?batchId={story["ctx"]["batchId"]}&changeId={cid}'
        rejected = reject(story, created)
        assert rejected['version'] == 1 and todo(story, cid)[0][0] == 'DONE'
        stale = student.post(MOBILE+'/'+cid+'/resubmit', json=apply_payload(story))
        assert stale.status_code == 409
        resubmitted = data(student.post(MOBILE+'/'+cid+'/resubmit', json=apply_payload(story,
            expectedVersion=1, reason='根据教师意见补充岗位安排与校企沟通情况')))
        assert resubmitted['id'] == cid and resubmitted['version'] == 2
        assert resubmitted['status'] == 'PENDING' and not resubmitted['reviewComment']
        assert todo(story, cid) == [('PENDING', story['users']['INTERN_MENTOR'], 'INTERN_ENTERPRISE_CHANGE')]
        with login(story, 'INTERN_MENTOR') as teacher:
            result = data(teacher.post(REVIEW+'/'+cid+'/review', json={'action': 'APPROVE',
                'comment': '沟通与岗位条件已核对', 'expectedVersion': 2, 'recordExpectedVersion': resubmitted['recordVersionSnapshot']}))
            assert result['version'] == 3 and result['status'] == 'APPROVED'
        reread = data(student.get(PC, params=story['ctx']))['items']
        assert len(reread) == 1 and reread[0]['id'] == cid and reread[0]['version'] == 3
        assert todo(story, cid)[0][0] == 'DONE'
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, story['recordId'])
        assert record.position_id == story['targetPosition'] and record.enterprise_id == story['targetCompany']
        assert record.status == 'READY' and record.version == 1
        assert db.get(InternshipPosition, story['oldPosition']).allocated_count == 0
        assert db.get(InternshipPosition, story['targetPosition']).allocated_count == 1
        trail = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(story['tenantId']),
            InternshipAuditTrail.target_type == 'CHANGE_REQ', InternshipAuditTrail.target_id == int(cid)).order_by(InternshipAuditTrail.id)).all()
        assert [t.action for t in trail] == ['APPLY_VERSIONED', 'REJECT', 'RESUBMIT_VERSIONED', 'APPROVE']
        assert trail[2].detail_json['before']['reviewComment'] == '请补充调整岗位原因及沟通情况'


def test_withdraw_closes_todo_and_cannot_resubmit(story):
    with login(story, 'STUDENT') as student:
        created = data(student.post(MOBILE, json=apply_payload(story)))
        cid = created['id']
        result = data(student.post(PC+'/'+cid+'/withdraw', json={**story['ctx'], 'expectedVersion': 0}))
        assert result['version'] == 1 and todo(story, cid)[0][0] == 'DONE'
        assert student.post(PC+'/'+cid+'/resubmit', json=apply_payload(story, expectedVersion=1)).status_code == 409


def test_original_type_owner_and_target_guards_preserve_rejected_row(story):
    with login(story, 'STUDENT') as student:
        created = data(student.post(PC, json=apply_payload(story)))
        reject(story, created)
        cid = created['id']
        assert student.post(PC+'/'+cid+'/resubmit', json=apply_payload(story, expectedVersion=1, changeType='WITHDRAW_POST')).status_code == 400
        assert student.post(PC+'/'+cid+'/resubmit', json=apply_payload(story, expectedVersion=1, targetPositionId=str(story['oldPosition']))).status_code == 409
        missing_context = student.post(PC+'/'+cid+'/resubmit', json={**apply_payload(story, expectedVersion=1), 'batchId': story['batches'][1]['id']})
        assert missing_context.status_code == 404 and missing_context.json()['bizCode'] == 'DATA_NOT_FOUND'
    foreign = seed_workspace(1)
    with login(foreign, 'STUDENT') as student:
        assert student.post(PC+'/'+cid+'/resubmit', json=apply_payload(story, expectedVersion=1)).status_code == 403
    with get_sessionmaker()() as db:
        row = db.get(InternshipChangeRequest, int(cid))
        assert row.status == 'REJECTED' and row.version == 1 and row.change_type == 'CHANGE_ENTERPRISE'
    assert todo(story, cid)[0][0] == 'DONE'


def test_self_arranged_audit_preserves_both_original_and_corrected_names(story):
    with login(story, 'STUDENT') as student:
        body = apply_payload(story, changeType='SELF_ARRANGED', targetEnterpriseName='合成自主企业甲', targetPositionName='合成自主岗位甲')
        body.pop('targetPositionId')
        created = data(student.post(PC, json=body)); reject(story, created)
        result = data(student.post(PC+'/'+created['id']+'/resubmit', json={**body, 'expectedVersion': 1,
            'targetEnterpriseName': '合成自主企业乙', 'targetPositionName': '合成自主岗位乙'}))
        assert result['id'] == created['id'] and not result['targetPositionId']
    with get_sessionmaker()() as db:
        trail = db.scalar(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(story['tenantId']),
            InternshipAuditTrail.target_type == 'CHANGE_REQ', InternshipAuditTrail.target_id == int(created['id']),
            InternshipAuditTrail.action == 'RESUBMIT_VERSIONED'))
        assert trail.detail_json['before']['targetEnterpriseName'] == '合成自主企业甲'
        assert trail.detail_json['before']['targetPositionName'] == '合成自主岗位甲'
        assert trail.detail_json['targetEnterpriseName'] == '合成自主企业乙'
        assert trail.detail_json['targetPositionName'] == '合成自主岗位乙'


def test_history_and_targets_are_paged_with_chinese_block_reasons(story):
    with get_sessionmaker()() as db:
        exemplar = db.get(InternshipPosition, story['targetPosition'])
        for index in range(23):
            db.add(InternshipPosition(tenant_id=int(story['tenantId']), batch_id=int(story['ctx']['batchId']),
                company_id=story['targetCompany'], company_name=exemplar.company_name,
                title=f'合成分页岗位{index:02}', work_location=exemplar.work_location,
                work_content=exemplar.work_content, daily_hours=None if index == 0 else 8,
                weekly_hours=40, night_shift=False, overtime_allowed=False, rest_days_per_week=2,
                remuneration_type='UNPAID', accommodation_provided=False, meal_provided=False,
                hazardous_flag=False, headcount=3, allocated_count=0, status='PUBLISHED'))
        for index in range(25):
            db.add(InternshipChangeRequest(tenant_id=int(story['tenantId']), internship_id=story['recordId'],
                student_id=story['studentId'], change_type='WITHDRAW_POST', reason=f'合成分页历史{index}', status='REJECTED'))
        db.commit()
    with login(story, 'STUDENT') as student:
        first = data(student.get(PC, params={**story['ctx'], 'pageSize': 20}))
        second = data(student.get(MOBILE, params={**story['ctx'], 'page': 2, 'pageSize': 20}))
        assert (first['total'], len(first['items']), first['hasMore']) == (25, 20, True)
        assert (second['total'], len(second['items']), second['hasMore']) == (25, 5, False)
        assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
        rows = []
        for page in range(1, 4):
            result = data(student.get(PC+'/target-positions', params={**story['ctx'],
                'changeType': 'CHANGE_ENTERPRISE', 'page': page, 'pageSize': 10}))
            assert result['total'] == 24 and len(result['items']) <= 10
            rows += result['items']
        assert len({r['id'] for r in rows}) == 24
        blocked = [r for r in rows if not r['canSelect']]
        assert len(blocked) == 1 and '每日工时' in blocked[0]['selectionReason']
        assert 'dailyHours' not in blocked[0]['selectionReason']
        response = student.post(PC, json=apply_payload(story, targetPositionId=blocked[0]['id']))
        assert response.status_code == 409 and response.json()['bizCode'] == 'DATA_CONFLICT'


def test_resubmit_reads_pending_created_after_initial_snapshot(story, monkeypatch):
    from app.modules.internship.services import internship_student_context_guard as guard
    with login(story, 'STUDENT') as first, login(story, 'STUDENT') as second:
        created = data(first.post(PC, json=apply_payload(story))); reject(story, created)
        seen, release = Event(), Event()
        original = guard.resolve_student_internship_context
        def wait_after_read(*args, **kwargs):
            ctx = original(*args, **kwargs)
            if not seen.is_set():
                seen.set(); assert release.wait(10)
            return ctx
        monkeypatch.setattr(guard, 'resolve_student_internship_context', wait_after_read)
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='change-resubmit') as pool:
            pending = pool.submit(first.post, PC+'/'+created['id']+'/resubmit', json=apply_payload(story, expectedVersion=1))
            try:
                assert seen.wait(10)
                new = data(second.post(PC, json=apply_payload(story)))
            finally: release.set()
            assert pending.result(timeout=15).status_code == 409
        assert todo(story, new['id'])[0][0] == 'PENDING'
        with get_sessionmaker()() as db:
            assert db.get(InternshipChangeRequest, int(created['id'])).status == 'REJECTED'


def test_write_refreshes_record_and_blocks_concurrent_archive(story, monkeypatch):
    from app.modules.internship.services import internship_student_context_guard as guard
    seen, release = Event(), Event()
    original = guard.resolve_student_internship_context
    def wait_after_read(*args, **kwargs):
        ctx = original(*args, **kwargs); seen.set(); assert release.wait(10); return ctx
    monkeypatch.setattr(guard, 'resolve_student_internship_context', wait_after_read)
    with login(story, 'STUDENT') as student, get_sessionmaker()() as school:
        record = school.scalar(select(InternshipRecord).where(InternshipRecord.id == story['recordId']).with_for_update())
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(student.post, PC, json=apply_payload(story))
            try:
                assert seen.wait(10)
                record.status = 'ARCHIVED'; record.version += 1; school.commit()
            finally: release.set()
            response = pending.result(timeout=15)
            assert response.status_code == 409, response.text
        targets = data(student.get(PC+'/target-positions', params={**story['ctx'], 'changeType': 'CHANGE_ENTERPRISE'}))
        assert len(targets['items']) == 1 and targets['items'][0]['canSelect'] is False
        assert '已结束，仅可查看' in targets['items'][0]['selectionReason']
        with get_sessionmaker()() as db:
            assert not db.scalar(select(func.count()).select_from(InternshipChangeRequest).where(
                InternshipChangeRequest.tenant_id == int(story['tenantId']), InternshipChangeRequest.internship_id == story['recordId']))
