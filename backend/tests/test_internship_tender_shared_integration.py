"""实习新增能力接公共上传、审批和文件授权的回归。"""
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.core.exceptions import AppException


@pytest.mark.parametrize(('ext', 'content', 'mime'), [
    ('mp4', b'\x00\x00\x00\x18ftypisom', 'video/mp4'),
    ('webm', b'\x1aE\xdf\xa3' + bytes(16), 'video/webm'),
    ('rar', b'Rar!\x1a\x07\x01\x00' + bytes(16), 'application/vnd.rar'),
])
def test_report_media_requires_matching_signature_and_internship_purpose(ext, content, mime):
    from app.services.file_content_security import validate_content
    assert validate_content(filename='材料.'+ext, declared_content_type=mime, data=content,
                            ext=ext, biz_type='INTERNSHIP_REPORT', source='USER')[0] == mime
    for payload, purpose in [(b'<script>forged</script>', 'INTERNSHIP_REPORT'), (content, 'ATTACHMENT')]:
        with pytest.raises(AppException):
            validate_content(filename='材料.'+ext, declared_content_type=mime, data=payload,
                             ext=ext, biz_type=purpose, source='USER')


def test_report_upload_never_accepts_client_business_binding(monkeypatch):
    import asyncio
    from app.api.v1 import file_contract
    captured = {}

    async def store(file, biz_type, **kwargs):
        captured.update(biz_type=biz_type, **kwargs)
        return {'fileId': '123', 'fileName': file.filename, 'scanStatus': 'PENDING',
                'scanRequired': True, 'readyForBusiness': False}

    monkeypatch.setattr(file_contract.file_service, 'store_upload', store)
    monkeypatch.setattr(file_contract.audit_log, 'record', lambda *args, **kwargs: None)
    reply = asyncio.run(file_contract.upload_contract(
        UploadFile(filename='周报.mp4', file=BytesIO(b'\x00\x00\x00\x18ftypisom')),
        biz_type='INTERNSHIP_REPORT', biz_id='someone-elses-report',
        user={'userId': 'test-upload', 'userType': 'STUDENT'}))
    assert captured['biz_type'] == 'TEMP_PRIVATE'
    assert captured['biz_id'] is None
    assert captured['visibility'] == 'PRIVATE'
    assert captured['validation_biz_type'] == 'INTERNSHIP_REPORT'
    assert reply['bindingCreated'] is False
    assert reply['allowedActions'] == ['viewMetadata']
    assert reply['readyForBusiness'] is False


def test_generic_approval_rejects_internship_leave_without_changing_other_leave():
    from app.services.db_service import require_generic_approval_source
    from app.services.approval_runtime_service import _task_can_act
    instance = SimpleNamespace(source_module='internship', source_biz_type='LEAVE')
    with pytest.raises(AppException, match='实习请假审批'):
        require_generic_approval_source(instance)
    assert _task_can_act(None, None, instance, {}) is False
    require_generic_approval_source(SimpleNamespace(source_module='student-affairs', source_biz_type='LEAVE'))


def test_business_context_uses_internship_leave_adapter_not_student_affairs(monkeypatch):
    from app.services import approval_business_context_service as context
    seen = []
    monkeypatch.setattr(context, '_internship_leave_context',
                        lambda *args, **kwargs: seen.append('internship') or {'completeness': context.FULL})
    monkeypatch.setitem(context._ADAPTERS, 'LEAVE',
                        lambda *args, **kwargs: seen.append('student-affairs') or {'completeness': context.FULL})
    context.resolve_context(None, SimpleNamespace(source_module='internship', source_biz_type='LEAVE', source_biz_id=7))
    assert seen == ['internship']


def test_new_file_types_have_business_resolvers_without_replacing_other_centers():
    from app.services.file_access_service import resolver_registry_snapshot, _ensure_builtin_resolvers
    from app.services.file_public_acl_guard import install
    install()
    _ensure_builtin_resolvers()
    registry = resolver_registry_snapshot()
    for kind in ('INTERNSHIP_CHECKIN', 'INTERNSHIP_CUSTOM_MATERIAL', 'INTERNSHIP_MATERIAL_TEMPLATE',
                 'INTERNSHIP_PAYROLL_VERSION', 'INTERNSHIP_FORMAL_DOCUMENT', 'INTERNSHIP_EMPLOYMENT',
                 'INTERNSHIP_TEACHER_CHECKIN', 'INTERNSHIP_TEACHER_PERIOD_REPORT'):
        assert 'file_internship_tender_resolvers' in registry[kind]
    assert 'graduation_material_resolver' in registry['GRADUATION_MATERIAL']
    assert 'funding' in registry['FUNDING']
