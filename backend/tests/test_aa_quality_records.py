"""教学质量 R3 续工端点测试（/academic-affairs/quality/records|rectifications|archive/*）。

覆盖三级卡 01督导听课/02巡课记录/03教学检查/04教学事故（共用 records，recordType判别）、
05质量整改/06整改跟进（共用 rectifications）、09质量归档（读侧聚合+导出）。
MySQL-only（db_mode 夹具，TEST_DATABASE_URL）。口径核对
docs/03-业务模块设计/教务中心/施工包/教学质量/三级施工卡/{01..06,09}-*.md。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed_colleges(db_mode):
    """两个学院 + college_admin01→软件学院数据范围（复用 test_aa_stats.py 已验证的种子模式）。"""
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope
    db = get_sessionmaker()()
    soft = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    other = College(tenant_id=TID, college_name="机械学院", status="ACTIVE")
    db.add_all([soft, other]); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", role_code="COLLEGE_ADMIN",
                              scope_type="COLLEGE", ref_value="软件学院", status="ACTIVE"))
    db.commit()
    ids = {"soft": soft.id, "other": other.id}
    db.close()
    return ids


# ────────────────────── 01/02/03 问题记录：主流程 ──────────────────────

def test_r1_supervision_create_confirm_close(client, db_mode):
    admin = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/quality/records", headers=admin,
                    json={"recordType": "SUPERVISION", "title": "2026春第3周推门听课",
                          "teacherName": "王老师", "courseName": "高等数学", "score": 88,
                          "conclusion": "合格", "description": "课堂组织良好"})
    assert r.status_code == 200
    rec = r.json()["data"]
    assert rec["status"] == "SUBMITTED" and rec["recordType"] == "SUPERVISION"
    rid = rec["recordId"]
    # 详情
    d = client.get(f"{BASE}/quality/records/{rid}", headers=admin).json()["data"]
    assert d["title"] == "2026春第3周推门听课" and d["score"] == 88.0
    # 确认
    c = client.post(f"{BASE}/quality/records/{rid}/confirm", headers=admin).json()["data"]
    assert c["status"] == "CONFIRMED" and c["confirmedByName"]
    # 未 CONFIRMED 不可再次 confirm
    assert client.post(f"{BASE}/quality/records/{rid}/confirm", headers=admin).status_code == 409
    # 关闭
    cl = client.post(f"{BASE}/quality/records/{rid}/close", headers=admin).json()["data"]
    assert cl["status"] == "CLOSED"


def test_r2_patrol_and_inspection_list_filter(client, db_mode):
    admin = _hdr(client, "school_admin01")
    client.post(f"{BASE}/quality/records", headers=admin,
               json={"recordType": "PATROL", "title": "教学楼A巡查", "location": "A101",
                     "category": "迟到", "description": "任课教师迟到5分钟"})
    client.post(f"{BASE}/quality/records", headers=admin,
               json={"recordType": "INSPECTION", "title": "期末命题专项检查", "teacherName": "李老师",
                     "conclusion": "待整改", "needRectify": True})
    only_patrol = client.get(f"{BASE}/quality/records", headers=admin,
                             params={"recordType": "PATROL"}).json()["data"]
    assert only_patrol["total"] == 1 and only_patrol["items"][0]["recordType"] == "PATROL"
    only_insp = client.get(f"{BASE}/quality/records", headers=admin,
                           params={"recordType": "INSPECTION"}).json()["data"]
    assert only_insp["total"] == 1 and only_insp["items"][0]["needRectify"] is True
    # 非法 recordType
    assert client.get(f"{BASE}/quality/records", headers=admin,
                      params={"recordType": "BOGUS"}).status_code == 400


def test_r3_edit_only_submitted(client, db_mode):
    admin = _hdr(client, "school_admin01")
    rid = client.post(f"{BASE}/quality/records", headers=admin,
                      json={"recordType": "PATROL", "title": "巡课草稿"}).json()["data"]["recordId"]
    ok = client.put(f"{BASE}/quality/records/{rid}", headers=admin, json={"title": "巡课已改标题"})
    assert ok.status_code == 200 and ok.json()["data"]["title"] == "巡课已改标题"
    client.post(f"{BASE}/quality/records/{rid}/confirm", headers=admin)
    # CONFIRMED 后不可再编辑
    blocked = client.put(f"{BASE}/quality/records/{rid}", headers=admin, json={"title": "再改一次"})
    assert blocked.status_code == 409


def test_r4_cancel_record(client, db_mode):
    admin = _hdr(client, "school_admin01")
    rid = client.post(f"{BASE}/quality/records", headers=admin,
                      json={"recordType": "SUPERVISION", "title": "待撤销听课记录"}).json()["data"]["recordId"]
    assert client.delete(f"{BASE}/quality/records/{rid}", headers=admin).json()["data"]["cancelled"] is True
    # 撤销后不再出现在列表（软删）
    lst = client.get(f"{BASE}/quality/records", headers=admin).json()["data"]["items"]
    assert all(str(i["recordId"]) != str(rid) for i in lst)


def test_r5_create_validation(client, db_mode):
    admin = _hdr(client, "school_admin01")
    assert client.post(f"{BASE}/quality/records", headers=admin,
                       json={"recordType": "BOGUS", "title": "x"}).status_code == 400
    assert client.post(f"{BASE}/quality/records", headers=admin,
                       json={"recordType": "SUPERVISION", "title": ""}).status_code in (400, 422)


# ────────────────────── 04 教学事故：认定仅限全校范围角色 ──────────────────────

def test_r6_incident_confirm_requires_school_scope(client, db_mode):
    _seed_colleges(db_mode)
    admin = _hdr(client, "school_admin01")
    college = _hdr(client, "college_admin01")
    # college_admin01 在本院范围内可以上报教学事故（record.manage+incident.manage 均来自 academicAffairs.* 通配）
    r = client.post(f"{BASE}/quality/records", headers=college,
                    json={"recordType": "INCIDENT", "title": "监考失职事故上报",
                          "description": "考试期间监考教师离场", "category": "一般"})
    assert r.status_code == 200
    rid = r.json()["data"]["recordId"]
    assert r.json()["data"]["collegeId"]  # 自动落到 college_admin01 的本院范围
    # college_admin01（COLLEGE 范围）不可认定教学事故——仅全校范围角色可确认
    denied = client.post(f"{BASE}/quality/records/{rid}/confirm", headers=college)
    assert denied.status_code == 403
    # school_admin01（全校范围）可以认定
    ok = client.post(f"{BASE}/quality/records/{rid}/confirm", headers=admin).json()["data"]
    assert ok["status"] == "CONFIRMED"


# ────────────────────── 05/06 质量整改 + 整改跟进（同表两视角） ──────────────────────

def test_r7_rectification_full_lifecycle(client, db_mode):
    admin = _hdr(client, "school_admin01")
    # 04: 先有一条需要整改的问题记录
    rid = client.post(f"{BASE}/quality/records", headers=admin,
                      json={"recordType": "INSPECTION", "title": "毕业论文选题审查检查",
                            "conclusion": "不合格", "needRectify": True,
                            "teacherKey": "counselor01", "teacherName": "王莉"}).json()["data"]["recordId"]
    # 05: 从问题记录一键发起整改
    rect = client.post(f"{BASE}/quality/records/{rid}/rectify", headers=admin,
                       json={"title": "毕业论文选题整改", "requirement": "两周内重新提交选题材料",
                             "deadline": "2026-08-01T00:00:00"}).json()["data"]
    assert rect["status"] == "PENDING" and rect["sourceRecordId"] == str(rid) and rect["sourceType"] == "INSPECTION"
    assert len(rect["progressLog"]) == 1 and rect["progressLog"][0]["action"] == "CREATE"
    rect_id = rect["rectId"]
    # 来源记录应被标记 needRectify（已是 True，验证幂等不报错）
    src = client.get(f"{BASE}/quality/records/{rid}", headers=admin).json()["data"]
    assert src["needRectify"] is True
    # 06: 记录跟进
    p = client.post(f"{BASE}/quality/rectifications/{rect_id}/progress", headers=admin,
                    json={"note": "责任人已认领，材料准备中"}).json()["data"]
    assert p["status"] == "IN_PROGRESS" and len(p["progressLog"]) == 2
    # 提交待复核
    s = client.post(f"{BASE}/quality/rectifications/{rect_id}/submit", headers=admin,
                    json={"note": "已重新提交选题材料"}).json()["data"]
    assert s["status"] == "SUBMITTED"
    # 复核驳回（原因过短 400）
    assert client.post(f"{BASE}/quality/rectifications/{rect_id}/review", headers=admin,
                       json={"action": "REJECT", "reason": "x"}).status_code == 400
    rej = client.post(f"{BASE}/quality/rectifications/{rect_id}/review", headers=admin,
                      json={"action": "REJECT", "reason": "选题仍与已授学位方向重复"}).json()["data"]
    assert rej["status"] == "IN_PROGRESS"
    # 重新提交 + 复核通过关闭
    client.post(f"{BASE}/quality/rectifications/{rect_id}/submit", headers=admin, json={"note": "已按意见二次修改"})
    done = client.post(f"{BASE}/quality/rectifications/{rect_id}/review", headers=admin,
                       json={"action": "APPROVE"}).json()["data"]
    assert done["status"] == "CLOSED" and done["closedAt"]
    # 已关闭不可再跟进
    assert client.post(f"{BASE}/quality/rectifications/{rect_id}/progress", headers=admin,
                       json={"note": "再来一次"}).status_code == 409


def test_r8_rectification_review_requires_school_scope(client, db_mode):
    _seed_colleges(db_mode)
    admin = _hdr(client, "school_admin01")
    college = _hdr(client, "college_admin01")
    rect = client.post(f"{BASE}/quality/rectifications", headers=college,
                       json={"title": "本院整改任务", "requirement": "限期完成本院教学秩序整改"}).json()["data"]
    rect_id = rect["rectId"]
    client.post(f"{BASE}/quality/rectifications/{rect_id}/submit", headers=college, json={"note": "已整改"})
    # 学院范围角色不可复核关闭
    assert client.post(f"{BASE}/quality/rectifications/{rect_id}/review", headers=college,
                       json={"action": "APPROVE"}).status_code == 403
    # 全校范围角色可以
    ok = client.post(f"{BASE}/quality/rectifications/{rect_id}/review", headers=admin,
                     json={"action": "APPROVE"}).json()["data"]
    assert ok["status"] == "CLOSED"


def test_r9_rectification_requirement_validation(client, db_mode):
    admin = _hdr(client, "school_admin01")
    short = client.post(f"{BASE}/quality/rectifications", headers=admin,
                        json={"title": "x", "requirement": "短"})
    assert short.status_code == 400


# ────────────────────── 09 质量归档：读侧聚合 + 导出 ──────────────────────

def test_r10_archive_overview_and_export(client, db_mode):
    admin = _hdr(client, "school_admin01")
    client.post(f"{BASE}/quality/records", headers=admin,
               json={"recordType": "SUPERVISION", "title": "归档统计-听课样本"})
    client.post(f"{BASE}/quality/records", headers=admin,
               json={"recordType": "PATROL", "title": "归档统计-巡课样本"})
    client.post(f"{BASE}/quality/rectifications", headers=admin,
               json={"title": "归档统计-整改样本", "requirement": "限期完成整改内容说明"})
    ov = client.get(f"{BASE}/quality/archive/overview", headers=admin).json()["data"]
    assert ov["byType"]["SUPERVISION"]["total"] >= 1
    assert ov["byType"]["PATROL"]["total"] >= 1
    assert ov["rectification"]["total"] >= 1
    # 导出用途过短 400
    assert client.get(f"{BASE}/quality/archive/export", headers=admin,
                      params={"domain": "records", "purpose": "x"}).status_code == 400
    # 合法导出
    rx = client.get(f"{BASE}/quality/archive/export", headers=admin,
                    params={"domain": "records", "purpose": "学期质量归档核对"})
    assert rx.status_code == 200 and rx.content[:2] == b"PK"
    rr = client.get(f"{BASE}/quality/archive/export", headers=admin,
                    params={"domain": "rectifications", "purpose": "学期整改归档核对"})
    assert rr.status_code == 200 and rr.content[:2] == b"PK"
    # 非法 domain
    assert client.get(f"{BASE}/quality/archive/export", headers=admin,
                      params={"domain": "bogus", "purpose": "学期质量归档核对"}).status_code == 400


# ────────────────────── 越权与数据范围 ──────────────────────

def test_r11_student_forbidden(client, db_mode):
    stu = _stu_token("学生", "QR01")
    assert client.get(f"{BASE}/quality/records", headers=stu).status_code == 403
    assert client.post(f"{BASE}/quality/records", headers=stu,
                       json={"recordType": "PATROL", "title": "越权"}).status_code == 403
    assert client.get(f"{BASE}/quality/rectifications", headers=stu).status_code == 403
    assert client.get(f"{BASE}/quality/archive/overview", headers=stu).status_code == 403


def test_r12_cross_college_scope_denied(client, db_mode):
    ids = _seed_colleges(db_mode)
    admin = _hdr(client, "school_admin01")
    college = _hdr(client, "college_admin01")
    # 全校角色建一条属于「机械学院」的记录
    rid = client.post(f"{BASE}/quality/records", headers=admin,
                      json={"recordType": "PATROL", "title": "机械学院巡课",
                            "collegeId": str(ids["other"])}).json()["data"]["recordId"]
    # 软件学院范围的 college_admin01 查看该记录应越权拒绝
    denied = client.get(f"{BASE}/quality/records/{rid}", headers=college)
    assert denied.status_code == 403
    # 列表按 collegeId=机械学院 查询也应越权拒绝
    denied2 = client.get(f"{BASE}/quality/records", headers=college, params={"collegeId": ids["other"]})
    assert denied2.status_code == 403
    # 列表不传 collegeId 时按自身范围收敛，看不到机械学院的记录
    scoped = client.get(f"{BASE}/quality/records", headers=college).json()["data"]["items"]
    assert all(str(i["recordId"]) != str(rid) for i in scoped)
