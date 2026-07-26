"""V2-01 教学任务生成前的方案质量门禁。"""
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException


def test_generation_precheck_requires_enabled_program(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_task_program_gate_facade as service

    monkeypatch.setattr(service, "_generation_programs", lambda _db, _user, _college: [])
    with pytest.raises(AppException) as exc:
        service._generation_precheck(object(), {}, None)

    assert exc.value.http_status == 409
    assert exc.value.code == "PROGRAM_NOT_READY"


def test_generation_precheck_blocks_invalid_enabled_program(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_task_program_gate_facade as service

    program = SimpleNamespace(id=7, program_name="软件技术2026级")
    monkeypatch.setattr(service, "_generation_programs", lambda _db, _user, _college: [program])
    monkeypatch.setattr(service, "validate_program_db", lambda _db, _pid: {
        "counts": {"warning": 1},
        "issues": [{"level": "BLOCKER", "message": "课程模块未配置"}],
    })

    with pytest.raises(AppException) as exc:
        service._generation_precheck(object(), {}, 2)

    assert exc.value.http_status == 409
    assert exc.value.code == "PROGRAM_VALIDATION_BLOCKED"
    assert "软件技术2026级" in exc.value.message


def test_generation_precheck_accepts_valid_program_and_counts_warnings(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_task_program_gate_facade as service

    programs = [SimpleNamespace(id=1, program_name="A"), SimpleNamespace(id=2, program_name="B")]
    monkeypatch.setattr(service, "_generation_programs", lambda _db, _user, _college: programs)
    monkeypatch.setattr(service, "validate_program_db", lambda _db, program_id: {
        "counts": {"warning": program_id},
        "issues": [{"level": "WARNING", "message": "提醒"}],
    })

    result = service._generation_precheck(object(), {}, None)

    assert result == {"programCount": 2, "warningCount": 3}


def test_public_task_service_uses_program_gate_above_security_workbench():
    from app.modules.academic_affairs import services

    task_service = services.academic_affairs_task_service
    assert task_service.__name__.endswith("academic_affairs_task_program_gate_facade")
    assert task_service.generate_batch.__module__.endswith("academic_affairs_task_program_gate_facade")
    assert task_service._base.__name__.endswith("academic_affairs_task_security_facade")
