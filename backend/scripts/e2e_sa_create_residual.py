"""Create residual SA records with correct schemas."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from scripts.e2e_bootstrap_student_affairs_accounts import STABLE_PWD, TENANT, _req  # noqa: E402

OUT = ROOT / "tmp" / "e2e_sa_create_residual.local.json"


def login(ln: str) -> str:
    pwd = "123456" if ln == "admin2" else STABLE_PWD
    for _ in range(8):
        r = _req("POST", "/auth/login", body={"loginName": ln, "password": pwd, "tenantCode": TENANT})
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            time.sleep(12)
            continue
        assert r.get("code") == 0, r
        return r["data"]["accessToken"]
    raise RuntimeError(ln)


def sid(no: str) -> str:
    db = get_sessionmaker()()
    try:
        row = db.execute(text(
            "SELECT id FROM t_student_profile WHERE student_no=:n AND is_deleted=0 LIMIT 1"
        ), {"n": no}).first()
        return str(row[0]) if row else ""
    finally:
        db.close()


def main() -> int:
    out = {}
    a = sid("E2E20260001")
    c = sid("E2E20260003")
    time.sleep(3)
    sa = login("e2e_sa_admin")
    time.sleep(7)
    counselor = login("e2e_counselor_a")

    disc = _req("POST", "/student-affairs/discipline/cases", token=sa, body={
        "studentId": a,
        "discType": "WARNING",
        "reason": "E2E违纪事实：课堂严重违纪行为登记冒烟",
    })
    out["discipline"] = disc

    time.sleep(5)
    risk = _req("POST", "/student-affairs/risk/records", token=counselor, body={
        "studentId": c,
        "source": "MANUAL",
        "riskLevel": "MEDIUM",
        "title": "E2E人工风险",
        "detail": "E2E人工风险登记冒烟测试原因说明足够字数",
    })
    out["risk"] = risk

    time.sleep(5)
    talk = _req("POST", "/student-affairs/talks", token=counselor, body={
        "studentIds": [a],
        "talkType": "DAILY",
        "topic": "E2E日常谈心冒烟",
        "scheduledAt": "2026-07-23T10:00:00",
    })
    out["talk"] = talk
    if talk.get("code") == 0:
        talk_id = (talk.get("data") or {}).get("id") or (talk.get("data") or {}).get("talkId")
        if talk_id:
            time.sleep(2)
            rec = _req("POST", f"/student-affairs/talks/{talk_id}/record", token=counselor, body={
                "content": "E2E谈话记录内容需要足够长度以满足最小二十字校验要求",
                "result": "CONTINUE",
                "needFollowUp": False,
            })
            out["talkRecord"] = rec

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: {"code": v.get("code"), "biz": v.get("bizCode"), "msg": v.get("message"),
                           "id": (v.get("data") or {}).get("id") or (v.get("data") or {}).get("caseId")
                                 or (v.get("data") or {}).get("riskId") or (v.get("data") or {}).get("talkId"),
                           "details": v.get("details")}
                      for k, v in out.items()}, ensure_ascii=False, indent=2))
    required = [out["discipline"], out["risk"], out["talk"]]
    ok = all(x.get("code") == 0 for x in required)
    print("ok", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
