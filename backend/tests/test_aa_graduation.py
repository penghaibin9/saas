"""13B-P6 毕业资格预审 · 端到端（十一项供数三态 + 终审经单一入口 + 三名单）。

Stage C3/D-W0 正式不可变评估按 required evidence fail-closed：blocking UNKNOWN/FAIL 进入
SYSTEM_ABNORMAL；非阻断提醒仍可 UNKNOWN。普通教务终审只能引用 latest SYSTEM_PASSED
GraduationEvaluationRun，review_note 只做审核留痕，不能充当毕业 Override。
"""
from __future__ import annotations

import hashlib
import json

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"
_REVIEW_NOTE = "已完成人工核验并留存学院初审意见"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, status="REGISTERED"):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2301", grade="2023", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="GR001", real_name="毕业甲", class_id=a.id, grade="2023",
                       major_id=1, current_stage="ON_CAMPUS", student_status=status, status="ACTIVE")
    db.add(s); db.flush()
    ids = {"s": s.id}
    db.commit()
    db.close()
    return ids


def _batch(client, hdr):
    return client.post(f"{BASE}/graduation-audit-batches", headers=hdr, json={
        "batchName": "2023届毕业预审", "gradeYear": "2023"}).json()["data"]["batchId"]


def _gen_precheck(client, hdr, bid, sid):
    client.post(f"{BASE}/graduation-audit-batches/{bid}/generate", headers=hdr,
                json={"studentIds": [str(sid)]})
    return client.post(f"{BASE}/graduation-audit-batches/{bid}/precheck", headers=hdr).json()["data"]


def _result_id(client, hdr, bid):
    return client.get(f"{BASE}/graduation-audit-batches/{bid}/results", headers=hdr).json()["data"]["items"][0]["resultId"]


