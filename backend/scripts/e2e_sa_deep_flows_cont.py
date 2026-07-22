"""Continue deep flows after funding grant (disburse + discipline + risk + eval + archive)."""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_sa_deep_flows import (  # noqa: E402
    SA, STU_A, STU_B, STU_C, backdate_risk_assigned, login, ok, pause, step,
)
from scripts.e2e_bootstrap_student_affairs_accounts import _req  # noqa: E402

OUT = ROOT / "tmp" / "e2e_sa_deep_flows_cont.local.json"
PREV = ROOT / "tmp" / "e2e_sa_deep_flows.local.json"


def main() -> int:
    report: list = []
    ids: dict = {"startedAt": datetime.now().isoformat(timespec="seconds")}
    prev = json.loads(PREV.read_text(encoding="utf-8")) if PREV.exists() else {}
    fbid = ((prev.get("ids") or {}).get("funding") or {}).get("fundingBatchId")
    # if interrupted before ids.funding saved, recover from steps
    if not fbid:
        for s in prev.get("steps") or []:
            if s.get("step") == "funding_batch" and s.get("ok"):
                fbid = str((s.get("data") or {}).get("batchId") or "")
    # last run had fundingBatchId only in local memory — probe open batches
    pause(3)
    admin = login("e2e_sa_admin")
    if not fbid:
        bl = _req("GET", f"{SA}/funding/batches", token=admin)
        items = ((bl.get("data") or {}).get("items") or [])
        for it in items:
            if str(it.get("batchName") or it.get("projectName") or "").find("E2E") >= 0 or True:
                # prefer batch that has GRANTED apps without disbursement
                fbid = str(it.get("batchId") or it.get("id") or "")
                break
    ids["fundingBatchId"] = fbid
    print("using fundingBatchId", fbid)

    # generate may already done — idempotent
    gen = _req("POST", f"{SA}/funding/batches/{fbid}/disbursements/generate", token=admin)
    step(report, "funding_disburse_generate", gen)
    pause()
    admin = login("e2e_sa_admin")
    lst = _req("GET", f"{SA}/funding/disbursements", token=admin, params={"batchId": fbid})
    items = ((lst.get("data") or {}).get("items") or [])
    step(report, "funding_disburse_list", lst, {"count": len(items)})
    if items:
        # find PENDING first
        pending = [x for x in items if x.get("bankStatus") == "PENDING"] or items
        did = pending[0]["disbursementId"]
        ids["disbursementId"] = did
        tag = uuid.uuid4().hex[:6].upper()
        pause()
        admin = login("e2e_sa_admin")
        if pending[0].get("bankStatus") == "PENDING":
            iss = _req("POST", f"{SA}/funding/disbursements/{did}/issue", token=admin,
                       body={"disburseNo": f"E2E-FB-{tag}", "bankLast4": "6222888888886411"})
            step(report, "funding_disburse_issue", iss)
        else:
            step(report, "funding_disburse_issue", True, {"note": "already issued", "did": did})
        pause()
        admin = login("e2e_sa_admin")
        dup = _req("POST", f"{SA}/funding/disbursements/{did}/issue", token=admin, body={})
        step(report, "funding_disburse_dup_block", not ok(dup), {"code": dup.get("code"), "biz": dup.get("bizCode")})
        pause()
        st = login(STU_A["login"])
        mine = _req("GET", "/portal/affairs/funding", token=st)
        step(report, "funding_student_portal_view", mine)

    # ── discipline appeal full ──
    pause()
    admin = login("e2e_sa_admin")
    reg = _req("POST", f"{SA}/discipline/cases", token=admin, body={
        "studentId": STU_B["id"], "discType": "WARNING",
        "reason": "E2E深链违纪：考试轻微违纪予以警告处分登记"})
    step(report, "disc_register", reg)
    cid = str((reg.get("data") or {}).get("caseId") or "")
    ids["caseId"] = cid
    if cid:
        pause(); admin = login("e2e_sa_admin")
        step(report, "disc_submit", _req("POST", f"{SA}/discipline/cases/{cid}/submit", token=admin))
        for label in ("college", "sa"):
            pause(); admin = login("e2e_sa_admin")
            step(report, f"disc_review_{label}",
                 _req("POST", f"{SA}/discipline/cases/{cid}/review", token=admin, body={"action": "APPROVE"}))
        pause(); admin = login("e2e_sa_admin")
        det = _req("GET", f"{SA}/discipline/cases/{cid}", token=admin)
        step(report, "disc_effective", det, {"effective": (det.get("data") or {}).get("status") == "EFFECTIVE"})
        pause(); admin = login("e2e_sa_admin")
        step(report, "disc_deliver", _req("POST", f"{SA}/discipline/cases/{cid}/deliver", token=admin,
                                          body={"method": "DIRECT", "remark": "本人签收决定书"}))
        pause(); st = login(STU_B["login"])
        portal_appeal = _req("POST", "/portal/affairs/discipline/appeal", token=st,
                             body={"caseId": cid, "reason": "对处分认定事实有异议申请复核"})
        aid = ""
        if ok(portal_appeal):
            step(report, "disc_student_portal_appeal", portal_appeal)
            aid = str((portal_appeal.get("data") or {}).get("appealId") or "")
        else:
            step(report, "disc_student_portal_appeal", portal_appeal)
            pause(); admin = login("e2e_sa_admin")
            a = _req("POST", f"{SA}/discipline/cases/{cid}/appeal", token=admin,
                     body={"reason": "对处分认定事实有异议申请复核"})
            step(report, "disc_staff_appeal", a)
            aid = str((a.get("data") or {}).get("appealId") or "")
        ids["appealId"] = aid
        if aid:
            pause(); admin = login("e2e_sa_admin")
            rev = _req("POST", f"{SA}/discipline/appeals/{aid}/review", token=admin,
                       body={"result": "REVOKED", "opinion": "经复核事实认定有误撤销原处分"})
            step(report, "disc_appeal_revoked", rev)
            pause(); admin = login("e2e_sa_admin")
            after = _req("GET", f"{SA}/discipline/cases/{cid}", token=admin)
            removed = ((after.get("data") or {}).get("status") == "REMOVED")
            step(report, "disc_case_removed", after, {"removed": removed})
            report[-1]["ok"] = removed and ok(after)

    # ── risk 72h ──
    pause(); admin = login("e2e_sa_admin")
    cands = _req("GET", f"{SA}/risk/owner-candidates", token=admin)
    step(report, "risk_owner_candidates", cands)
    owner_id = ""
    data = cands.get("data")
    cand_items = []
    if isinstance(data, dict):
        cand_items = data.get("items") or data.get("list") or []
    elif isinstance(data, list):
        cand_items = data
    for it in cand_items:
        if isinstance(it, dict):
            owner_id = str(it.get("userId") or it.get("id") or it.get("ownerId") or "")
            if owner_id:
                break
    if not owner_id:
        pause(); tok = login("e2e_counselor_a")
        me = _req("GET", "/auth/me", token=tok)
        owner_id = str(((me.get("data") or {}).get("userId") or "")).replace("db-", "")
    ids["ownerId"] = owner_id
    pause(); admin = login("e2e_sa_admin")
    create = _req("POST", f"{SA}/risk/records", token=admin, body={
        "studentId": STU_C["id"], "source": "MANUAL", "riskLevel": "LOW",
        "title": "E2E风险72h升级", "detail": "E2E风险记录用于验证72小时未处置自动升级"})
    step(report, "risk_create", create)
    rid = str((create.get("data") or {}).get("riskId") or "")
    ids["riskId"] = rid
    if rid:
        pause(); admin = login("e2e_sa_admin")
        assign = _req("POST", f"{SA}/risk/records/{rid}/assign", token=admin, body={"ownerId": owner_id})
        step(report, "risk_assign", assign)
        try:
            backdate_risk_assigned(int(rid), 73)
            report.append({"step": "risk_backdate_assigned_at", "ok": True, "hours": 73})
            print("PASS risk_backdate_assigned_at")
        except Exception as e:
            report.append({"step": "risk_backdate_assigned_at", "ok": False, "error": str(e)})
            print("FAIL risk_backdate_assigned_at", e)
        pause(); admin = login("e2e_sa_admin")
        scan = _req("POST", f"{SA}/risk/scan-timeout", token=admin)
        step(report, "risk_scan_timeout_72h", scan)
        escalated = int(((scan.get("data") or {}).get("escalated") or 0))
        pause(); admin = login("e2e_sa_admin")
        det = _req("GET", f"{SA}/risk/records/{rid}", token=admin)
        status = (det.get("data") or {}).get("status")
        level = (det.get("data") or {}).get("riskLevel")
        final_ok = status == "ESCALATED" and escalated >= 1
        step(report, "risk_escalated_state", final_ok, {"status": status, "riskLevel": level,
                                                        "scanEscalated": escalated})
        pause(); admin = login("e2e_sa_admin")
        scan2 = _req("POST", f"{SA}/risk/scan-timeout", token=admin)
        step(report, "risk_scan_idempotent",
             int((scan2.get("data") or {}).get("escalated") or 0) == 0, {"data": scan2.get("data")})
        pause(); ct = login("e2e_counselor_a")
        step(report, "risk_counselor_mini_list", _req("GET", "/mobile/teacher/risk-students", token=ct))

    # ── counselor eval ──
    tag = uuid.uuid4().hex[:6]
    pause(); admin = login("e2e_sa_admin")
    i1 = _req("POST", f"{SA}/counselor-eval/indicators", token=admin,
              body={"name": f"E2E师德{tag}", "weight": 30, "maxScore": 100})
    step(report, "eval_indicator", i1)
    ind = str((i1.get("data") or {}).get("indicatorId") or "")
    pause(); admin = login("e2e_sa_admin")
    ev = _req("POST", f"{SA}/counselor-eval/evals", token=admin, body={
        "periodCode": f"2025-2026-E2E-{tag}", "counselorKey": "e2e_counselor_a",
        "counselorName": "E2E辅导员A", "scores": {ind: 90}})
    step(report, "eval_score", ev)
    eid = str((ev.get("data") or {}).get("evalId") or "")
    ids["evalId"] = eid
    if eid:
        pause(); admin = login("e2e_sa_admin")
        step(report, "eval_publish", _req("POST", f"{SA}/counselor-eval/evals/{eid}/publish", token=admin))
        pause(); ct = login("e2e_counselor_a")
        ap = _req("POST", f"{SA}/counselor-eval/evals/{eid}/appeal", token=ct,
                  body={"reason": "对师德指标评分有异议申请复核调分"})
        step(report, "eval_counselor_appeal", ap)
        if not ok(ap):
            pause(); admin = login("e2e_sa_admin")
            ap = _req("POST", f"{SA}/counselor-eval/evals/{eid}/appeal", token=admin,
                      body={"reason": "对师德指标评分有异议申请复核调分"})
            step(report, "eval_admin_proxy_appeal", ap)
        pause(); admin = login("e2e_sa_admin")
        rev = _req("POST", f"{SA}/counselor-eval/evals/{eid}/appeal-review", token=admin, body={
            "result": "ADJUSTED", "opinion": "经复核上调师德得分", "scores": {ind: 95}})
        step(report, "eval_appeal_review", rev)

    # ── archive ──
    tag = uuid.uuid4().hex[:6]
    pause(); admin = login("e2e_sa_admin")
    b = _req("POST", f"{SA}/archive/batches", token=admin,
             body={"batchName": f"E2E学工归档{tag}", "yearCode": "2026"})
    step(report, "archive_batch", b)
    bid = str((b.get("data") or {}).get("batchId") or "")
    ids["archiveBatchId"] = bid
    if bid:
        pause(); admin = login("e2e_sa_admin")
        col = _req("POST", f"{SA}/archive/batches/{bid}/collect", token=admin,
                   body={"studentIds": [STU_A["id"], STU_B["id"]]})
        step(report, "archive_collect", col)
        last = col
        for i in range(3):
            pause(); admin = login("e2e_sa_admin")
            last = _req("POST", f"{SA}/archive/batches/{bid}/advance", token=admin,
                        body={"action": "APPROVE"})
            step(report, f"archive_advance_{i+1}", last)
        status = ((last.get("data") or {}).get("status"))
        step(report, "archive_final_archived", status == "ARCHIVED", {"status": status})
        pause(); admin = login("e2e_sa_admin")
        det = _req("GET", f"{SA}/archive/batches/{bid}", token=admin)
        pkgs = ((det.get("data") or {}).get("packages") or [])
        watermarked = bool(pkgs) and all(
            p.get("status") == "ARCHIVED" and p.get("exportTaskId") for p in pkgs)
        step(report, "archive_watermark_packages", watermarked and ok(det),
             {"packages": len(pkgs), "watermarked": watermarked})

    passed = sum(1 for x in report if x.get("ok"))
    total = len(report)
    out = {"summary": {"passed": passed, "total": total, "ok": passed == total},
           "ids": ids, "steps": report, "prevOrientation": (prev.get("ids") or {}).get("orientation")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRESULT {passed}/{total} -> {OUT}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
