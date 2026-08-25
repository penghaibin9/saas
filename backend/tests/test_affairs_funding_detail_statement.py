from types import SimpleNamespace

from app.services import affairs_funding_service as funding


class _Session:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_funding_statement_is_detail_only(monkeypatch):
    """审核所需申请说明必须在单笔详情可见，但不得扩散到列表投影。"""
    application = SimpleNamespace(
        id=7,
        batch_id=3,
        student_id=11,
        project_type="SCHOLARSHIP",
        apply_source="SELF",
        amount=None,
        status="COUNSELOR_REVIEW",
        return_reason=None,
        version=2,
        check_snapshot_json='{"type":"SCHOLARSHIP","statusOk":true,"disciplineOk":true,"gradeOk":true}',
        statement="本学年学习表现稳定并积极参加集体活动，申请奖学金。",
    )
    student = SimpleNamespace(student_no="E2E20260001", real_name="E2E学生A")

    monkeypatch.setattr(funding, "session", lambda: _Session())
    monkeypatch.setattr(funding, "_load", lambda _db, _app_id: (application, student))
    monkeypatch.setattr(funding, "_scope_or_403", lambda _db, _student_id, _user: None)
    monkeypatch.setattr(funding, "_pending_appeal_ids", lambda _db, _ids: set())

    list_row = funding._app_row(application, {}, student)
    detail_row = funding.get_application("7", {})

    assert "statement" not in list_row
    assert detail_row["statement"] == application.statement
    assert detail_row["checkSnapshot"]["statusOk"] is True
