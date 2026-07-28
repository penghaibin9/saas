"""学生 PC 门户 · 学工事务（第4期）测试（MySQL 真库 via db_mode）：

学工自视图(总览/请假/奖助/资助/违纪) / 通用事务申请(校验) / 打印回执 / 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/affairs"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M", grade="2023",
                          current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def test_affairs_views(client, db_mode):
    _seed("SA-001", "学工一")
    h = _stu_token("学工一", "SA-001")
    for path in ("/overview", "/leave", "/funding", "/aid", "/discipline"):
        assert client.get(f"{PORTAL}{path}", headers=h).json()["code"] == 0


def test_service_apply(client, db_mode):
    _seed("SA-002", "学工二")
    h = _stu_token("学工二", "SA-002")
    ok = client.post(f"{PORTAL}/service-apply", headers=h,
                     json={"serviceKey": "CONSULT", "reason": "咨询关于奖学金评定的相关问题"}).json()
    assert ok["code"] == 0
    # 事由过短拒绝
    assert client.post(f"{PORTAL}/service-apply", headers=h,
                       json={"serviceKey": "CONSULT", "reason": "短"}).json()["code"] != 0


def test_print(client, db_mode):
    _seed("SA-003", "学工三")
    h = _stu_token("学工三", "SA-003")
    r = client.post(f"{PORTAL}/print", headers=h,
                    json={"bizType": "LEAVE", "docName": "请假条"}).json()
    assert r["code"] == 0 and r["data"]["watermark"] == "学工三"


def test_psy_and_applications(client, db_mode):
    _seed("SA-010", "学工十")
    h = _stu_token("学工十", "SA-010")
    assert client.get(f"{PORTAL}/psy/questions", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/psy/history", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/applications", headers=h).json()["code"] == 0
    # 心理测评未作答拒绝
    assert client.post(f"{PORTAL}/psy/submit", headers=h, json={"answers": []}).json()["code"] != 0


def _seed_effective_case(no):
    """为学生（按学号）建一条已生效处分，返回 (caseId, studentId)，供本人申诉入口测试。"""
    from app.db.session import get_sessionmaker
    from app.models import DisciplineCase, StudentProfile
    from sqlalchemy import select
    db = get_sessionmaker()()
    sid = db.scalars(select(StudentProfile.id).where(
        StudentProfile.tenant_id == TID, StudentProfile.student_no == no)).first()
    c = DisciplineCase(tenant_id=TID, student_id=sid, disc_type="WARNING",
                       reason="旷课", status="EFFECTIVE")
    db.add(c); db.flush()
    cid = c.id
    db.commit(); db.close()
    return cid, sid


def test_discipline_appeal(client, db_mode):
    """修复后契约：申诉必须带本人生效处分的 caseId，且写入真实 DisciplineAppeal 表（老师端可见）。"""
    from affairs_contract_test_support import ensure_role_user

    _seed("SA-011", "学工十一")
    case_id, sid = _seed_effective_case("SA-011")
    # 正式申诉工作流必须有真实学工处受理人，测试显式准备控制面角色关系。
    ensure_role_user("STUDENT_AFFAIRS_ADMIN")
    h = _stu_token("学工十一", "SA-011")
    ok = client.post(f"{PORTAL}/discipline/appeal", headers=h,
                     json={"caseId": str(case_id),
                           "reason": "对处分认定的事实有异议，特此书面申辩说明。"}).json()
    assert ok["code"] == 0, ok
    # 申诉真的落到老师端审核队列所读的 DisciplineAppeal 表（闭环验证）
    from app.db.session import get_sessionmaker
    from app.models import DisciplineAppeal
    from sqlalchemy import select
    db = get_sessionmaker()()
    appeal = db.scalars(select(DisciplineAppeal).where(
        DisciplineAppeal.tenant_id == TID, DisciplineAppeal.case_id == case_id)).first()
    db.close()
    assert appeal is not None and appeal.student_id == sid and appeal.status == "SUBMITTED"
    # 负例：缺 caseId → 校验失败；理由过短 → 校验失败
    assert client.post(f"{PORTAL}/discipline/appeal", headers=h,
                       json={"reason": "对处分有异议需要申辩"}).json()["code"] != 0
    assert client.post(f"{PORTAL}/discipline/appeal", headers=h,
                       json={"caseId": str(case_id), "reason": "短"}).json()["code"] != 0


def test_funding_aid_apply_guards_and_self(client, db_mode):
    _seed("SA-020", "学工廿")
    h = _stu_token("学工廿", "SA-020")
    # 缺 batchId / 未勾选承诺 → 校验失败
    assert client.post(f"{PORTAL}/funding/apply", headers=h,
                       json={"confirm": True}).json()["code"] != 0
    assert client.post(f"{PORTAL}/funding/apply", headers=h,
                       json={"batchId": "1"}).json()["code"] != 0
    # 请求体满足正式长文本合同，但批次不存在 → 到达底层返回不存在。
    r = client.post(f"{PORTAL}/funding/apply", headers=h,
                    json={"batchId": "999999", "confirm": True,
                          "statement": "家庭经济困难情况说明满足申请材料字数要求"}).json()
    assert r["code"] == 404001
    # 困难认定同理(到达真实服务并被业务拒绝:等级非法或批次不存在,均证明已强制本人+落到真实服务)
    assert client.post(f"{PORTAL}/aid/apply", headers=h,
                       json={"batchId": "999999", "applyLevel": "一般困难", "confirm": True,
                             "statement": "家庭经济困难情况说明满足十字要求"}).json()["code"] != 0


def test_activities_view(client, db_mode):
    _seed("SA-021", "学工廿一")
    h = _stu_token("学工廿一", "SA-021")
    assert client.get(f"{PORTAL}/activities", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/activities/my", headers=h).json()["code"] == 0


def test_leave_visible_via_old_cs_student_id_link(client, db_mode):
    """t_cs_leave 双状态列并行(P0 §4.2 集成①)回归：老 campus-service 提交只挂
    cs_student_id(student_id/affairs_status 均为空)，此前 /portal/affairs/leave 和
    /portal/affairs/applications 都只认 student_id/cs.id 单一条件，看不到这类记录——
    学生自己提交的请假在「我的档案·我的申请」能看到，切到「学工事务·请假销假」却是空的。"""
    from app.db.session import get_sessionmaker
    from app.models import CsLeave, CsServiceStudent
    _seed("SA-030", "学工卅")
    db = get_sessionmaker()()
    cs = CsServiceStudent(tenant_id=TID, student_no="SA-030", name="学工卅")
    db.add(cs); db.flush()
    db.add(CsLeave(tenant_id=TID, cs_student_id=cs.id, leave_type="SICK",
                   status="PENDING_REVIEW", reason="老链路请假记录"))
    db.commit(); db.close()
    h = _stu_token("学工卅", "SA-030")
    leave = client.get(f"{PORTAL}/leave", headers=h).json()
    assert leave["code"] == 0 and len(leave["data"]["items"]) == 1
    assert leave["data"]["items"][0]["status"] == "PENDING_REVIEW"
    apps = client.get(f"{PORTAL}/applications", headers=h).json()["data"]["applications"]
    assert any(a["sourceType"] == "LEAVE" and a["status"] == "PENDING_REVIEW" for a in apps)


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/leave", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/funding", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/service-apply", headers=admin,
                       json={"serviceKey": "CONSULT", "reason": "咨询相关问题事项"}).json()["code"] == 403001
    assert client.post(f"{PORTAL}/print", headers=admin, json={}).json()["code"] == 403001
    assert client.get(f"{PORTAL}/psy/questions", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/applications", headers=admin).json()["code"] == 403001
    # 使用完整合法请求体，确保请求进入身份门禁而不是先被字段校验拦截。
    assert client.post(f"{PORTAL}/funding/apply", headers=admin,
                       json={"batchId": "1", "confirm": True,
                             "statement": "家庭经济困难情况说明满足申请材料字数要求"}).json()["code"] == 403001
    assert client.post(f"{PORTAL}/aid/apply", headers=admin,
                       json={"batchId": "1", "applyLevel": "一般困难", "confirm": True,
                             "statement": "x" * 20}).json()["code"] == 403001


def test_portal_leave_resubmit_self_only(client, db_mode):
    """SA-BUG-001 回归：学生 PC 门户可重交本人被退回请假；他人/非 RETURNED 拒绝。"""
    from datetime import datetime

    from app.db.session import get_sessionmaker
    from app.models import CsLeave, SchoolClass, StudentProfile, User
    from app.services import affairs_leave_service as leave_svc

    db = get_sessionmaker()()
    counselor = User(tenant_id=TID, login_name="portal-resubmit-counselor", real_name="重交回归辅导员",
                     password_hash="x", user_type="TEACHER", status="ACTIVE")
    db.add(counselor); db.flush()
    cls = SchoolClass(tenant_id=TID, major_id=1, class_name="门户重交回归班", counselor_id=counselor.id)
    db.add(cls); db.flush()
    stu = StudentProfile(tenant_id=TID, student_no="SA-RESUB-01", real_name="重交生",
                         gender="M", grade="2024", current_stage="ENROLLED",
                         student_status="NORMAL", status="ACTIVE", class_id=cls.id)
    other = StudentProfile(tenant_id=TID, student_no="SA-RESUB-02", real_name="他人",
                           gender="F", grade="2024", current_stage="ENROLLED",
                           student_status="NORMAL", status="ACTIVE", class_id=cls.id)
    db.add(stu); db.add(other); db.flush()
    leave = CsLeave(
        tenant_id=TID, cs_student_id=0, student_id=stu.id, leave_type="PERSONAL",
        start_time=datetime(2026, 8, 1), end_time=datetime(2026, 8, 2),
        days=1, reason="门户重交回归初始事由足够字数",
        affairs_status="RETURNED", status="RETURNED",
        return_reason="材料不齐请补充说明",
    )
    db.add(leave); db.commit()
    db.refresh(leave)
    leave_id = leave.id
    leave_version = leave.version
    db.close()

    h = _stu_token("重交生", "SA-RESUB-01")
    ok = client.post(f"{PORTAL}/leave/{leave_id}/resubmit", headers=h,
                     json={"reason": "已按退回意见补充行程说明材料", "version": leave_version}).json()
    assert ok["code"] == 0
    assert ok["data"]["affairsStatus"] == "COUNSELOR_REVIEW"

    # 再次重交应失败（已不在 RETURNED）
    again = client.post(f"{PORTAL}/leave/{leave_id}/resubmit", headers=h,
                       json={"reason": "再次重交不应成功", "version": leave_version + 1}).json()
    assert again["code"] != 0

    # 他人不可重交
    leave_svc.return_leave  # keep import used for clarity of domain
    db = get_sessionmaker()()
    row = db.get(CsLeave, leave_id)
    row.affairs_status = "RETURNED"
    row.status = "RETURNED"
    db.commit(); db.close()
    other_h = _stu_token("他人", "SA-RESUB-02")
    deny = client.post(f"{PORTAL}/leave/{leave_id}/resubmit", headers=other_h,
                       json={"reason": "他人冒充重交应当失败", "version": leave_version + 1}).json()
    assert deny["code"] in (403001, 403002) or deny.get("bizCode") in ("NO_PERMISSION", "NO_DATA_SCOPE")
