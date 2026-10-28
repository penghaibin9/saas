"""Shared file readiness and directory scope; no database connection."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import mysql

from app.api.v1 import org_directory
from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.services import file_access_service, file_service, mobile_teacher_service


@pytest.mark.parametrize('missing', ['major', 'college', None])
def test_directory_keeps_visible_class_when_parent_chain_is_incomplete(monkeypatch, request, missing):
    set_tenant({'tenantId': '12'})
    request.addfinalizer(lambda: set_tenant(None))
    monkeypatch.setattr(org_directory, '_visible_student_ids', lambda _: None)
    school_class = SimpleNamespace(id=1, major_id=2, class_name='合成班级', grade='2026', class_status='ACTIVE')
    major = SimpleNamespace(id=2, college_id=3, major_name='合成专业')
    college = SimpleNamespace(id=3, college_name='合成学院')
    db = MagicMock()
    results = [[school_class], [] if missing == 'major' else [major]]
    if missing != 'major':
        results.append([] if missing == 'college' else [college])
    db.scalars.return_value.all.side_effect = results
    db.execute.return_value.all.return_value = [(1, 4)]
    monkeypatch.setattr(org_directory, 'get_sessionmaker', lambda: lambda: db)
    tree = org_directory.org_tree({'currentRoleCode': 'SCHOOL_ADMIN'})['data']['tree']
    assert tree[0]['value'] == ('3' if missing is None else '__ORPHAN__')
    leaf = tree[0]['children'][0]['children'][0]
    assert leaf['value'] == '1' and leaf['studentCount'] == 4
    db.close.assert_called_once()


def test_shared_metadata_requires_explicit_safe_scan_state(monkeypatch):
    monkeypatch.setattr(file_access_service, 'authorize_file_object',
                        lambda row, *a, **kw: file_access_service._scan_ready(row))
    row = SimpleNamespace(id=1, file_name='合成材料.pdf', ext='pdf', mime_type='application/pdf',
                          size_bytes=1, sha256='test', file_key='test', biz_type='', biz_id='', status='AVAILABLE')
    for scan, ready in [(None, False), ('', False), ('UNKNOWN', False), ('PENDING', False),
                        ('INFECTED', False), ('CLEAN', True), ('NOT_REQUIRED', True)]:
        row.scan_status = scan
        assert file_access_service._scan_ready(row) is ready
        assert file_service._meta(row)['readyForBusiness'] is ready
        view = file_access_service.file_view(row, user={}, bindings=[], db=None)
        assert view['readyForBusiness'] is ready
        assert ('download' in view['allowedActions']) is ready
        assert view['scanStatus'] == (scan or '')
    row.status = 'DELETED'
    assert not file_access_service._scan_ready(row)
    assert not file_service._meta(row)['readyForBusiness']


def test_directory_rejects_non_staff_and_unavailable_scope(monkeypatch):
    for role in ['STUDENT', 'PARENT', 'GUARDIAN', 'PLATFORM_SUPER_ADMIN']:
        with pytest.raises(AppException):
            org_directory._visible_student_ids({'currentRoleCode': role})
    monkeypatch.setattr(mobile_teacher_service, 'resolve_teacher_scope', lambda _: {'mode': 'UNAVAILABLE'})
    with pytest.raises(AppException):
        org_directory._visible_student_ids({'currentRoleCode': 'INTERN_MENTOR'})


def test_directory_scope_keeps_tenant_current_advisor_and_empty_scope(monkeypatch, request):
    set_tenant({'tenantId': '12'})
    request.addfinalizer(lambda: set_tenant(None))
    monkeypatch.setattr(mobile_teacher_service, 'resolve_teacher_scope',
                        lambda _: {'mode': 'SCOPED', 'roleCode': 'INTERN_MENTOR', 'advisorUserIds': {38}})
    query = org_directory._visible_student_ids({'currentRoleCode': 'INTERN_MENTOR'})
    sql = str(query.compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
    assert 'tenant_id = 12' in sql and 'advisor_user_id IN (38)' in sql
    monkeypatch.setattr(mobile_teacher_service, 'resolve_teacher_scope',
                        lambda _: {'mode': 'SCOPED', 'roleCode': 'COUNSELOR'})
    query = org_directory._visible_student_ids({'currentRoleCode': 'COUNSELOR'})
    sql = str(query.compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
    assert 'false' in sql.lower() or '0 = 1' in sql
