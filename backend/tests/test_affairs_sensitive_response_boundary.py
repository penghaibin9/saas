"""Regression controls for alternate sensitive response paths; DB cases use isolated MySQL."""
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import affairs_funding_authority_service as authority
from app.services import affairs_funding_service as funding


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def mappings(self):
        return self


class _Session:
    def __init__(self, rows=()):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def scalars(self, statement):
        return _Rows([])

    def execute(self, statement, params):
        return _Rows(self.rows)


@pytest.mark.parametrize("source", ["FUNDING_PROJECT", "DUAL_REVIEW_ADJUSTMENT"])
def test_teacher_amount_snapshot_uses_same_confidentiality_as_top_level(monkeypatch, source):
    from app.core import permissions
    monkeypatch.setattr(permissions, "_db_granted", lambda user, **kwargs:
                        {"studentAffairs.funding.sensitiveView"} if user.get("currentRoleCode") == "FUNDING_TEACHER" else None)
    snapshot = {"statusOk": True, "disciplineOk": True, "amountAuthority": {
        "source": source, "amount": "6789.12", "reason": "申请调整至6789.12元",
        "requesterId": 701, "reviewerId": 702,
    }}
    application = SimpleNamespace(id=7, student_id=11, statement="申请说明应当保留",
                                  check_snapshot_json=json.dumps(snapshot))
    monkeypatch.setattr(funding, "session", _Session)
    monkeypatch.setattr(funding, "_tid", lambda: 1)
    monkeypatch.setattr(funding, "_load", lambda db, app_id: (application, None))
    monkeypatch.setattr(funding, "_scope_or_403", lambda *args: None)
    monkeypatch.setattr(funding, "_pending_appeal_ids", lambda *args: set())
    monkeypatch.setattr(funding, "_app_row", lambda *args, **kwargs: {"applicationId": "7"})
    monkeypatch.setattr(funding, "_check_fund_review_node", lambda *args: None)

    limited = funding.get_application(7, {"currentRoleCode": "COUNSELOR"})
    privileged = funding.get_application(7, {"currentRoleCode": "FUNDING_TEACHER"})
    assert "6789.12" not in json.dumps(limited, ensure_ascii=False)
    assert limited["checkSnapshot"]["statusOk"] is True
    assert limited["statement"] == application.statement
    assert "amountAuthority" not in limited["checkSnapshot"]
    assert privileged["checkSnapshot"] == snapshot
    assert json.loads(application.check_snapshot_json) == snapshot
    from app.core.exceptions import AppException
    application.check_snapshot_json = "[]"
    with pytest.raises(AppException):
        funding.get_application(7, {"currentRoleCode": "COUNSELOR"})


def test_amount_adjustment_history_cannot_bypass_masked_application(monkeypatch):
    from app.core import permissions
    monkeypatch.setattr(permissions, "_db_granted", lambda user, **kwargs:
                        {"studentAffairs.funding.sensitiveView"} if user.get("currentRoleCode") == "FUNDING_TEACHER" else None)
    record = dict(id=8, requested_amount=Decimal("6789.12"), reason="调整至6789.12元",
                  requester_id=701, requester_name="申请人", status="APPROVED",
                  reviewer_id=702, reviewer_name="复核人", review_reason="同意6789.12元",
                  reviewed_at=None, created_at=None, version=1)
    monkeypatch.setattr(authority, "session", lambda: _Session([record]))
    monkeypatch.setattr(authority, "_tid", lambda: 1)
    monkeypatch.setattr(funding, "_load", lambda *args: (SimpleNamespace(student_id=11), None))
    monkeypatch.setattr(funding, "_scope_or_403", lambda *args: None)
    limited = authority.list_adjustments(7, {"currentRoleCode": "COUNSELOR"})[0]
    privileged = authority.list_adjustments(7, {"currentRoleCode": "FUNDING_TEACHER"})[0]
    assert "6789.12" not in json.dumps(limited, ensure_ascii=False)
    assert limited["requestedAmount"] == "5000以上"
    assert limited["status"] == "APPROVED" and limited["version"] == 1
    assert privileged["requestedAmount"] == "6789.12"
    assert privileged["reason"] == record["reason"]


@pytest.mark.parametrize("action", ["CREATE", "FOLLOW", "ESCALATE", "ESCALATE_AGAIN", "CLOSE"])
def test_mental_write_responses_never_reveal_existing_private_note(client, db_mode, action):
    from test_affairs_mental import BASE, _hdr, _refer, _seed
    ids = _seed(db_mode)
    headers = _hdr(client, "school_admin01")
    response = _refer(client, headers, ids["sa"])
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    rid = result["referralId"]
    if action == "FOLLOW":
        response = client.post(f"{BASE}/mental/referrals/{rid}/follow", headers=headers,
                               json={"content": "已核实学生当前情况", "version": result["version"]})
    elif action in {"ESCALATE", "ESCALATE_AGAIN"}:
        response = client.post(f"{BASE}/mental/referrals/{rid}/escalate", headers=headers,
                               json={"content": "需要危机协同处置", "version": result["version"]})
        if action == "ESCALATE_AGAIN":
            first = response.json()["data"]
            response = client.post(f"{BASE}/mental/referrals/{rid}/escalate", headers=headers,
                                   json={"content": "再次核对危机协同情况", "version": first["version"]})
            assert response.json()["data"]["riskId"] == first["riskId"]
    elif action == "CLOSE":
        response = client.post(f"{BASE}/mental/referrals/{rid}/close", headers=headers,
                               json={"conclusion": "已经完成本次跟进工作", "version": result["version"]})
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["noteMasked"] is True
    assert "涉密明细内容XYZ" not in json.dumps(result, ensure_ascii=False)
    assert "allowedActions" in result and "version" in result
    revealed = client.get(f"{BASE}/mental/referrals/{rid}", headers=headers,
                          params={"reason": "核实授权学生服务记录"})
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["data"]["note"] == "涉密明细内容XYZ"


def test_psychology_scope_uses_stable_identity_not_shared_real_name(db_mode, monkeypatch):
    from test_affairs_mental import TID, _seed
    from app.db.session import get_sessionmaker
    from app.services import affairs_mental_service as mental
    ids = _seed(db_mode)
    monkeypatch.setattr(mental, "_tid", lambda: TID)
    with get_sessionmaker()() as db:
        stranger = {"userId": "db-212", "loginName": "different-teacher",
                    "realName": "心理·孙", "currentRoleCode": "PSYCHOLOGY_TEACHER"}
        owner = {"userId": "db-211", "loginName": "psych01",
                 "realName": "修改后的显示姓名", "currentRoleCode": "PSYCHOLOGY_TEACHER"}
        assert mental.psy_scope_ids(db, stranger) == set()
        assert mental.psy_scope_ids(db, owner) == {ids["sa"]}
