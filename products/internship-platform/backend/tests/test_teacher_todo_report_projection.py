from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.v1.teacher_mobile_workbench import _todo


def projection(kind):
    return _todo(SimpleNamespace(
        id=9007199254740993101, todo_type=kind, source_biz_id=9007199254740993102,
        source_biz_type='PROCESS_REPORT', title='合成报告待批阅', status='PENDING',
        due_at=None, created_at=datetime(2026, 10, 16), student_id=9007199254740993103))


@pytest.mark.parametrize('kind', ['INTERN_DAILY_REVIEW', 'INTERN_MONTHLY_REVIEW', 'INTERN_SUMMARY_REVIEW'])
def test_process_report_todo_opens_exact_source_without_batch_guessing(kind):
    row=projection(kind)
    assert row['actionPath']=='/pages/teacher-internship/process-report-review/index?reportId=9007199254740993102'
    assert row['sourceBizId']=='9007199254740993102' and row['group']=='REPORT'


def test_unknown_todo_keeps_internal_type_but_has_chinese_label_and_no_write_entry():
    row=projection('UNKNOWN_INTERNAL_KIND')
    assert row['todoType']=='UNKNOWN_INTERNAL_KIND'
    assert row['typeLabel']=='岗位实习待办' and row['actionPath']==''


def test_attendance_todo_opens_its_exception_instead_of_the_weekly_queue():
    row=projection('INTERN_EXCEPTION_HANDLE')
    assert row['actionPath']=='/pages/teacher-internship/internship-review/index?tab=abnormal&exceptionId=9007199254740993102'
    assert row['group']=='ATTENDANCE'


@pytest.mark.parametrize('kind,target,key', [
    ('INTERN_EXEMPTION_APPROVAL', 'checkin-exemption', 'exemptionId'),
    ('INTERN_APPLICATION_REVIEW', 'internship-application', 'applicationId'),
    ('INTERN_EXEMPTION_APPLICATION', 'internship-application', 'applicationId'),
    ('INTERN_CHANGE_APPROVAL', 'internship-change', 'changeId'),
    ('INTERN_ENTERPRISE_CHANGE', 'internship-change', 'changeId'),
])
def test_todo_includes_authoritative_batch_and_original_id(kind, target, key):
    source = SimpleNamespace(id=1, todo_type=kind, source_biz_id=9007199254740993,
        source_biz_type='TEST', title='虚构待办', status='PENDING', due_at=None,
        created_at=None, student_id=None)
    row = _todo(source, batch_id=7)
    assert row['actionPath'] == f'/pages/teacher-internship/{target}/index?batchId=7&{key}=9007199254740993'
