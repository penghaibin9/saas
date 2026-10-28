"""Read-only business handoff contracts; no database is connected or changed."""
from contextlib import nullcontext
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select


def test_archive_missing_actions_target_current_record_and_never_reuse_incident_id():
    from app.modules.internship.services.internship_archive_service import _missing_actions
    record = 9007199254741003
    codes = ['eligibility', 'advisor', 'visit', 'openIncident']
    actions = _missing_actions([{'code': code, 'label': code} for code in codes], record)
    routes = {row['code']: urlsplit(row['path']) for row in actions}
    assert routes['eligibility'].path == f'/admin/internship/students/{record}'
    assert parse_qs(routes['eligibility'].query) == {'section': ['eligibility']}
    assert parse_qs(routes['advisor'].query) == {'panel': ['mentor'], 'advisorId': [str(record)]}
    assert routes['visit'].path == '/admin/internship/guidance'
    assert parse_qs(routes['visit'].query) == {'panel': ['visit']}
    assert routes['openIncident'].path == '/admin/internship/compliance'
    assert parse_qs(routes['openIncident'].query) == {'tab': ['incidents'], 'internshipId': [str(record)]}
    assert all('participants' not in route.path for route in routes.values())


def test_school_opening_orders_batch_students_and_advisors_before_approver_preview(monkeypatch):
    from app.models import StudentProfile
    from app.services import system_settings as settings
    query = select(StudentProfile)
    db = SimpleNamespace(scalar=lambda *_: 0)
    monkeypatch.setattr(settings, 'enforce_permission', lambda *_: None)
    monkeypatch.setattr(settings, 'has_permission', lambda *_: False)
    monkeypatch.setattr(settings, 'get_sessionmaker', lambda: lambda: nullcontext(db))
    for name in ['scoped_students', 'scoped_staff', 'people_query', 'tenant_query']:
        monkeypatch.setattr(settings.sm, name, lambda *_, **__: query)
    monkeypatch.setattr(settings.sm, 'school_wide', lambda *_: False)
    monkeypatch.setattr(settings.sm, 'ids', lambda *_: (7, 11))
    paths = [step['path'] for step in settings.overview({})['steps']]
    assert paths.index('/admin/system/organizations') < paths.index('/admin/system/identity-import/staff')
    assert paths.index('/admin/system/identity-import/students') < paths.index('/admin/system/roles')
    assert paths.index('/admin/system/scopes') < paths.index('/admin/internship/batches?panel=list')
    assert paths.index('/admin/internship/batches?panel=list') < paths.index('/admin/internship/students?panel=mentor')
    assert paths.index('/admin/internship/students?panel=mentor') < paths.index('/admin/system/leave-policy')
    assert paths.index('/admin/system/leave-policy') < paths.index('/admin/internship/plans')
