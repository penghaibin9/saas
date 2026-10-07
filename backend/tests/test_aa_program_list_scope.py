"""培养方案列表必须与单条办理使用同一学院/班级范围。"""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("scope_type,allowed,visible", [
    ("COLLEGE", {11}, (11,)),
    ("CLASS", set(), ()),
    ("TENANT_ALL", set(), None),
])
def test_program_list_filters_before_count_and_pagination(monkeypatch, scope_type, allowed, visible):
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_program_governance_service as governance

    class Db:
        def __init__(self):
            self.queries = []

        def scalar(self, statement):
            self.queries.append(statement)
            return 0

        def scalars(self, statement):
            self.queries.append(statement)
            return SimpleNamespace(all=lambda: [])

    db = Db()
    monkeypatch.setattr(core, "session", lambda: nullcontext(db))
    monkeypatch.setattr(core, "_tid", lambda: 1)
    monkeypatch.setattr(governance, "_scope", lambda _user, _db: SimpleNamespace(scope_type=scope_type))
    monkeypatch.setattr(governance, "_allowed_major_ids", lambda _db, _scope: allowed)

    rows, total = core.list_programs({"currentRoleCode": "COLLEGE_ADMIN"})
    assert rows == [] and total == 0
    assert len(db.queries) == 2
    for statement in db.queries:
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        if visible is None:
            assert "t_aa_program.major_id IN" not in sql
        elif visible:
            assert "t_aa_program.major_id IN (11)" in sql
        else:
            assert "t_aa_program.major_id IN (NULL)" in sql


@pytest.mark.parametrize("operation", ["get_credit_requirements", "update_program"])
def test_program_read_and_edit_stop_before_out_of_scope_data(monkeypatch, operation):
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core

    program = SimpleNamespace(id=7, tenant_id=1, is_deleted=False, status="DRAFT")

    class Db:
        def get(self, _model, _id):
            return program

        def commit(self):
            pytest.fail("跨学院方案不应写入")

    monkeypatch.setattr(core, "session", lambda: nullcontext(Db()))
    monkeypatch.setattr(core, "_tid", lambda: 1)

    def reject(_db, _program, _user):
        raise PermissionError("跨学院方案")

    monkeypatch.setattr(core, "_ensure_program_scope", reject)
    with pytest.raises(PermissionError, match="跨学院方案"):
        if operation == "update_program":
            core.update_program(7, {}, SimpleNamespace(programName="不应保存"))
        else:
            core.get_credit_requirements(7, {})