def _approve_for_final(client, hdr, rid):
    resp = client.post(
        f"{BASE}/graduation-results/{rid}/college-review",
        headers=hdr,
        json={"action": "APPROVE", "note": _REVIEW_NOTE},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "ACADEMIC_REVIEW"


def _append_formal_pass_fixture(rid, sid):
    """Append a semantically consistent PASS run for tests that exercise final/read projections.

    The initial real precheck run remains immutable and abnormal. This helper models a later
    formal rerun after blockers were resolved by appending Run#N; it never overwrites history.
    """
    from app.db.session import get_sessionmaker
    from app.models import AaGraduationAuditResult, GraduationEvaluationRun
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as graduation_service

    db = get_sessionmaker()()
    try:
        result = db.get(AaGraduationAuditResult, int(rid))
        previous = db.query(GraduationEvaluationRun).filter(
            GraduationEvaluationRun.tenant_id == TID,
            GraduationEvaluationRun.result_id == result.id,
        ).order_by(GraduationEvaluationRun.run_no.desc()).first()
        assert previous is not None
        run_no = int(previous.run_no) + 1
        items = [
            {"item": code, "result": "PASS", "evidence": "D-W0 resolved formal fixture"}
            for code in sorted(graduation_service._BLOCKING_UNKNOWN_ITEMS)
        ]
        items.extend([
            {"item": "EMPLOYMENT", "result": "UNKNOWN", "evidence": "非毕业硬门提醒"},
            {"item": "ARCHIVE", "result": "UNKNOWN", "evidence": "人工复核提醒"},
            {"item": "FEE", "result": "UNKNOWN", "evidence": "财务未对接，本项不阻断"},
        ])
        payload = json.dumps(items, ensure_ascii=False, sort_keys=True)
        marker = hashlib.sha256(f"D-W0:{rid}:{sid}:{run_no}".encode("utf-8")).hexdigest()
        db.add(GraduationEvaluationRun(
            tenant_id=TID,
            batch_id=result.batch_id,
            result_id=result.id,
            student_id=int(sid),
            run_no=run_no,
            program_id=previous.program_id,
            input_snapshot_json=json.dumps({"contract": "D-W0", "resolved": True}, ensure_ascii=False),
            input_hash=marker,
            item_results_json=payload,
            overall="SYSTEM_PASSED",
            evaluator_version=previous.evaluator_version,
        ))
        result.item_results_json = payload
        result.overall = "SYSTEM_PASSED"
        result.status = "SYSTEM_PASSED"
        result.rerun_count = run_no
        db.commit()
    finally:
        db.close()


def test_gr1_precheck_passed(client, db_mode):
    """历史名称保留：验证 blocking UNKNOWN 仍进入正式异常队列。"""
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    r = _gen_precheck(client, hdr, bid, ids["s"])
    assert r["passed"] == 0 and r["abnormal"] == 1
    rid = _result_id(client, hdr, bid)
    d = client.get(f"{BASE}/graduation-results/{rid}", headers=hdr).json()["data"]
    assert d["overall"] == "SYSTEM_ABNORMAL" and len(d["items"]) == 11
    fee = next(i for i in d["items"] if i["item"] == "FEE")
    assert fee["result"] == "UNKNOWN"
    assert fee["owner"] == "FINANCE"
    assert "财务" in fee["evidence"] and "不阻断" in fee["evidence"]
    blocking_unknown = [
        i for i in d["items"]
        if i["item"] in {"STATUS", "CREDIT", "COURSE_REQUIRED", "COURSE_ELECTIVE", "PRACTICE",
                         "INTERNSHIP", "GRADUATION_DESIGN", "DISCIPLINE"}
        and i["result"] == "UNKNOWN"
    ]
    assert blocking_unknown


def test_gr2_status_abnormal(client, db_mode):
    ids = _seed(db_mode, "SUSPENDED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    r = _gen_precheck(client, hdr, bid, ids["s"])
    assert r["abnormal"] == 1
    d = client.get(f"{BASE}/graduation-results/{_result_id(client, hdr, bid)}", headers=hdr).json()["data"]
    status_item = next(i for i in d["items"] if i["item"] == "STATUS")
    assert d["overall"] == "SYSTEM_ABNORMAL" and status_item["result"] == "FAIL"


def test_gr3_final_writes_status(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    _append_formal_pass_fixture(rid, ids["s"])
    _approve_for_final(client, hdr, rid)
    final = client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                        json={"conclusion": "GRADUATED", "confirm": True})
    assert final.status_code == 200, final.text
    r = final.json()
    assert r["data"]["conclusion"] == "GRADUATED"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    assert db.get(StudentProfile, ids["s"]).student_status == "GRADUATED"
    db.close()


def test_gr4_final_needs_confirm(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    _approve_for_final(client, hdr, rid)
    assert client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                       json={"conclusion": "GRADUATED", "confirm": False}).status_code == 409


def test_gr5_rosters(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    _append_formal_pass_fixture(rid, ids["s"])
    _approve_for_final(client, hdr, rid)
    final = client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                        json={"conclusion": "GRADUATED", "confirm": True})
    assert final.status_code == 200, final.text
    ro = client.get(f"{BASE}/graduation-audit-batches/{bid}/rosters", headers=hdr).json()["data"]
    assert ro["counts"]["GRADUATED"] == 1


def test_gr6_precheck_idempotent(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    client.post(f"{BASE}/graduation-audit-batches/{bid}/precheck", headers=hdr)
    d = client.get(f"{BASE}/graduation-results/{_result_id(client, hdr, bid)}", headers=hdr).json()["data"]
    assert d["rerunCount"] == 2


def test_gr7_roster_org_names(client, db_mode):
    """毕业学生名单补全学号/学院/专业/班级，供 audit-console roster tab 使用。"""
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    _append_formal_pass_fixture(rid, ids["s"])
    _approve_for_final(client, hdr, rid)
    final = client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                        json={"conclusion": "GRADUATED", "confirm": True})
    assert final.status_code == 200, final.text
    ro = client.get(f"{BASE}/graduation-audit-batches/{bid}/rosters", headers=hdr).json()["data"]
    row = ro["graduated"][0]
    assert row["studentNo"] == "GR001"
    assert row["realName"] == "毕业甲"
    assert row["className"] == "软件2301"


def test_gr8_college_reject_reason_roundtrip(client, db_mode):
    """退回原因<5字→400；正式退回原因经列表与详情一致回传。"""
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    bad = client.post(f"{BASE}/graduation-results/{rid}/college-review", headers=hdr,
                      json={"action": "REJECT", "note": "太短"})
    assert bad.status_code == 400
    ok = client.post(f"{BASE}/graduation-results/{rid}/college-review", headers=hdr,
                     json={"action": "REJECT", "note": "材料不全，缺实习鉴定表"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "REJECTED"
    lst = client.get(f"{BASE}/graduation-audit-batches/{bid}/results", headers=hdr,
                     params={"status": "REJECTED"}).json()["data"]["items"]
    assert len(lst) == 1
    assert lst[0]["reviewNote"] == "材料不全，缺实习鉴定表"
    assert lst[0]["studentNo"] == "GR001"
    detail = client.get(f"{BASE}/graduation-results/{rid}", headers=hdr).json()["data"]
    assert detail["reviewNote"] == "材料不全，缺实习鉴定表"


def test_gr9_fee_clearance_cannot_upgrade_other_unknowns(client, db_mode):
    """财务回填只解决 FEE；其它 blocking UNKNOWN 未解除时 projection 仍必须 fail-closed。"""
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    precheck = _gen_precheck(client, hdr, bid, ids["s"])
    assert precheck["passed"] == 0 and precheck["abnormal"] == 1

    resp = client.post(
        f"{BASE}/graduation-audit-batches/{bid}/fee-clearance",
        headers=hdr,
        json={"rows": [{
            "studentNo": "GR001",
            "status": "CLEARED",
            "evidence": "财务已人工核验并确认费用结清",
        }]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["updated"] == 1

    rid = _result_id(client, hdr, bid)
    detail = client.get(f"{BASE}/graduation-results/{rid}", headers=hdr).json()["data"]
    fee = next(i for i in detail["items"] if i["item"] == "FEE")
    assert fee["result"] == "PASS"
    assert detail["overall"] == "SYSTEM_ABNORMAL"
    assert detail["status"] == "SYSTEM_ABNORMAL"
    assert any(
        i["item"] in {"STATUS", "CREDIT", "COURSE_REQUIRED", "COURSE_ELECTIVE", "PRACTICE",
                      "INTERNSHIP", "GRADUATION_DESIGN", "DISCIPLINE"}
        and i["result"] == "UNKNOWN"
        for i in detail["items"]
    )
