"""Exercise the student routes' paging contract without a database."""
from app.student_portal import internship_router as portal
from app.api.v1 import mobile_internship_student as mobile


def test_student_routes_forward_pagination_to_authoritative_service(monkeypatch):
    calls = []
    def record(user, **kwargs):
        calls.append((user, kwargs))
        return {'items': [], 'page': kwargs['page'], 'total': 21}
    monkeypatch.setattr(portal.reports, 'list_weekly', record)
    monkeypatch.setattr(portal.reports, 'list_my', record)
    actor = {'userId': '9007199254741001'}
    common = dict(batchId=18, internshipId=18, page=2, pageSize=20, focusReportId=42, user=actor)
    portal.portal_weekly_report_list(**common)
    portal.portal_report_list(**common, reportType='DAILY')
    mobile.my_selected_weekly_reports(**common)
    mobile.my_selected_reports(**common, reportType='DAILY')
    assert len(calls) == 4
    for user, args in calls:
        assert user == actor
        assert args == dict(batch_id=18, internship_id=18, page=2, page_size=20, focus_report_id=42,
                            **({'report_type': 'DAILY'} if 'report_type' in args else {}))


def test_weekly_export_uses_school_dates_and_current_review(monkeypatch):
    from datetime import timezone, timedelta
    from app.core import timeutil
    from app.modules.internship.services import internship_service as service, internship_export_util as export
    from app.services import xlsx_util
    monkeypatch.setattr(timeutil, 'tenant_tz', lambda: timezone(timedelta(hours=8)))
    item = dict(studentName='合成学生', className='合成班级', enterpriseName='合成企业', week=1,
                submitAt='2026-10-06T16:30:00', version=3, reportVersion='v2', wordCount=30, riskFlag='', statusLabel='已批阅',
                review=dict(ratingLevel=4, reviewerName='合成教师', reviewedAt='2026-10-06T17:00:00Z', comment='通过'))
    monkeypatch.setattr(export, 'load_export_rows', lambda *a, **k: ([item], 1))
    monkeypatch.setattr(service, '_op_name', lambda: '合成教师')
    rows = []
    monkeypatch.setattr(xlsx_util, 'build_ledger_xlsx', lambda title, headers, values, **kwargs: rows.extend(values) or b'file')
    monkeypatch.setattr(xlsx_util, 'pack_xlsx_result', lambda *a: {})
    service.export_weekly_reports()
    assert rows[0][4] == '2026-10-07 00:30'
    assert rows[0][5] == 2
    assert rows[0][9:13] == [4, '合成教师', '2026-10-07 01:00', '通过']
