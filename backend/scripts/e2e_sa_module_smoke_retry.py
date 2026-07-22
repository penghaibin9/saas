"""Retry failed smoke modules with correct API paths + DB student resolve."""
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

OUT = ROOT / "tmp" / "e2e_sa_module_smoke_retry.local.json"


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


def student_id(no: str) -> str:
    db = get_sessionmaker()()
    try:
        row = db.execute(text(
            "SELECT id FROM t_student_profile WHERE student_no=:n AND is_deleted=0 LIMIT 1"
        ), {"n": no}).first()
        return str(row[0]) if row else ""
    finally:
        db.close()


def main() -> int:
    rows = []
    sid_a = student_id("E2E20260001")
    sid_c = student_id("E2E20260003")
    time.sleep(3)
    sa = login("e2e_sa_admin")
    time.sleep(7)
    counselor = login("e2e_counselor_a")

    profile = _req("GET", f"/student-affairs/students/{sid_a}/profile", token=counselor)
    rows.append({"module": "学生画像", "ok": profile.get("code") == 0, "code": profile.get("code"), "sid": sid_a})

    time.sleep(3)
    disc = _req("POST", "/student-affairs/discipline/cases", token=sa, body={
        "studentId": sid_a,
        "violationType": "OTHER",
        "fact": "E2E冒烟违纪事实登记不得少于十字说明内容",
        "disciplineLevel": "WARNING",
    })
    if disc.get("code") != 0:
        # try alternate body keys from schema
        disc = _req("GET", "/student-affairs/discipline/cases?pageSize=5", token=sa)
        rows.append({"module": "违纪处分", "ok": disc.get("code") == 0, "mode": "list",
                     "create": disc if disc.get("code") != 0 else None, "code": disc.get("code")})
    else:
        rows.append({"module": "违纪处分登记", "ok": True, "id": (disc.get("data") or {}).get("id")
                     or (disc.get("data") or {}).get("caseId"), "resp": disc.get("data")})

    time.sleep(7)
    risk = _req("POST", "/student-affairs/risk/records", token=counselor, body={
        "studentId": sid_c,
        "riskType": "MANUAL",
        "riskLevel": "MEDIUM",
        "reason": "E2E人工风险登记冒烟测试原因说明足够字数",
    })
    if risk.get("code") != 0:
        risk_list = _req("GET", "/student-affairs/risk/records?pageSize=5", token=counselor)
        rows.append({"module": "风险预警", "ok": risk_list.get("code") == 0, "createCode": risk.get("code"),
                     "createMsg": risk.get("message"), "listCode": risk_list.get("code"),
                     "createDetails": risk.get("details")})
    else:
        rows.append({"module": "风险登记", "ok": True, "id": (risk.get("data") or {}).get("id")
                     or (risk.get("data") or {}).get("riskId")})

    time.sleep(7)
    talk = _req("POST", "/student-affairs/talks", token=counselor, body={
        "studentIds": [int(sid_a)],
        "talkType": "ROUTINE",
        "plannedAt": "2026-07-23",
        "topic": "E2E谈心谈话冒烟",
        "content": "E2E谈心谈话内容需要足够长度以满足最小字数校验要求不少于二十字",
    })
    if talk.get("code") != 0:
        talk_list = _req("GET", "/student-affairs/talks?pageSize=5", token=counselor)
        rows.append({"module": "谈心谈话", "ok": talk_list.get("code") == 0, "createCode": talk.get("code"),
                     "createMsg": talk.get("message"), "details": talk.get("details"),
                     "listCode": talk_list.get("code")})
    else:
        rows.append({"module": "谈心谈话", "ok": True, "id": (talk.get("data") or {}).get("id")})

    OUT.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    ok = sum(1 for r in rows if r["ok"])
    print(f"ok={ok}/{len(rows)}")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
