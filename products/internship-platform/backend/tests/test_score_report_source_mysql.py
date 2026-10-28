"""F03: new synthetic schools, normal login and score commands; no retained data cleanup."""
from datetime import datetime
import os

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app.config import settings
from app.db.session import get_engine, get_sessionmaker
from app.models import (InternshipAuditTrail, InternshipBatch, InternshipFinalScore,
    InternshipProcessReport, InternshipRecord, InternshipReportReview, InternshipReportVersion, InternshipScoreConfig)
from app.models.file import FileBinding
from test_yiyang_write_flows_mysql import context, login, seed_flow, upload

STAFF = '/api/v1/internship'
PORTAL = '/api/v1/portal/internship'
WEIGHTS = {'checkin': 20, 'weekly': 20, 'monthly': 10, 'enterprise': 30, 'school': 20}


def data(response):
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    return response.json()['data']


@pytest.fixture(scope='module', autouse=True)
def isolated_mysql_only():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('requires explicit isolated MySQL opt-in')
    url = make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == 'test' and url.get_backend_name() == 'mysql'
    assert (url.host, url.port, url.database) in {
        ('127.0.0.1', 3318, 'internship_pr275_test_20261003'),
        ('127.0.0.1', 3306, 'internship_employment_test_ci'),
    }
    with get_engine().connect() as db:
        assert db.scalar(text('SELECT DATABASE()')) == url.database
    def retained():
        with get_sessionmaker()() as db:
            return list(db.execute(select(InternshipRecord.id, InternshipRecord.status, InternshipRecord.version)
                .where(InternshipRecord.tenant_id == 88018, InternshipRecord.id.in_([555, 557]))
                .order_by(InternshipRecord.id)).all())
    before = retained()
    yield
    assert retained() == before


def workspace(rules, record_property):
    item = seed_flow()
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, int(item['recordId']))
        record.status = 'ASSESSING'  # New test-school precondition, never a retained student's state.
        batch = db.get(InternshipBatch, int(item['batchId']))
        batch.rules_config = rules
        config = InternshipScoreConfig(tenant_id=int(item['tenantId']), batch_id=batch.id,
            active_scope_key=f'BATCH:{batch.id}', status='ACTIVE', version=4,
            checkin_weight=20, weekly_weight=20, monthly_weight=10, enterprise_weight=30,
            school_weight=20, pass_line=60)
        db.add(config); db.flush(); item['configId'] = str(config.id)
        db.commit()
    record_property('syntheticTenantId', item['tenantId'])
    record_property('syntheticTenantCode', item['tenantCode'])
    return item


def submit(student, item, kind, period, *, version=0):
    body = {**context(item), 'expectedVersion': version, 'attachmentFileIds': []}
    if kind == 'WEEKLY':
        body.update(weekNo=int(period), workContent='合成岗位工作与安全记录。'*5,
                    harvestContent='合成工作收获记录。'*5, planContent='合成下周任务计划。'*3)
    else:
        body.update(reportType=kind, periodKey=period, content='合成报告来源核对内容。'*40)
    return data(student.post(PORTAL + ('/context/weekly-reports' if kind == 'WEEKLY' else '/context/reports'), json=body))


def review(teacher, item, report, kind, action='APPROVE'):
    body = {'batchId': item['batchId'], 'expectedVersion': report['version'],
            'action': action, 'comment': '合成报告来源校验意见'}
    if action == 'APPROVE':
        body.update(summaryScore=0) if kind == 'SUMMARY' else body.update(ratingLevel=4)
    return data(teacher.post(STAFF + ('/reports/' if kind == 'WEEKLY' else '/process-reports/')
                            + report['id'] + '/review', json=body))


def compute_and_read(teacher, school, item):
    computed = data(teacher.post(STAFF + '/scores/compute', json={'internshipId': item['recordId']}))
    reread = data(school.get(STAFF + '/scores/' + computed['id']))
    assert reread['suggestedScores'] == computed['suggestedScores']
    assert reread['scoreConfigId'] == item['configId'] and reread['scoreConfigVersion'] == 4
    with get_sessionmaker()() as db:
        snapshot = db.scalar(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == int(item['tenantId']),
            InternshipAuditTrail.target_type == 'SCORE', InternshipAuditTrail.target_id == int(computed['id']),
            InternshipAuditTrail.action == 'COMPUTE_FACT_SNAPSHOT'))
        assert snapshot is not None
        detail = snapshot.detail_json
        assert detail['weights'] == WEIGHTS and detail['sourceReadiness'] == {
            'enterpriseEvaluation': False, 'studentSelfEvaluation': False, 'advisorEvaluation': False}
        assert detail['sourceManifest']['facts']['scoreConfig']['version'] == 4
        assert detail['factSourceHash'] == computed['factSourceHash']
        assert detail['sourceHash'] == computed['sourceHash']
    return computed, detail


