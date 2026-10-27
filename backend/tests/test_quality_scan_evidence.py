from datetime import datetime
import pytest
from sqlalchemy import select
from app.core.exceptions import AppException

def test_skipped_rules_never_close_issues_and_scores_require_coverage(db_mode,monkeypatch):
    from app.core.context import set_tenant,set_current_user
    from app.db.session import get_sessionmaker
    from app.models.master_data_governance import DataDomain,DataQualityRule,DataQualityIssue
    from app.services import master_data_governance_service as md
    tid=1000000000000000001
    actor={'userId':'db-900001','tenantId':str(tid),'currentRoleCode':'SCHOOL_ADMIN','realName':'质量验收管理员'}
    set_tenant({'tenantId':tid});set_current_user(actor)
    with get_sessionmaker()() as db:
        db.add(DataDomain(tenant_id=tid,domain_code='D606',domain_name='虚构质量域',owner_module='systemAdmin',authoritative_table='fixture'))
        db.add(DataQualityRule(tenant_id=tid,domain_code='D606',rule_code='D606_RULE',rule_name='虚构检查',rule_type='MISSING',severity='P1',executor_key='D606_EXECUTOR',status='ACTIVE'))
        issue=DataQualityIssue(tenant_id=tid,domain_code='D606',rule_code='D606_RULE',issue_key='D606_ISSUE',severity='P1',status='OPEN',summary='虚构问题',first_seen_at=datetime.now(),last_seen_at=datetime.now())
        db.add(issue);db.commit();identifier=issue.id
    assert md.list_domains(tenant_id=tid)['list'][0]['qualityScore'] is None
    skipped=md.scan(tenant_id=tid,rule_code='D606_RULE',user=actor)
    assert skipped['cleared']==0 and skipped['skippedRules']
    with get_sessionmaker()() as db:
        issue=db.get(DataQualityIssue,identifier);assert issue.status=='OPEN'
        issue.status='VERIFIED';db.commit()
    monkeypatch.setitem(md.EXECUTORS,'D606_EXECUTOR',lambda db,tenant:[{'issueKey':'D606_ISSUE','summary':'虚构问题重新出现'}])
    md.scan(tenant_id=tid,rule_code='D606_RULE',user=actor)
    with get_sessionmaker()() as db:
        assert db.get(DataQualityIssue,identifier).status=='OPEN'
    domain=md.list_domains(tenant_id=tid)['list'][0]
    assert domain['checkedRuleCount']==1 and domain['activeRuleCount']==1 and domain['lastScanAt']
    assert domain['qualityScore']==92
    monkeypatch.setitem(md.EXECUTORS,'D606_EXECUTOR',lambda db,tenant:[])
    md.scan(tenant_id=tid,rule_code='D606_RULE',user=actor)
    with pytest.raises(AppException): md.verify_issue(identifier,tenant_id=tid,user=actor)
    with get_sessionmaker()() as db:
        assert db.get(DataQualityIssue,identifier).status=='VERIFIED'


def test_scanners_do_not_silently_truncate_relationship_or_student_findings(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College,Major,SchoolClass,StudentProfile
    from app.services import master_data_governance_service as md
    tid=1000000000000000001
    with get_sessionmaker()() as db:
        college=College(tenant_id=tid,college_name='D606分页学院');db.add(college);db.flush()
        major=Major(tenant_id=tid,college_id=college.id,major_name='D606分页专业');db.add(major);db.flush()
        classes=[SchoolClass(tenant_id=tid,major_id=major.id,class_name=f'D606分页班{i}',status='ACTIVE') for i in range(21)]
        students=[StudentProfile(tenant_id=tid,student_no=f'D606-P{i}',real_name=f'虚构分页学生{i}') for i in range(501)]
        db.add_all(classes+students);db.commit()
        assert {str(row.id) for row in classes} <= {row['objectId'] for row in md._scan_class_missing_counselor(db,tid)}
        assert {str(row.id) for row in students} <= {row['objectId'] for row in md._scan_student_missing_class(db,tid)}
