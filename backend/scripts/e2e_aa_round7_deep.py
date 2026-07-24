# -*- coding: utf-8 -*-
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001/api/v1"
TENANT = "sandbox-school"
STABLE = "E2eTest@2026"


def req(method, path, token=None, body=None):
    data = None
    hdrs = {}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        hdrs["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(raw)
            j["http"] = e.code
            return j
        except Exception:
            return {"code": e.code, "http": e.code, "message": raw[:400]}


def login(ln, pwd=None, client="PC"):
    pwd = pwd or ("123456" if ln == "admin2" else STABLE)
    r = req("POST", "/auth/login", body={
        "loginName": ln, "password": pwd, "tenantCode": TENANT, "clientType": client,
    })
    assert r.get("code") == 0, r
    return r["data"]["accessToken"]


def main():
    issues = []
    stu = login("E2EAA20260001", client="MINI_PROGRAM")
    adm = login("e2e_aa_admin")

    print("=== REGISTRATION DETAIL ===")
    reg = req("GET", "/mobile/academic/registration/my", token=stu)["data"]
    batches = reg.get("batches") or []
    print("batches", len(batches), "studentStatus", reg.get("studentStatus"))
    if not batches:
        issues.append("无开放注册批次（环境数据）— 自助注册写路径未在本轮真实执行")
    else:
        b = batches[0]
        print("batch", b.get("batchName"), "canRegister", b.get("canRegister"),
              "status", b.get("registrationStatus"), "elig", b.get("eligibilityStatus"),
              "block", b.get("blockReason"))
        r = req("POST", f"/mobile/academic/registration/{b['batchId']}/register", token=stu)
        print("SELF_REGISTER", r.get("code"), r.get("bizCode"), r.get("message"), r.get("data"))
        if b.get("canRegister") and r.get("code") != 0:
            issues.append(f"可注册批次自助注册失败: {r.get('message')}")
        if not b.get("canRegister") and r.get("code") == 0:
            issues.append("不可注册批次却注册成功（异常）")

    print("=== STATUS PENDING ADMIN ===")
    sp = req("GET", "/mobile/teacher/academic/status-changes/pending", token=adm).get("data") or {}
    print("total", sp.get("total"))
    for it in (sp.get("list") or [])[:5]:
        print({k: it.get(k) for k in ("changeId", "realName", "changeType", "status", "currentNode")})
    if (sp.get("total") or 0) == 0:
        issues.append("教务管理员异动待审为空（环境）— 审批写路径未在本轮真实执行")

    print("=== FEE MARK DEEP ===")
    cb = req("POST", "/academic-affairs/graduation-audit-batches", token=adm,
             body={"batchName": "Round7费用冒烟批次", "gradeYear": "2026"})
    print("create", cb.get("code"), cb.get("message"), cb.get("data"))
    bid = (cb.get("data") or {}).get("batchId")
    if not bid:
        issues.append(f"无法创建毕业审核批次: {cb.get('message')}")
    else:
        g = req("POST", f"/academic-affairs/graduation-audit-batches/{bid}/generate", token=adm, body={})
        print("generate", g.get("code"), g.get("message"), g.get("data"))
        p = req("POST", f"/academic-affairs/graduation-audit-batches/{bid}/precheck", token=adm)
        print("precheck", p.get("code"), p.get("message"), p.get("data"))
        bad = req("POST", f"/academic-affairs/graduation-audit-batches/{bid}/fee-clearance/mark",
                  token=adm, body={"studentNo": "E2EAA20260001", "status": "PASS"})
        print("mark PASS", bad.get("code"), bad.get("message"))
        if bad.get("code") == 0:
            issues.append("fee mark 接受了非法 status=PASS")
        ok = req("POST", f"/academic-affairs/graduation-audit-batches/{bid}/fee-clearance/mark",
                 token=adm, body={"studentNo": "E2EAA20260001", "status": "CLEARED",
                                  "evidence": "Round7 live smoke"})
        print("mark CLEARED", ok.get("code"), ok.get("message"), ok.get("data"))
        data = ok.get("data") or {}
        if ok.get("code") != 0:
            issues.append(f"fee mark CLEARED 失败: {ok.get('message')}")
        elif data.get("updated", 0) == 0:
            issues.append("fee mark CLEARED 返回 updated=0（学生可能不在批次内）")
        res = req("GET", f"/academic-affairs/graduation-audit-batches/{bid}/results?item=FEE&pageSize=50",
                  token=adm)
        rows = ((res.get("data") or {}).get("list") or [])
        print("fee rows", len(rows))
        hit = False
        for row in rows:
            fee = next((i for i in (row.get("items") or []) if i.get("item") == "FEE"), {})
            if row.get("studentNo") == "E2EAA20260001":
                hit = True
                print("E2E student FEE", fee.get("result"), fee.get("evidence"))
                if fee.get("result") != "PASS":
                    issues.append(f"勾选后 FEE 结果不是 PASS: {fee}")
        if rows and not hit:
            issues.append("批次有 FEE 行但未包含 E2EAA20260001")

    print("=== MAKEUP EMPTY STATE ===")
    opts = req("GET", "/mobile/academic/makeup/options", token=stu).get("data") or {}
    print("retake", opts.get("retakeTotal"), "exemption", opts.get("exemptionTotal"), "note", opts.get("note"))
    if (opts.get("retakeTotal") or 0) == 0:
        issues.append("当前学生无挂科（环境）— 重修列表选择写路径未在本轮真实提交")

    print("\nISSUES:")
    for i, x in enumerate(issues, 1):
        print(f"{i}. {x}")
    if not issues:
        print("(none)")


if __name__ == "__main__":
    main()