def test_configured_reports_use_approved_originals_and_preserve_zero_summary_grade(record_property):
    item = workspace({'weeklyReport': {'requiredCount': 1}, 'processReport': {
        'dailyRequiredCount': 1, 'monthlyRequiredCount': 1, 'summaryRequiredCount': 1}}, record_property)
    with login(item, 'STUDENT') as student, login(item, 'INTERN_MENTOR') as teacher, login(item) as school:
        week = submit(student, item, 'WEEKLY', 1); review(teacher, item, week, 'WEEKLY')
        month = submit(student, item, 'MONTHLY', '2026-09')
        returned = review(teacher, item, month, 'MONTHLY', 'RETURN')
        resubmitted = submit(student, item, 'MONTHLY', '2026-09', version=returned['version'])
        assert resubmitted['id'] == month['id']
        review(teacher, item, resubmitted, 'MONTHLY')
        summary = submit(student, item, 'SUMMARY', 'FINAL'); review(teacher, item, summary, 'SUMMARY')
        computed, snapshot = compute_and_read(teacher, school, item)
        assert computed['suggestedScores']['weekly'] == computed['suggestedScores']['monthly'] == 100
        source = snapshot['sourceManifest']['facts']['monthly']
        assert source['expected'] == source['actual'] == 2 and len(source['rows']) == 2
        with get_sessionmaker()() as db:
            versions = list(db.scalars(select(InternshipReportVersion.version_no).where(
                InternshipReportVersion.tenant_id == int(item['tenantId']),
                InternshipReportVersion.report_kind == 'PROCESS',
                InternshipReportVersion.report_id == int(month['id'])).order_by(InternshipReportVersion.version_no)))
            assert versions == [1, 2]
            summary_review = db.scalar(select(InternshipReportReview).where(
                InternshipReportReview.tenant_id == int(item['tenantId']),
                InternshipReportReview.report_kind == 'PROCESS',
                InternshipReportReview.report_id == int(summary['id'])))
            assert summary_review.summary_score == 0


def test_extra_monthly_cannot_replace_summary_and_nonapproved_rows_do_not_count(record_property):
    item = workspace({'weeklyReport': {'requiredCount': 1}, 'processReport': {
        'monthlyRequiredCount': 1, 'summaryRequiredCount': 1}}, record_property)
    with login(item, 'STUDENT') as student, login(item, 'INTERN_MENTOR') as teacher, login(item) as school:
        for period in ['2026-09', '2026-10']:
            report = submit(student, item, 'MONTHLY', period); review(teacher, item, report, 'MONTHLY')
        submit(student, item, 'MONTHLY', '2026-11')
        returned = submit(student, item, 'SUMMARY', 'FINAL'); review(teacher, item, returned, 'SUMMARY', 'RETURN')
        with get_sessionmaker()() as db:
            for kind, period, status, deleted in [('MONTHLY', '2026-12', 'DRAFT', False),
                    ('MONTHLY', '2026-08', 'APPROVED', True)]:
                db.add(InternshipProcessReport(tenant_id=int(item['tenantId']), internship_id=int(item['recordId']),
                    report_type=kind, period_key=period, content='新测试学校的排除计数前置',
                    status=status, is_deleted=deleted, submitted_at=datetime(2026, 9, 1)))
            db.commit()
        computed, snapshot = compute_and_read(teacher, school, item)
        source = snapshot['sourceManifest']['facts']['monthly']
        assert source['expected'] == 2 and source['actual'] == 1 and len(source['rows']) == 2
        assert computed['suggestedScores']['monthly'] == 50
        assert computed['suggestedScores']['weekly'] == 0


@pytest.mark.parametrize('weekly', [{}, {'requiredCount': 0}])
def test_unconfigured_reports_remain_missing_and_cannot_be_adjusted_reviewed_or_published(record_property, weekly):
    item = workspace({'weeklyReport': weekly, 'processReport': {
        'monthlyRequiredCount': 0, 'summaryRequiredCount': 0}}, record_property)
    with login(item, 'INTERN_MENTOR') as teacher, login(item) as school:
        computed, snapshot = compute_and_read(teacher, school, item)
        assert computed['suggestedScores']['weekly'] is None and computed['suggestedScores']['monthly'] is None
        assert computed['incomplete'] is True and computed['total'] is None
        assert snapshot['finalScores']['weekly'] is None and snapshot['finalScores']['monthly'] is None
        assert snapshot['sourceManifest']['facts']['weekly']['expected'] == 0
        assert snapshot['sourceManifest']['facts']['monthly']['expected'] == 0
        for action in ['review', 'publish']:
            denied = school.post(STAFF + '/scores/' + computed['id'] + '/' + action,
                                 json={'expectedVersion': computed['version']})
            assert denied.status_code == 400 and denied.json()['bizCode'] == 'DATA_CONFLICT', denied.text
        evidence = upload(teacher, biz='INTERNSHIP_SCORE_ADJUSTMENT')
        denied = teacher.post(STAFF + '/scores/compute', json={'internshipId': item['recordId'],
            'expectedVersion': computed['version'], 'manualAdjustments': {'weekly': 1},
            'adjustmentReason': '合成核对缺少权威报告来源', 'adjustmentEvidenceFileIds': [evidence['fileId']]})
        assert denied.status_code == 400 and denied.json()['bizCode'] == 'DATA_CONFLICT', denied.text
        assert '缺少权威来源' in denied.json()['message']
        with get_sessionmaker()() as db:
            score = db.get(InternshipFinalScore, int(computed['id']))
            assert score.version == computed['version'] and score.status == 'PENDING_REVIEW'
            assert score.total_score is None
            assert db.scalar(select(FileBinding.id).where(FileBinding.file_id == int(evidence['fileId']))) is None
