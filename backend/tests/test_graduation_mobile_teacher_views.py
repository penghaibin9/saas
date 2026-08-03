"""毕业设计中心 · 移动端教师视图测试：中期检查 / 评阅 / 答辩安排 / 成绩复核。
全部走真库(db_mode)，验证真实处理闭环 + 范围校验（SCOPED 越权 403）+ SoD 回避。"""
from __future__ import annotations

from conftest import make_org_class

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
MOBILE = "/api/v1/mobile"
DG = "/api/v1/graduation/defense-groups"
MAIN = 1000000000000000001


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _teacher_token(real_name, role="GD_MENTOR"):
    from hashlib import sha1
    from app.core.security import create_access_token
    login_name = f"TEST-{sha1(real_name.encode('utf-8')).hexdigest()[:12]}"
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "MP", "loginName": login_name})}


def _gd_student_with_topic(graduation_client, h, no, name, advisor):
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = graduation_client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": advisor,
        "capacity": 1, "submitReview": True}).json()["data"]["id"]
    graduation_client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    graduation_client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid


def _set_stage(gd_student_id, stage):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gd_student_id))
        if stu:
            stu.stage = stage
            if stage == "MIDTERM":
                exists = db.scalars(select(GraduationMidterm).where(
                    GraduationMidterm.tenant_id == MAIN,
                    GraduationMidterm.gd_student_id == int(gd_student_id),
                    GraduationMidterm.is_deleted.is_(False),
                ).limit(1)).first()
                if exists is None:
                    db.add(GraduationMidterm(
                        tenant_id=MAIN, gd_student_id=int(gd_student_id),
                        batch_id=stu.batch_id, status="PENDING",
                    ))
            db.commit()
    finally:
        db.close()


def _items(data):
    return data.get("items", []) if isinstance(data, dict) else data


