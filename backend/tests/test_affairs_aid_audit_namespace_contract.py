from types import SimpleNamespace

import app.models as models
from app.services import affairs_aid_service as aid
from app.services import affairs_data_integrity_guard as guard


class _Db:
    def __init__(self):
        self.rows = []

    def add(self, row):
        self.rows.append(row)


def test_aid_batch_audit_uses_distinct_namespace(monkeypatch):
    """批次与申请即使数字 ID 相同，也不得落到同一个 AID 审计键。"""
    application_calls = []

    def application_audit(db, biz_id, action, detail="", before="", after=""):
        application_calls.append((biz_id, action, detail, before, after))

    class _Trail:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    monkeypatch.setattr(aid, "_audit", application_audit)
    monkeypatch.setattr(aid, "_op", lambda: ("验收管理员", "STUDENT_AFFAIRS_ADMIN", "99"))
    monkeypatch.setattr(guard, "_tid", lambda: 1001)
    monkeypatch.setattr(models, "AffairsAuditTrail", _Trail)

    guard._patch_aid_audit_namespace()

    db = _Db()
    aid._audit(db, 1, "BATCH_CREATE", "publish=True")
    aid._audit(db, 1, "APPLY", "level=DIFFICULT")

    assert len(db.rows) == 1
    batch_row = db.rows[0]
    assert batch_row.tenant_id == 1001
    assert batch_row.biz_type == "AID_BATCH"
    assert batch_row.biz_id == 1
    assert batch_row.action == "BATCH_CREATE"
    assert application_calls == [(1, "APPLY", "level=DIFFICULT", "", "")]
