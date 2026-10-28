"""Shared material route forwarding and package cleanup; no database access."""
import asyncio
from fastapi.responses import FileResponse
import pytest
from app.api.v1 import mobile_internship_context as teacher, mobile_internship_student as student
from app.modules.internship.routers import internship_material_center as routes


def test_material_routes_keep_filters_version_and_package_cleanup(monkeypatch, tmp_path):
    actor = {'userId': '9007199254741001'}
    calls = []
    def coverage(requirement_id, **kwargs):
        calls.append((requirement_id, kwargs))
        return {'total': 1}
    monkeypatch.setattr(routes.requirement_svc, 'coverage', coverage)
    routes.material_requirement_coverage(2, keyword='合成', collegeId=11, majorId=12, classId=13, user=actor)
    teacher.teacher_material_requirement_coverage(2, keyword='合成', user=actor)
    assert calls == [(2, dict(user=actor, keyword='合成', college_id=11, major_id=12, class_id=13)),
                     (2, dict(user=actor, keyword='合成'))]
    package = tmp_path / 'package.zip'
    package.write_bytes(b'PK')
    template_calls = []
    monkeypatch.setattr(routes.requirement_svc, 'template_download',
                        lambda requirement_id, user, **kwargs: template_calls.append(kwargs) or (package, '材料.xlsx'))
    monkeypatch.setattr(routes, 'validated_local_file_response', lambda path, **kwargs: FileResponse(path))
    monkeypatch.setattr(student, 'validated_local_file_response', lambda path, **kwargs: FileResponse(path))
    routes.material_requirement_template_download(2, templateVersionId=42, user=actor)
    student.my_material_template_download(2, batchId=18, internshipId=18, templateVersionId=42, user=actor)
    assert template_calls == [dict(template_version_id=42), dict(batch_id=18, internship_id=18, template_version_id=42)]
    monkeypatch.setattr(routes.requirement_svc, 'build_material_package', lambda *a, **k: (package, '材料.zip'))
    params = dict(state='SUBMITTED', keyword='', collegeId=None, majorId=None, classId=None, user=actor)
    response = routes.material_requirement_package_download(2, **params)
    asyncio.run(response.background())
    assert not package.exists()
    package.write_bytes(b'PK')
    def denied(*a, **k):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr(routes, 'validated_local_file_response', denied)
    with pytest.raises(RuntimeError):
        routes.material_requirement_package_download(2, **params)
    assert not package.exists()