def test_midterm_check_rectify_flow_and_scope(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name, advisor = "中期检查生", "中期导师"
    gid = _gd_student_with_topic(graduation_client, h, "MT001", name, advisor)
    _set_stage(gid, "MIDTERM")
    th = _teacher_token(advisor)

    # 详情 get-or-create PENDING
    d = graduation_client.get(f"{MOBILE}/teacher/graduation/midterm/{gid}", headers=th).json()["data"]
    assert d["status"] == "PENDING"
    # 队列出现该生
    q = _items(graduation_client.get(f"{MOBILE}/teacher/graduation/midterm/queue", headers=th).json()["data"])
    assert any(str(x["gdStudentId"]) == str(gid) for x in q)
    # SCOPED 越权 403
    out = graduation_client.get(f"{MOBILE}/teacher/graduation/midterm/{gid}", headers=_teacher_token("中期范围外"))
    assert out.json()["code"] != 0

    # 教师给出 RECTIFY 结论
    chk = graduation_client.post(f"{MOBILE}/teacher/graduation/midterm/{gid}/check", headers=th,
                      json={"conclusion": "RECTIFY", "comment": "需补充中期进展与测试记录"})
    assert chk.json()["code"] == 0
    # 学生提交整改
    sh = _stu_token(name)
    rec = graduation_client.post(f"{MOBILE}/graduation/midterm/rectify", headers=sh,
                      json={"content": "已补充测试与阶段进展说明"})
    assert rec.json()["code"] == 0
    # 教师复核整改 PASS
    rr = graduation_client.post(f"{MOBILE}/teacher/graduation/midterm/{gid}/rectify-review", headers=th,
                     json={"action": "PASS"})
    assert rr.json()["code"] == 0
    assert rr.json()["data"]["status"] == "RECTIFIED_PASS"


def test_review_assign_sod_and_submit(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name, advisor = "评阅学生", "评阅导师"
    gid = _gd_student_with_topic(graduation_client, h, "RV001", name, advisor)
    ASSIGN = "/api/v1/graduation/gd-reviews/assign"

    # SoD：评阅人=指导教师 → 后端拒绝
    sod = graduation_client.post(ASSIGN, headers=h, json={"gdStudentId": str(gid), "reviewerName": advisor})
    assert sod.json()["code"] != 0
    # 分配给不同评阅人
    reviewer = "评阅王老师"
    asg = graduation_client.post(ASSIGN, headers=h, json={"gdStudentId": str(gid), "reviewerName": reviewer})
    assert asg.json()["code"] == 0
    rid = asg.json()["data"]["id"]

    # 评阅人本人看到任务，无关老师看不到
    th = _teacher_token(reviewer, role="GD_REVIEWER")
    my = _items(graduation_client.get(f"{MOBILE}/teacher/graduation/reviews/my", headers=th).json()["data"])
    assert any(str(r["id"]) == str(rid) for r in my)
    other_resp = graduation_client.get(f"{MOBILE}/teacher/graduation/reviews/my",
                            headers=_teacher_token("无关评阅老师", role="GD_REVIEWER"))
    if other_resp.status_code == 403:
        assert other_resp.json()["code"] != 0
    else:
        other = _items(other_resp.json()["data"])
        assert not any(str(r["id"]) == str(rid) for r in other)

    # 评分越界 / 意见过短 → 校验失败
    assert graduation_client.post(f"{MOBILE}/teacher/graduation/review/{rid}/submit", headers=th,
                       json={"score": 120, "opinion": "结构完整论证充分"}).json()["code"] != 0
    assert graduation_client.post(f"{MOBILE}/teacher/graduation/review/{rid}/submit", headers=th,
                       json={"score": 88, "opinion": "短"}).json()["code"] != 0
    # 冒充非评阅人提交 → 403
    assert graduation_client.post(f"{MOBILE}/teacher/graduation/review/{rid}/submit",
                       headers=_teacher_token("冒充老师", role="GD_REVIEWER"),
                       json={"score": 60, "opinion": "越权提交测试意见"}).json()["code"] != 0
    # 评阅人本人正常提交
    ok = graduation_client.post(f"{MOBILE}/teacher/graduation/review/{rid}/submit", headers=th,
                     json={"score": 88, "opinion": "结构完整，论证充分，建议通过"})
    assert ok.json()["code"] == 0


def test_defense_arrangement_readonly(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name, advisor = "答辩学生", "答辩导师"
    bid = graduation_client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "移动答辩批", "batchNo": "GD-MOB-DF", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    sid = graduation_client.post(STU, headers=h, json={"studentNo": "DF001", "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]
    tid = graduation_client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": advisor,
        "capacity": 1, "submitReview": True, "batchId": bid}).json()["data"]["id"]
    graduation_client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    graduation_client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    th = _teacher_token(advisor)

    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    db = get_sessionmaker()()
    try:
        db.get(GraduationStudent, int(gid)).stage = "FINAL_CHECK"
        db.commit()
    finally:
        db.close()

    # 建组（评委不含导师，避免回避冲突）→ 分配 → 发布
    grp = graduation_client.post(DG, headers=h, params={"batchId": bid}, json={
        "groupName": "移动答辩组", "batchId": bid, "chair": "答辩组长", "location": "M301",
        "members": ["评委甲", "评委乙"], "secretary": "答辩秘书", "defenseDate": "2026-06-01 09:00"}).json()["data"]
    gpid = grp["id"]
    graduation_client.post(f"{DG}/{gpid}/assign", headers=h, json={"studentIds": [str(gid)]})
    pub = graduation_client.post(f"{DG}/{gpid}/publish", headers=h)
    assert pub.json()["code"] == 0

    # 导师本人只读看到已发布答辩安排
    arr = _items(graduation_client.get(f"{MOBILE}/teacher/graduation/defense/arrangements", headers=th).json()["data"])
    mine = next((a for a in arr if str(a["gdStudentId"]) == str(gid)), None)
    assert mine is not None
    assert mine["published"] is True
    assert mine["groupName"] == "移动答辩组"
    assert mine["location"] == "M301"
    # 无关老师看不到
    other_resp = graduation_client.get(f"{MOBILE}/teacher/graduation/defense/arrangements", headers=_teacher_token("答辩无关"))
    if other_resp.status_code == 403:
        assert other_resp.json()["code"] != 0
    else:
        other = _items(other_resp.json()["data"])
        assert not any(str(a["gdStudentId"]) == str(gid) for a in other)


def test_grade_detail_queue_and_review(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name, advisor = "成绩学生", "成绩导师"
    gid = _gd_student_with_topic(graduation_client, h, "GR001", name, advisor)
    # 成绩证据完整性：核算前必须存在真实的定稿+已完成评阅+已确认答辩分来源记录
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationDefenseScore, GraduationFinal, GraduationReview
    db = get_sessionmaker()()
    final = GraduationFinal(
        tenant_id=MAIN, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), status="APPROVED",
        plagiarism_rate="10.0%", plagiarism_status="已检测", attachments_json=["test-file"],
    )
    db.add(final)
    db.flush()
    db.add(GraduationReview(
        tenant_id=MAIN, gd_student_id=int(gid), gd_final_id=final.id,
        reviewer_name="成绩评阅人",
        status="COMPLETED", score=80, opinion="评阅完成", reviewed_at=datetime.utcnow(),
    ))
    db.add(GraduationDefenseScore(
        tenant_id=MAIN, gd_student_id=int(gid), judge_name="成绩评委",
        score=90, absent=False, round_no=1, status="CONFIRMED", confirmed_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
    # PC 核算三段成绩（与来源记录一致）
    calc = graduation_client.post(f"/api/v1/graduation/gd-grades/{gid}/calculate", headers=h,
                       json={"advisorScore": 85, "reviewerScore": 80, "defenseScore": 90})
    assert calc.json()["code"] == 0
    th = _teacher_token(advisor, role="GD_GRADE_ADMIN")

    # 详情：三段构成
    d = graduation_client.get(f"{MOBILE}/teacher/graduation/grade/{gid}", headers=th).json()["data"]
    assert d["status"] == "CALCULATED"
    assert d["advisorScore"] == 85 and d["defenseScore"] == 90
    assert d["totalScore"] == 85  # 85*0.4 + 80*0.3 + 90*0.3
    # 队列出现待复核
    q = _items(graduation_client.get(f"{MOBILE}/teacher/graduation/grade/queue", headers=th).json()["data"])
    assert any(str(x["gdStudentId"]) == str(gid) for x in q)
    # SCOPED 越权 403
    out = graduation_client.get(f"{MOBILE}/teacher/graduation/grade/{gid}", headers=_teacher_token("成绩范围外"))
    assert out.json()["code"] != 0

    # RETURN 不填原因 → 失败；复核通过 → 成功
    assert graduation_client.post(f"{MOBILE}/teacher/graduation/grade/{gid}/review", headers=th,
                       json={"action": "RETURN", "comment": "短"}).json()["code"] != 0
    ok = graduation_client.post(f"{MOBILE}/teacher/graduation/grade/{gid}/review", headers=th,
                     json={"action": "APPROVE"})
    assert ok.json()["code"] == 0
