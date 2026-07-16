"""13B-P6 毕业资格预审 · 端到端（十项供数三态 + 终审经单一入口 + 三名单）。
Tier1 R1 起由七项扩展为十项（新增 STATUS_CHANGE/DISCIPLINE 等联动项，见 grade-graduation.js GRAD_ITEM_LABEL）。

GR1 生成+预审→SYSTEM_PASSED；GR2 学籍异常→SYSTEM_ABNORMAL；GR3 全链终审写学籍GRADUATED;
GR4 终审无二次确认409；GR5 三名单；GR6 预审幂等(rerun)。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


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


def test_gr1_precheck_passed(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    r = _gen_precheck(client, hdr, bid, ids["s"])
    assert r["passed"] == 1 and r["abnormal"] == 0  # 在籍PASS，其余UNKNOWN不阻断
    rid = _result_id(client, hdr, bid)
    d = client.get(f"{BASE}/graduation-results/{rid}", headers=hdr).json()["data"]
    # 十一项（Tier1 R1 扩展十项 + R3 补 FEE 费用结清）。FEE 恒 UNKNOWN（待接入学校财务系统）且
    # 不阻断——overall 仍为 SYSTEM_PASSED，正是"提醒不卡审"的既定口径（见 _check_fee 注释与
    # graduation.conditions.feeCheck 默认 false）。
    assert d["overall"] == "SYSTEM_PASSED" and len(d["items"]) == 11
    fee = next(i for i in d["items"] if i["item"] == "FEE")
    assert fee["result"] == "UNKNOWN" and "财务系统" in fee["evidence"]


def test_gr2_status_abnormal(client, db_mode):
    ids = _seed(db_mode, "SUSPENDED")  # 休学中 → 学籍不在籍
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
    client.post(f"{BASE}/graduation-results/{rid}/college-review", headers=hdr, json={"action": "APPROVE"})
    r = client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                    json={"conclusion": "GRADUATED", "confirm": True}).json()
    assert r["data"]["conclusion"] == "GRADUATED"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    assert db.get(StudentProfile, ids["s"]).student_status == "GRADUATED"  # 经单一入口写主档
    db.close()


def test_gr4_final_needs_confirm(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    client.post(f"{BASE}/graduation-results/{rid}/college-review", headers=hdr, json={"action": "APPROVE"})
    # 无二次确认 → 409
    assert client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                       json={"conclusion": "GRADUATED", "confirm": False}).status_code == 409


def test_gr5_rosters(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    client.post(f"{BASE}/graduation-results/{rid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                json={"conclusion": "GRADUATED", "confirm": True})
    ro = client.get(f"{BASE}/graduation-audit-batches/{bid}/rosters", headers=hdr).json()["data"]
    assert ro["counts"]["GRADUATED"] == 1


def test_gr6_precheck_idempotent(client, db_mode):
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    client.post(f"{BASE}/graduation-audit-batches/{bid}/precheck", headers=hdr)  # 重跑
    d = client.get(f"{BASE}/graduation-results/{_result_id(client, hdr, bid)}", headers=hdr).json()["data"]
    assert d["rerunCount"] == 2  # 覆盖非追加，rerun 计数


def test_gr7_roster_org_names(client, db_mode):
    """毕业学生名单（三级菜单补建）：三名单补全学号/学院/专业/班级，供 audit-console roster tab 使用。"""
    ids = _seed(db_mode, "REGISTERED")
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _gen_precheck(client, hdr, bid, ids["s"])
    rid = _result_id(client, hdr, bid)
    client.post(f"{BASE}/graduation-results/{rid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/graduation-results/{rid}/final", headers=hdr,
                json={"conclusion": "GRADUATED", "confirm": True})
    ro = client.get(f"{BASE}/graduation-audit-batches/{bid}/rosters", headers=hdr).json()["data"]
    row = ro["graduated"][0]
    assert row["studentNo"] == "GR001"
    assert row["realName"] == "毕业甲"
    assert row["className"] == "软件2301"  # _seed 建的 SchoolClass.class_name


def test_gr8_college_reject_reason_roundtrip(client, db_mode):
    """不通过原因（三级菜单补建）：退回原因<5字→400；退回后 reviewNote/studentNo 经 list_results(status=REJECTED)
    正确回传（此前 _row() 未透出 reviewNote，audit-console 详情抽屉的「最近处理意见」实为死代码，一并修复）。"""
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
