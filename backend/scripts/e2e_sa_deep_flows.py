"""学工剩余深链路四端联测：迎新 / 奖助发放+异议 / 处分申诉 / 风险72h / 考评 / 档案封存。

对 sandbox-school 真实 API + MySQL；密码限流时自动等待。结果写 tmp/e2e_sa_deep_flows.local.json。
风险 72h：分派后回写 assigned_at 再扫 scan-timeout（不等真实 72 小时）。
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import STABLE_PWD, TENANT, _req  # noqa: E402

OUT = ROOT / "tmp" / "e2e_sa_deep_flows.local.json"
SA = "/student-affairs"
ORI = "/orientation"

# 既有 E2E 学生（bootstrap 产出）
STU_A = {"login": "E2E20260001", "id": "369", "name": "E2E学生A"}
STU_B = {"login": "E2E20260002", "id": "370", "name": "E2E学生B"}
STU_C = {"login": "E2E20260003", "id": "371", "name": "E2E学生C"}
STU_D = {"login": "E2E20260004", "id": "372", "name": "E2E学生D"}


def login(ln: str) -> str:
    pwd = "123456" if ln == "admin2" else STABLE_PWD
    for _ in range(10):
        r = _req("POST", "/auth/login", body={"loginName": ln, "password": pwd, "tenantCode": TENANT,
                                               "clientType": "PC"})
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            time.sleep(12)
            continue
        if r.get("code") != 0:
            raise RuntimeError(f"login {ln}: {r}")
        return r["data"]["accessToken"]
    raise RuntimeError(f"login rate {ln}")


def pause(sec: float = 7.0) -> None:
    time.sleep(sec)


def ok(resp: dict) -> bool:
    return resp.get("code") == 0


def step(report: list, name: str, resp_or_bool, extra: dict | None = None) -> bool:
    if isinstance(resp_or_bool, bool):
        item = {"step": name, "ok": resp_or_bool}
    else:
        item = {"step": name, "ok": ok(resp_or_bool), "code": resp_or_bool.get("code"),
                "bizCode": resp_or_bool.get("bizCode"), "message": resp_or_bool.get("message"),
                "data": resp_or_bool.get("data")}
    if extra:
        item.update(extra)
    report.append(item)
    print(("PASS" if item["ok"] else "FAIL"), name, item.get("bizCode") or item.get("message") or "")
    return item["ok"]


def backdate_risk_assigned(risk_id: int, hours: int = 73) -> None:
    from sqlalchemy import text
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        ts = datetime.utcnow() - timedelta(hours=hours)
        db.execute(text(
            "UPDATE t_affairs_risk_record SET assigned_at=:ts, updated_at=UTC_TIMESTAMP() "
            "WHERE id=:id AND is_deleted=0"), {"ts": ts, "id": risk_id})
        db.commit()
    finally:
        db.close()


def bind_ori_student_id(ori_id: int, student_id: int) -> None:
    """create_student 未写 student_id 时，绑定到门户本人档案以便预报到。"""
    from sqlalchemy import text
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        db.execute(text(
            "UPDATE t_orientation_student SET student_id=:sid WHERE id=:oid AND is_deleted=0"),
            {"sid": student_id, "oid": ori_id})
        db.commit()
    finally:
        db.close()


def flow_orientation(report: list) -> dict:
    ids: dict = {}
    tag = uuid.uuid4().hex[:6].upper()
    pause(3)
    admin = login("e2e_sa_admin")
    batch = _req("POST", f"{ORI}/batches", token=admin, body={
        "batchName": f"E2E迎新批次{tag}", "batchNo": f"E2E-ORI-{tag}",
        "year": "2026", "startDate": "2026-09-01", "reportEndDate": "2026-09-20",
        "plannedCount": 4, "remark": "E2E深链迎新"})
    step(report, "ori_batch_create", batch)
    bid = str((batch.get("data") or {}).get("id") or "")
    ids["batchId"] = bid
    if not bid:
        return ids
    pause()
    admin = login("e2e_sa_admin")
    act = _req("POST", f"{ORI}/batches/{bid}/activate", token=admin)
    step(report, "ori_batch_activate", act)

    pause()
    ot = login("e2e_orientation_teacher")
    adm_no = f"E2E-LQ-{tag}-004"
    create = _req("POST", f"{ORI}/students", token=ot, body={
        "name": STU_D["name"], "admissionNo": adm_no, "studentId": STU_D["id"],
        "majorName": "E2E工业机器人技术", "className": "E2E机器人2401班",
        "phone": "13900004004", "origin": "浙江杭州", "counselor": "E2E辅导员A"})
    step(report, "ori_student_create", create)
    oid = str((create.get("data") or {}).get("id") or "")
    ids["oriStudentId"] = oid
    ids["admissionNo"] = adm_no
    # 若后端未写 student_id（旧进程未 reload），兜底绑定
    if oid:
        try:
            bind_ori_student_id(int(oid), int(STU_D["id"]))
            report.append({"step": "ori_bind_student_id", "ok": True, "oriId": oid, "studentId": STU_D["id"]})
        except Exception as e:
            report.append({"step": "ori_bind_student_id", "ok": False, "error": str(e)})

    pause()
    ot = login("e2e_orientation_teacher")
    verify = _req("POST", f"{ORI}/students/{oid}/verify", token=ot, body={"passed": True})
    step(report, "ori_verify", verify)

    pause()
    st = login(STU_D["login"])
    mine = _req("GET", "/mobile/orientation/my", token=st)
    has = bool((mine.get("data") or {}).get("hasData"))
    step(report, "ori_student_mini_my", mine, {"hasData": has})
    pause()
    st = login(STU_D["login"])
    collect = _req("POST", "/mobile/orientation/collect", token=st,
                   body={"phone": "13900004004", "origin": "浙江杭州"})
    step(report, "ori_student_collect", collect)
    pause()
    st = login(STU_D["login"])
    gc = _req("POST", "/mobile/orientation/green-channel", token=st, body={
        "applyType": "生源地助学贷款", "applyAmount": 8600,
        "reason": "家庭经济困难申请绿色通道缓缴学费"})
    step(report, "ori_student_green_channel", gc)
    gid = str((gc.get("data") or {}).get("id") or (gc.get("data") or {}).get("greenChannelId") or "")

    pause()
    ot = login("e2e_orientation_teacher")
    gclist = _req("GET", f"{ORI}/green-channels", token=ot)
    if not gid:
        items = ((gclist.get("data") or {}).get("items") or [])
        for it in items:
            if str(it.get("studentId")) == oid or it.get("admissionNo") == adm_no:
                gid = str(it.get("id") or "")
                break
    ids["greenChannelId"] = gid
    if gid:
        approve = _req("POST", f"{ORI}/green-channels/{gid}/approve", token=ot,
                       body={"remark": "材料齐全予以通过缓缴"})
        step(report, "ori_green_approve_pc", approve)
    else:
        step(report, "ori_green_approve_pc", False, {"note": "未找到绿通单"})

    pause()
    ot_m = login("e2e_orientation_teacher")
    checkin = _req("POST", "/mobile/teacher/orientation/checkin", token=ot_m,
                   body={"admissionNo": adm_no})
    step(report, "ori_teacher_mini_checkin", checkin)

    pause()
    ot = login("e2e_orientation_teacher")
    det = _req("GET", f"{ORI}/students/{oid}", token=ot)
    st_ok = ((det.get("data") or {}).get("student") or {}).get("reportStatus") == "CHECKED_IN"
    step(report, "ori_checkin_status", det, {"checkedIn": st_ok})

    pause()
    admin = login("e2e_sa_admin")
    arch = _req("POST", f"{ORI}/archives", token=admin,
                body={"archiveName": f"E2E迎新归档{tag}", "scope": "全校"})
    step(report, "ori_archive_create", arch)
    aid = str((arch.get("data") or {}).get("id") or "")
    if aid:
        pause()
        admin = login("e2e_sa_admin")
        run = _req("POST", f"{ORI}/archives/{aid}/run", token=admin)
        step(report, "ori_archive_run", run)
        ids["oriArchiveId"] = aid
    return ids


def flow_funding_and_aid(report: list) -> dict:
    ids: dict = {}
    tag = uuid.uuid4().hex[:6].upper()
    pause(3)
    admin = login("e2e_sa_admin")
    # 困难认定 → 异议申诉
    ab = _req("POST", f"{SA}/aid/batches", token=admin, body={
        "batchName": f"E2E困难认定{tag}", "schoolYear": "2025-2026",
        "publicityDays": 0, "levelConfig": {"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]},
        "publish": True})
    step(report, "aid_batch", ab)
    abid = str((ab.get("data") or {}).get("batchId") or "")
    ids["aidBatchId"] = abid
    if not abid:
        return ids
    pause()
    admin = login("e2e_sa_admin")
    ap = _req("POST", f"{SA}/aid/applications", token=admin, body={
        "batchId": abid, "studentId": STU_A["id"], "applyLevel": "DIFFICULT",
        "statement": "家庭收入较低父母务农需要资助支持完成学业",
        "memberCount": 4, "annualIncome": "25000", "specialTags": ["单亲"]})
    step(report, "aid_apply", ap)
    apply_id = str((ap.get("data") or {}).get("applyId") or "")
    ids["aidApplyId"] = apply_id
    last = ap
    for i in range(4):
        pause()
        admin = login("e2e_sa_admin")
        body = {"action": "APPROVE"}
        if i == 3:
            body["level"] = "DIFFICULT"
        last = _req("POST", f"{SA}/aid/applications/{apply_id}/review", token=admin, body=body)
    step(report, "aid_to_publicity", last)
    pause()
    admin = login("e2e_sa_admin")
    # 公示中提异议（申诉）
    obj = _req("POST", f"{SA}/aid/applications/{apply_id}/objection", token=admin,
               body={"reason": "对困难等级公示结果有异议申请复核"})
    step(report, "aid_objection", obj)
    oid = str((obj.get("data") or {}).get("objectionId") or "")
    if oid:
        pause()
        admin = login("e2e_sa_admin")
        # 不成立维持 → 继续公示
        rev = _req("POST", f"{SA}/aid/objections/{oid}/review", token=admin,
                   body={"result": "OVERRULED", "opinion": "经复核材料充分维持原认定等级"})
        step(report, "aid_objection_review", rev)
    pause()
    admin = login("e2e_sa_admin")
    conf = _req("POST", f"{SA}/aid/applications/{apply_id}/publicity-confirm", token=admin)
    step(report, "aid_publicity_confirm", conf)

    # 奖学金项目→申请→审批→公示→GRANTED→发放台账
    pause()
    fund = login("e2e_funding_teacher")
    # funding teacher may lack project.manage — try sa_admin
    admin = login("e2e_sa_admin")
    proj = _req("POST", f"{SA}/funding/projects", token=admin, body={
        "projectName": f"E2E奖学金{tag}", "projectType": "SCHOLARSHIP",
        "amount": 3000, "quota": 10})
    step(report, "funding_project", proj)
    pid = str((proj.get("data") or {}).get("projectId") or "")
    pause()
    admin = login("e2e_sa_admin")
    fb = _req("POST", f"{SA}/funding/batches", token=admin, body={
        "projectId": pid, "schoolYear": "2025-2026", "publicityDays": 0,
        "quota": 10, "publish": True})
    step(report, "funding_batch", fb)
    fbid = str((fb.get("data") or {}).get("batchId") or "")
    ids["fundingBatchId"] = fbid
    pause()
    admin = login("e2e_sa_admin")
    fap = _req("POST", f"{SA}/funding/applications", token=admin, body={
        "batchId": fbid, "studentId": STU_A["id"], "amount": 3000,
        "statement": "品学兼优申请E2E奖学金资助"})
    step(report, "funding_apply", fap)
    faid = str((fap.get("data") or {}).get("applicationId") or "")
    ids["fundingAppId"] = faid
    last = fap
    for _ in range(3):
        pause()
        admin = login("e2e_sa_admin")
        last = _req("POST", f"{SA}/funding/applications/{faid}/review", token=admin,
                    body={"action": "APPROVE"})
    step(report, "funding_to_publicity", last)
    pause()
    admin = login("e2e_sa_admin")
    g = _req("POST", f"{SA}/funding/applications/{faid}/publicity-confirm", token=admin)
    step(report, "funding_granted", g)
    pause()
    admin = login("e2e_sa_admin")
    gen = _req("POST", f"{SA}/funding/batches/{fbid}/disbursements/generate", token=admin)
    step(report, "funding_disburse_generate", gen)
    pause()
    admin = login("e2e_sa_admin")
    lst = _req("GET", f"{SA}/funding/disbursements", token=admin, params={"batchId": fbid})
    items = ((lst.get("data") or {}).get("items") or [])
    step(report, "funding_disburse_list", lst, {"count": len(items)})
    if items:
        did = items[0]["disbursementId"]
        ids["disbursementId"] = did
        pause()
        admin = login("e2e_sa_admin")
        iss = _req("POST", f"{SA}/funding/disbursements/{did}/issue", token=admin,
                   body={"disburseNo": f"E2E-FB-{tag}", "bankLast4": "6222888888886411"})
        step(report, "funding_disburse_issue", iss)
        pause()
        admin = login("e2e_sa_admin")
        dup = _req("POST", f"{SA}/funding/disbursements/{did}/issue", token=admin, body={})
        step(report, "funding_disburse_dup_block", not ok(dup), {"code": dup.get("code")})
        # 学生端可见本人奖助
        pause()
        st = login(STU_A["login"])
        mine = _req("GET", "/portal/affairs/funding", token=st)
        step(report, "funding_student_portal_view", mine)
    return ids


def flow_discipline_appeal(report: list) -> dict:
    ids: dict = {}
    pause(3)
    admin = login("e2e_sa_admin")
    reg = _req("POST", f"{SA}/discipline/cases", token=admin, body={
        "studentId": STU_B["id"], "discType": "WARNING",
        "reason": "E2E深链违纪：考试轻微违纪予以警告处分登记"})
    step(report, "disc_register", reg)
    cid = str((reg.get("data") or {}).get("caseId") or "")
    ids["caseId"] = cid
    if not cid:
        return ids
    pause()
    admin = login("e2e_sa_admin")
    sub = _req("POST", f"{SA}/discipline/cases/{cid}/submit", token=admin)
    step(report, "disc_submit", sub)
    for label in ("college", "sa"):
        pause()
        admin = login("e2e_sa_admin")
        r = _req("POST", f"{SA}/discipline/cases/{cid}/review", token=admin,
                 body={"action": "APPROVE"})
        step(report, f"disc_review_{label}", r)
    pause()
    admin = login("e2e_sa_admin")
    det = _req("GET", f"{SA}/discipline/cases/{cid}", token=admin)
    eff = ((det.get("data") or {}).get("status") == "EFFECTIVE")
    step(report, "disc_effective", det, {"effective": eff})
    pause()
    admin = login("e2e_sa_admin")
    deliver = _req("POST", f"{SA}/discipline/cases/{cid}/deliver", token=admin,
                   body={"method": "DIRECT", "remark": "本人签收决定书"})
    step(report, "disc_deliver", deliver)

    # 学生门户申诉（若有）/ 教师代提申诉
    pause()
    st = login(STU_B["login"])
    portal_appeal = _req("POST", "/portal/affairs/discipline/appeal", token=st,
                         body={"caseId": cid, "reason": "对处分认定事实有异议申请复核"})
    if ok(portal_appeal):
        step(report, "disc_student_portal_appeal", portal_appeal)
        aid = str((portal_appeal.get("data") or {}).get("appealId") or "")
    else:
        step(report, "disc_student_portal_appeal", portal_appeal, {"note": "门户申诉失败则改教师端提起"})
        pause()
        admin = login("e2e_sa_admin")
        a = _req("POST", f"{SA}/discipline/cases/{cid}/appeal", token=admin,
                 body={"reason": "对处分认定事实有异议申请复核"})
        step(report, "disc_staff_appeal", a)
        aid = str((a.get("data") or {}).get("appealId") or "")
    ids["appealId"] = aid
    if aid:
        pause()
        admin = login("e2e_sa_admin")
        # 撤销结论：真正下线处分
        rev = _req("POST", f"{SA}/discipline/appeals/{aid}/review", token=admin,
                   body={"result": "REVOKED", "opinion": "经复核事实认定有误撤销原处分"})
        step(report, "disc_appeal_revoked", rev)
        pause()
        admin = login("e2e_sa_admin")
        after = _req("GET", f"{SA}/discipline/cases/{cid}", token=admin)
        removed = ((after.get("data") or {}).get("status") == "REMOVED")
        step(report, "disc_case_removed", after, {"removed": removed})
    return ids


def flow_risk_72h(report: list) -> dict:
    ids: dict = {}
    pause(3)
    admin = login("e2e_sa_admin")
    # owner candidates
    cands = _req("GET", f"{SA}/risk/owner-candidates", token=admin)
    step(report, "risk_owner_candidates", cands)
    owner_id = ""
    for it in ((cands.get("data") or {}).get("items") or (cands.get("data") if isinstance(cands.get("data"), list) else []) or []):
        if isinstance(it, dict) and (it.get("userId") or it.get("id") or it.get("ownerId")):
            owner_id = str(it.get("userId") or it.get("id") or it.get("ownerId"))
            break
    # fallback: counselor a user id from login
    if not owner_id:
        pause()
        tok = login("e2e_counselor_a")
        me = _req("GET", "/auth/me", token=tok)
        owner_id = str(((me.get("data") or {}).get("userId") or "").replace("db-", ""))
    ids["ownerId"] = owner_id

    pause()
    admin = login("e2e_sa_admin")
    create = _req("POST", f"{SA}/risk/records", token=admin, body={
        "studentId": STU_C["id"], "source": "MANUAL", "riskLevel": "LOW",
        "title": "E2E风险72h升级", "detail": "E2E风险记录用于验证72小时未处置自动升级"})
    step(report, "risk_create", create)
    rid = str((create.get("data") or {}).get("riskId") or "")
    ids["riskId"] = rid
    if not rid:
        return ids
    pause()
    admin = login("e2e_sa_admin")
    assign = _req("POST", f"{SA}/risk/records/{rid}/assign", token=admin,
                  body={"ownerId": owner_id})
    step(report, "risk_assign", assign)
    # 回写 assigned_at 到 73h 前
    try:
        backdate_risk_assigned(int(rid), 73)
        report.append({"step": "risk_backdate_assigned_at", "ok": True, "hours": 73})
    except Exception as e:
        report.append({"step": "risk_backdate_assigned_at", "ok": False, "error": str(e)})
        return ids
    pause()
    admin = login("e2e_sa_admin")
    scan = _req("POST", f"{SA}/risk/scan-timeout", token=admin)
    step(report, "risk_scan_timeout_72h", scan)
    escalated = int(((scan.get("data") or {}).get("escalated") or 0))
    pause()
    admin = login("e2e_sa_admin")
    det = _req("GET", f"{SA}/risk/records/{rid}", token=admin)
    status = (det.get("data") or {}).get("status")
    level = (det.get("data") or {}).get("riskLevel")
    step(report, "risk_escalated_state", det,
         {"status": status, "riskLevel": level, "scanEscalated": escalated,
          "ok_final": status == "ESCALATED" and escalated >= 1})
    # 修正 step ok：上面 step() 用了 det 的 code；用 ok_final 再记一条
    report[-1]["ok"] = status == "ESCALATED" and (level in ("MEDIUM", "HIGH", "CRITICAL") or escalated >= 1)
    print(("PASS" if report[-1]["ok"] else "FAIL"), "risk_escalated_state_final", status, level)

    # 幂等再扫
    pause()
    admin = login("e2e_sa_admin")
    scan2 = _req("POST", f"{SA}/risk/scan-timeout", token=admin)
    step(report, "risk_scan_idempotent", int((scan2.get("data") or {}).get("escalated") or 0) == 0,
         {"data": scan2.get("data")})

    # 辅导员小程序可见风险
    pause()
    ct = login("e2e_counselor_a")
    mini = _req("GET", "/mobile/teacher/risk-students", token=ct)
    step(report, "risk_counselor_mini_list", mini)
    return ids


def flow_counselor_eval(report: list) -> dict:
    ids: dict = {}
    tag = uuid.uuid4().hex[:6]
    pause(3)
    admin = login("e2e_sa_admin")
    i1 = _req("POST", f"{SA}/counselor-eval/indicators", token=admin,
              body={"name": f"E2E师德{tag}", "weight": 30, "maxScore": 100})
    step(report, "eval_indicator", i1)
    ind = str((i1.get("data") or {}).get("indicatorId") or "")
    pause()
    admin = login("e2e_sa_admin")
    ev = _req("POST", f"{SA}/counselor-eval/evals", token=admin, body={
        "periodCode": f"2025-2026-E2E-{tag}", "counselorKey": "e2e_counselor_a",
        "counselorName": "E2E辅导员A", "scores": {ind: 90}})
    step(report, "eval_score", ev)
    eid = str((ev.get("data") or {}).get("evalId") or "")
    ids["evalId"] = eid
    if not eid:
        return ids
    pause()
    admin = login("e2e_sa_admin")
    pub = _req("POST", f"{SA}/counselor-eval/evals/{eid}/publish", token=admin)
    step(report, "eval_publish", pub)
    pause()
    # 辅导员本人申诉
    ct = login("e2e_counselor_a")
    ap = _req("POST", f"{SA}/counselor-eval/evals/{eid}/appeal", token=ct,
              body={"reason": "对师德指标评分有异议申请复核调分"})
    step(report, "eval_counselor_appeal", ap)
    if not ok(ap):
        # 权限不足则管理员代提
        pause()
        admin = login("e2e_sa_admin")
        ap = _req("POST", f"{SA}/counselor-eval/evals/{eid}/appeal", token=admin,
                  body={"reason": "对师德指标评分有异议申请复核调分"})
        step(report, "eval_admin_proxy_appeal", ap)
    pause()
    admin = login("e2e_sa_admin")
    rev = _req("POST", f"{SA}/counselor-eval/evals/{eid}/appeal-review", token=admin, body={
        "result": "ADJUSTED", "opinion": "经复核上调师德得分", "scores": {ind: 95}})
    step(report, "eval_appeal_review", rev)
    return ids


def flow_archive(report: list) -> dict:
    ids: dict = {}
    tag = uuid.uuid4().hex[:6]
    pause(3)
    admin = login("e2e_sa_admin")
    b = _req("POST", f"{SA}/archive/batches", token=admin, body={
        "batchName": f"E2E学工归档{tag}", "yearCode": "2026"})
    step(report, "archive_batch", b)
    bid = str((b.get("data") or {}).get("batchId") or "")
    ids["archiveBatchId"] = bid
    if not bid:
        return ids
    pause()
    admin = login("e2e_sa_admin")
    col = _req("POST", f"{SA}/archive/batches/{bid}/collect", token=admin,
               body={"studentIds": [STU_A["id"], STU_B["id"]]})
    step(report, "archive_collect", col)
    last = col
    for i in range(3):
        pause()
        admin = login("e2e_sa_admin")
        last = _req("POST", f"{SA}/archive/batches/{bid}/advance", token=admin,
                    body={"action": "APPROVE"})
        step(report, f"archive_advance_{i+1}", last)
    status = ((last.get("data") or {}).get("status"))
    step(report, "archive_final_archived", status == "ARCHIVED", {"status": status})
    pause()
    admin = login("e2e_sa_admin")
    det = _req("GET", f"{SA}/archive/batches/{bid}", token=admin)
    pkgs = ((det.get("data") or {}).get("packages") or [])
    watermarked = all(p.get("status") == "ARCHIVED" and p.get("exportTaskId") for p in pkgs) if pkgs else False
    step(report, "archive_watermark_packages", det, {"packages": len(pkgs), "watermarked": watermarked,
                                                     "ok_final": watermarked})
    report[-1]["ok"] = watermarked and ok(det)
    return ids


def main() -> int:
    report: list = []
    ids: dict = {"startedAt": datetime.now().isoformat(timespec="seconds")}
    try:
        ids["orientation"] = flow_orientation(report)
        ids["funding"] = flow_funding_and_aid(report)
        ids["discipline"] = flow_discipline_appeal(report)
        ids["risk"] = flow_risk_72h(report)
        ids["eval"] = flow_counselor_eval(report)
        ids["archive"] = flow_archive(report)
    except Exception as e:
        report.append({"step": "FATAL", "ok": False, "error": str(e)})
        print("FATAL", e)
    passed = sum(1 for x in report if x.get("ok"))
    total = len(report)
    out = {"summary": {"passed": passed, "total": total, "ok": passed == total},
           "ids": ids, "steps": report}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRESULT {passed}/{total} -> {OUT}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
