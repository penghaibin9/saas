"""教务中心·学籍管理 Tier1 R3：学籍信息更正 · 端到端（真实 DB 模式）。

C1 更正审核通过→主档字段同步+审计留痕；C2 驳回需理由≥5字，驳回后主档不变；
C3 同学生同字段在途重复409；C4 更正字段范围排除学籍状态（单一写入口红线，400）；
C5 无权限角色（辅导员）发起更正403；C6 性别非法取值400。
C7-C10（R3 合规补建）：关键身份字段无证明材料400 / 带真实材料200并回显 / 伪造file_id 400 /
非关键字段材料选填200。
（HTTP 状态口径对齐 app/core/exceptions.py CODE_HTTP：VALIDATION_ERROR→400，非 422，
 与本仓库 test_aa_course.py/test_aa_calendar_period.py 等既有校验失败用例一致。）
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA100", real_name="更正甲", gender="男",
                       id_card_encrypted="110101200001011234", grade="2021", class_id=a.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"s": s.id}
    db.commit()
    db.close()
    return ids


def _seed_file(db_mode, name="户籍证明.pdf"):
    """造一个真实 t_file_object（证明材料附件回链目标，与 AaExemption 免修材料同款机制）。"""
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    db = get_sessionmaker()()
    f = FileObject(tenant_id=TID, file_key=f"test/{name}", file_name=name, ext="pdf",
                   mime_type="application/pdf", size_bytes=1024, biz_type="ATTACHMENT", status="STORED")
    db.add(f); db.flush()
    fid = f.id
    db.commit()
    db.close()
    return str(fid)


def _apply(client, hdr, sid, field_key, new_value, reason="数据录入错误据实更正", material=None):
    body = {"studentId": str(sid), "fieldKey": field_key, "newValue": new_value, "reason": reason}
    if material is not None:
        body["materialFileIds"] = material if isinstance(material, list) else [material]
    return client.post(f"{BASE}/roster/corrections", headers=hdr, json=body)


def test_c0_list_static_route_not_captured_by_student_detail(client, db_mode):
    """静态 /roster/corrections 必须先于 /roster/{studentId}，不能把 corrections 当整数 ID。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/roster/corrections?page=1&pageSize=10", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["code"] == 0
    assert isinstance(r.json()["data"]["items"], list)


def test_c1_approve_syncs_profile_and_audits(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "REAL_NAME", "更正乙", material=_seed_file(db_mode))
    assert r.status_code == 200, r.text
    cid = r.json()["data"]["correctionId"]
    rv = client.post(f"{BASE}/roster/corrections/{cid}/review", headers=hdr,
                     json={"action": "APPROVE"})
    assert rv.status_code == 200, rv.text
    assert rv.json()["data"]["status"] == "APPROVED"
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    assert s.real_name == "更正乙"  # 主档已同步
    cnt = db.query(AffairsAuditTrail).filter_by(
        biz_type="AA_STUDENT_CORRECTION", biz_id=int(cid), action="APPROVE").count()
    assert cnt == 1  # 审计留痕
    db.close()


def test_c2_reject_requires_reason_and_keeps_profile(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "GRADE", "2022")
    cid = r.json()["data"]["correctionId"]
    short = client.post(f"{BASE}/roster/corrections/{cid}/review", headers=hdr,
                        json={"action": "REJECT", "note": "太短"})
    assert short.status_code == 400
    ok = client.post(f"{BASE}/roster/corrections/{cid}/review", headers=hdr,
                     json={"action": "REJECT", "note": "材料不足，退回补充证明"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "REJECTED"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    assert s.grade == "2021"  # 驳回不改主档
    db.close()


def test_c3_duplicate_pending_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r1 = _apply(client, hdr, ids["s"], "STUDENT_NO", "AA200")
    assert r1.status_code == 200
    r2 = _apply(client, hdr, ids["s"], "STUDENT_NO", "AA201")
    assert r2.status_code == 409


def test_c4_status_field_out_of_scope_400(client, db_mode):
    """学籍状态/组织归属不在更正范围内（必须走「学籍异动」单一入口），杜绝绕过 change_student_status。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "STUDENT_STATUS", "SUSPENDED")
    assert r.status_code == 400


def test_c5_counselor_no_permission_403(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")
    r = _apply(client, hdr, ids["s"], "REAL_NAME", "越权改名")
    assert r.status_code == 403


def test_c6_gender_invalid_value_400(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "GENDER", "other")
    assert r.status_code == 400


# ═══════════ 证明材料强制（R3 外部法规核验后补建的合规红线）═══════════
# 依据：教职成〔2014〕12号第十六条（中职直接适用，"上传证明材料"是条文原文）+ 教育部令41号
# 第三十四条（"提供有法定效力的相应证明文件"）+ 教基一〔2014〕8号（身份证号/姓名/性别/出生日期
# 为关键信息，需户籍部门出具）。学号/年级不强制——户籍部门无法为校内编码/学业属性出具证明。


def test_c7_key_field_without_material_400(client, db_mode):
    """关键身份字段（姓名/性别/证件号）无证明材料 → 400（合规红线，不是可选项）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    for field, value in (("REAL_NAME", "无附件甲"), ("GENDER", "女"), ("ID_CARD", "110101200002022345")):
        r = _apply(client, hdr, ids["s"], field, value)
        assert r.status_code == 400, f"{field} 应因缺证明材料被拒：{r.text}"
        assert "证明材料" in r.json()["message"], r.text


def test_c8_key_field_with_material_ok_and_echo(client, db_mode):
    """关键身份字段带真实证明材料 → 200，且 materialFileIds/materialRequired 正确回显。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    fid = _seed_file(db_mode)
    r = _apply(client, hdr, ids["s"], "ID_CARD", "110101200002022345", material=fid)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["materialFileIds"] == [fid]
    assert d["materialRequired"] is True


def test_c9_material_invalid_file_id_400(client, db_mode):
    """证明材料 file_id 不是本租户真实文件对象 → 400（防伪造 id，同 AaExemption 免修材料校验）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "REAL_NAME", "伪造附件甲", material="99999999")
    assert r.status_code == 400, r.text
    assert "无效文件" in r.json()["message"], r.text


def test_c10_non_key_field_material_optional(client, db_mode):
    """非关键字段（年级）无证明材料仍可提交 → 200，materialRequired=False。
    教基一〔2014〕8号：非关键信息由学校直接维护，不要求附件；且户籍部门无法为"年级"出具证明。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "GRADE", "2022")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["materialRequired"] is False
