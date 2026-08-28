from types import SimpleNamespace

from app.services import affairs_aid_service as aid


class _Session:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_aid_statement_is_detail_only(monkeypatch):
    """审核所需困难说明必须在单笔详情可见，但不得扩散到列表投影。"""
    application = SimpleNamespace(
        id=7,
        batch_id=3,
        student_id=11,
        apply_level="DIFFICULT",
        suggest_level=None,
        final_level=None,
        status="CLASS_REVIEW",
        return_reason=None,
        version=2,
        statement="家庭收入下降且近期医疗支出增加，请予困难认定。",
    )
    student = SimpleNamespace(student_no="E2E20260001", real_name="E2E学生A")

    monkeypatch.setattr(aid, "session", lambda: _Session())
    monkeypatch.setattr(aid, "_load", lambda _db, _apply_id: (application, student))
    monkeypatch.setattr(aid, "_scope_or_403", lambda _db, _student_id, _user: None)
    monkeypatch.setattr(aid, "_family_of", lambda _db, _apply_id: None)
    monkeypatch.setattr(aid, "_pending_objection_ids", lambda _db, _ids: set())

    list_row = aid._apply_row(application, student, None)
    detail_row = aid.get_application("7", {})

    assert "statement" not in list_row
    assert detail_row["statement"] == application.statement
