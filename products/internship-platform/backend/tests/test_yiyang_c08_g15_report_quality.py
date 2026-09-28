from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.internship.services import internship_report_quality_service as svc


def test_g15_default_rules_and_minimum_words():
    assert svc.DEFAULT_RULES["weeklyMinWords"] == 30
    assert svc.DEFAULT_RULES["monthlyMinWords"] == 100
    assert svc.DEFAULT_RULES["summaryMinWords"] == 300
    assert svc.minimum_words(svc.DEFAULT_RULES, "DAILY") == 30
    assert svc.minimum_words(svc.DEFAULT_RULES, "MONTHLY") == 100
    assert svc.minimum_words(svc.DEFAULT_RULES, "SUMMARY") == 300


def test_g15_attachment_validation_accepts_images_and_videos(monkeypatch):
    metas = {
        "img": {
            "fileId": "img", "fileName": "现场.jpg", "mimeType": "image/jpeg",
            "sizeBytes": 123, "sha256": "a" * 64,
        },
        "vid": {
            "fileId": "vid", "fileName": "过程.mp4", "mimeType": "video/mp4",
            "sizeBytes": 456, "sha256": "b" * 64,
        },
    }
    monkeypatch.setattr(svc.file_service, "get_file_meta", lambda fid: metas.get(fid))
    ids, views = svc.validate_attachments(["img", "vid", "img"], svc.DEFAULT_RULES)
    assert ids == ["img", "vid"]
    assert [v["kind"] for v in views] == ["IMAGE", "VIDEO"]
    assert views[0]["sha256"] == "a" * 64


def test_g15_attachment_limits_are_server_enforced(monkeypatch):
    monkeypatch.setattr(
        svc.file_service,
        "get_file_meta",
        lambda fid: {
            "fileId": fid, "fileName": f"{fid}.jpg", "mimeType": "image/jpeg",
            "sizeBytes": 1, "sha256": "c" * 64,
        },
    )
    with pytest.raises(AppException):
        svc.validate_attachments(
            ["1", "2"],
            {**svc.DEFAULT_RULES, "maxImages": 1},
        )


class _FakeDb:
    def scalar(self, _query):
        return None

    def add(self, value):
        self.value = value

    def flush(self):
        if getattr(self, "value", None) is not None and getattr(self.value, "id", None) is None:
            self.value.id = 99


def _row(report_type="MONTHLY"):
    return SimpleNamespace(id=10, report_type=report_type)


def _user():
    return {"userId": "7", "realName": "指导教师"}


def test_g15_approve_requires_five_level_rating(monkeypatch):
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "latest_process_snapshot",
        lambda db, report_id: SimpleNamespace(id=88),
    )
    with pytest.raises(AppException) as exc:
        svc.record_process_review(
            _FakeDb(), row=_row(), action="APPROVE", comment="通过",
            user=_user(), rating_level=None, summary_score=None,
        )
    assert "五级评价" in str(exc.value)


def test_g15_summary_requires_0_to_100_score(monkeypatch):
    monkeypatch.setattr(
        svc,
        "latest_process_snapshot",
        lambda db, report_id: SimpleNamespace(id=88),
    )
    with pytest.raises(AppException):
        svc.record_process_review(
            _FakeDb(), row=_row("SUMMARY"), action="APPROVE", comment="通过",
            user=_user(), rating_level=5, summary_score=101,
        )
    with pytest.raises(AppException):
        svc.record_process_review(
            _FakeDb(), row=_row("SUMMARY"), action="APPROVE", comment="通过",
            user=_user(), rating_level=5, summary_score=None,
        )


def test_g15_return_can_be_unrated_but_is_version_bound(monkeypatch):
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "latest_process_snapshot",
        lambda db, report_id: SimpleNamespace(id=88),
    )
    db = _FakeDb()
    review = svc.record_process_review(
        db, row=_row("SUMMARY"), action="RETURN", comment="请补充现场过程",
        user=_user(), rating_level=None, summary_score=None,
    )
    assert review.report_version_id == 88
    assert review.action == "RETURN"
    assert review.rating_level is None
    assert review.summary_score is None
