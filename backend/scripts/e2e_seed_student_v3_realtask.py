"""S9-RT 学生端 V3「Real Task 真实点击回放」浏览器夹具。

手册 §13 测试矩阵的 Real Task 一行要求真实点击回放这四条链路：

1. 请假退回 → 首页/消息 → 原请假对象 → 修改重提；
2. 资助带附件；
3. 消息确认回执；
4. Agenda 跳考试/课程。

本脚本只负责把这四条链路的**前置事实**放进隔离的本地 Playwright 库，真正的点击、
上传、回执和跳转由 ``e2e/specs/student-v3-real-task.spec.mjs`` 在真实浏览器里完成。

原则：**有正式 API 的一律走正式 API**（辅导员任职、请假申请/退回、资助项目与批次、
消息发布），只有考试排考座位没有对应的正式写接口，才落到 ORM 直插；那部分在下面
``_seed_exam`` 里单独说明。这样夹具本身也在验证真实写路径，而不是绕开它造数据。

命令：``seed`` / ``cleanup``。两者都幂等。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _mysql_env  # noqa: F401,E402
from sqlalchemy import select  # noqa: E402

from app.core.context import set_tenant  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402

TENANT_CODE = "sandbox-school"
ADMIN_LOGIN = ("admin2", "123456")
COUNSELOR_LOGIN = ("e2e_counselor_a", "E2eTest@2026")
STUDENT_LOGIN = ("E2E20260001", "E2eTest@2026")
STUDENT_NO = "E2E20260001"

STATE_PATH = Path(__file__).resolve().parents[1] / "tmp" / "e2e_student_v3_realtask_state.local.json"
API_BASE = os.getenv("E2E_API_BASE_URL") or "http://127.0.0.1:8000/api/v1"

# 夹具自己的标记：cleanup 只删带这些标记的数据，绝不按表清空。
MARK = "E2E-V3-REALTASK"
EXAM_BATCH_NAME = f"{MARK} 期末考试批次"
FUNDING_PROJECT_NAME = f"{MARK} 优秀学生奖学金"
ACK_TITLE = f"{MARK} 学生证年度注册确认"


# ── 安全闸：与其他浏览器夹具保持同一套判定 ──

def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing S9-RT browser fixture in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like production/staging")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("S9-RT browser fixture only accepts a local database")


# ── 正式 API 客户端 ──

class ApiError(RuntimeError):
    def __init__(self, path: str, payload: dict):
        super().__init__(f"{path} -> {payload.get('bizCode')}: {payload.get('message')}")
        self.payload = payload


def _call(path: str, token: str | None = None, method: str = "GET", body: dict | None = None) -> dict:
    request = urllib.request.Request(API_BASE + path, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    try:
        with urllib.request.urlopen(request, data, timeout=60) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read())
    if payload.get("code") != 0:
        raise ApiError(path, payload)
    return payload.get("data") or {}


def _login(login_name: str, password: str) -> str:
    data = _call("/auth/login", method="POST", body={
        "loginName": login_name, "password": password, "tenantCode": TENANT_CODE,
    })
    return str(data["accessToken"])


# ── ORM 只读/直写辅助 ──

def _session():
    return get_sessionmaker()()


def _student_facts() -> dict:
    from app.models import SchoolClass, StudentProfile, Tenant, User
    db = _session()
    try:
        tenant = db.scalars(select(Tenant).where(Tenant.tenant_code == TENANT_CODE)).first()
        if not tenant:
            raise SystemExit(f"tenant {TENANT_CODE} missing — run e2e_seed_playwright_tenants.py first")
        set_tenant(int(tenant.id))
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant.id,
            StudentProfile.student_no == STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not student:
            raise SystemExit(f"student {STUDENT_NO} missing — run e2e_bootstrap_graduation_accounts_ci.py first")
        counselor = db.scalars(select(User).where(
            User.tenant_id == tenant.id, User.login_name == COUNSELOR_LOGIN[0],
            User.is_deleted.is_(False),
        )).first()
        if not counselor:
            raise SystemExit("counselor missing — run e2e_bootstrap_affairs_counselor_ci.py first")
        school_class = db.get(SchoolClass, student.class_id) if student.class_id else None
        if not school_class:
            raise SystemExit("student has no class — counselor assignment cannot be resolved")
        return {
            "tenantId": int(tenant.id),
            "studentId": int(student.id),
            "studentName": student.real_name,
            "classId": int(school_class.id),
            "collegeId": int(student.college_id or 0) or None,
            "counselorUserId": int(counselor.id),
        }
    finally:
        db.close()


# ── 1. 请假退回（全程正式 API） ──

_LEAVE_TERMINAL = {"CLOSED", "REJECTED", "CANCELLED", "VOIDED", "WITHDRAWN"}
_RETURN_REASON = "请补充家长同意证明后重新提交"


def _in_flight_leave(tokens: dict) -> dict | None:
    """本人当前还在途的请假（服务端不允许时间重叠的重复提交，所以必须先看有没有）。"""
    mine = _call("/mobile/affairs/leave/my", tokens["student"])
    rows = [row for row in (mine.get("items") or [])
            if str(row.get("status") or "").upper() not in _LEAVE_TERMINAL]
    if not rows:
        return None
    return sorted(rows, key=lambda row: int(row["leaveId"]))[-1]


def _seed_returned_leave(facts: dict, tokens: dict) -> dict:
    """学生真实发起请假 → 辅导员真实退回。留给浏览器的是「修改重提」那一步。

    幂等做法不是"每次新建一条"——服务端本来就不允许同一学生提交时间重叠的在途请假
    （DATA_CONFLICT），那是真实业务规则，夹具不该绕开它。所以先看有没有在途的：
    已经是 RETURNED 就直接复用；还在审批中就让辅导员真实退回一次；都没有才新建。
    """
    row = _in_flight_leave(tokens)
    if row is None:
        start = datetime.now() + timedelta(days=5)
        end = start + timedelta(days=1, hours=10)
        applied = _call("/mobile/affairs/leave", tokens["student"], "POST", {
            "leaveType": "PERSONAL",
            "startTime": start.replace(microsecond=0).isoformat(),
            "endTime": end.replace(microsecond=0).isoformat(),
            "reason": f"{MARK} 回家处理家庭事务，需要请假两天",
        })
        row = {"leaveId": str(applied["id"]), "version": applied.get("version", 0),
               "status": str(applied.get("status") or "")}

    leave_id = str(row["leaveId"])
    if str(row.get("status") or "").upper() != "RETURNED":
        returned = _call(f"/mobile/teacher/affairs/leaves/{leave_id}/return", tokens["counselor"],
                         "POST", {"reason": _RETURN_REASON, "version": int(row.get("version") or 0)})
        version = int(returned.get("version") or 0)
        status = str(returned.get("status") or "")
    else:
        version = int(row.get("version") or 0)
        status = "RETURNED"

    return {
        "leaveId": leave_id,
        "version": version,
        "status": status,
        "returnReason": _RETURN_REASON,
    }


# ── 2. 资助带附件（项目+批次走正式 API，申请与附件由浏览器完成） ──

def _seed_funding_batch(facts: dict, tokens: dict) -> dict:
    """资助项目与批次是学校侧**配置**，不是本次回放产生的业务数据。

    所以这里只保证"存在且在申请期内"，重复执行复用同一个项目/批次；cleanup 也不删它们
    ——删掉会让历史申请变成孤儿。真正由回放产生的资助申请与附件属于业务数据，
    由浏览器用例自己提交、并在断言后回读 server truth。
    """
    admin = tokens["admin"]
    existing = _call("/student-affairs/funding/projects?pageSize=200", admin)
    project_id = next(
        (str(row["projectId"]) for row in (existing.get("items") or [])
         if str(row.get("projectName") or "") == FUNDING_PROJECT_NAME),
        None,
    )
    if not project_id:
        # 用奖学金而不是助学金：助学金（GRANT）的资格硬校验要求学生已通过困难认定，
        # 那是另一条业务链；本回放要证的是"带附件申请能不能真的提交并绑上"，
        # 不该顺带把困难认定也造成假数据。奖学金的资格事实（学籍正常、无有效处分、
        # 无不及格）这个 E2E 学生天然满足。
        project = _call("/student-affairs/funding/projects", admin, "POST", {
            "projectName": FUNDING_PROJECT_NAME,
            "projectType": "SCHOLARSHIP",
            "amount": "2000.00",
            "quota": 50,
        })
        project_id = str(project["projectId"])

    batches = _call(f"/student-affairs/funding/batches?projectId={project_id}&pageSize=200", admin)
    open_batch = next((row for row in (batches.get("items") or [])
                       if str(row.get("status") or "").upper() in {"OPEN", "PUBLISHED", "APPLYING"}), None)
    if open_batch:
        return {"projectId": project_id, "batchId": str(open_batch["batchId"])}

    today = date.today()
    batch = _call("/student-affairs/funding/batches", admin, "POST", {
        "projectId": project_id,
        "schoolYear": f"{today.year}-{today.year + 1}",
        "applyStart": (today - timedelta(days=1)).isoformat(),
        "applyEnd": (today + timedelta(days=30)).isoformat(),
        "publicityDays": 5,
        "quota": 50,
        "publish": True,
    })
    return {"projectId": project_id, "batchId": str(batch["batchId"])}



def _clear_in_flight_funding(facts: dict, batch_id: str) -> None:
    """清掉本学生在本批次的在途申请，让浏览器用例每次都能真的提交一笔。

    服务端禁止同批次重复在途申请（真实业务规则），所以要么复用要么清掉；这里选清掉，
    因为被测的正是"带附件提交"这个动作本身。只删本夹具批次下本人的申请及其附件绑定，
    不碰其他批次、其他学生。
    """
    from app.models import FundingApplication
    from app.models.file import FileBinding
    db = _session()
    try:
        set_tenant(facts["tenantId"])
        rows = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == facts["tenantId"],
            FundingApplication.batch_id == int(batch_id),
            FundingApplication.student_id == facts["studentId"],
        )).all()
        for row in rows:
            for binding in db.scalars(select(FileBinding).where(
                FileBinding.tenant_id == facts["tenantId"],
                FileBinding.biz_type == "FUNDING",
                FileBinding.biz_id == str(row.id),
            )).all():
                db.delete(binding)
            db.delete(row)
        db.commit()
    finally:
        db.close()

# ── 3. 需回执的消息（正式消息中心发布） ──

def _past_non_quiet_delivery_slot() -> str:
    """返回一个已经到期、且按 UTC+8 不落在 22:00–07:00 静默窗的正式预约时间。

    真实产品必须保留静默规则；浏览器回放只需要消除墙钟时间依赖。把预约时间固定到
    “前一天本地 12:00”，服务端仍完整执行 scheduled/quiet-hours 生产逻辑，但因为该时间
    已到期且不在静默窗，会进入正常投递而不是被当前凌晨时刻再次顺延。
    """
    local_now = datetime.utcnow() + timedelta(hours=8)
    local_slot = (local_now - timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    return (local_slot - timedelta(hours=8)).isoformat()


def _seed_ack_message(facts: dict, tokens: dict) -> dict:
    """走完整的正式发布流程：草稿 → 受众预览 → 发布 → 正式 delivery worker。

    publish 需要预览产生的 previewToken + audienceFingerprint + version，这是消息中心
    防"受众漂移后照发"的真实约束，夹具照走，不绕开。回放可能在 22:00–07:00 静默窗
    执行，因此用一个已经到期的非静默预约时间消除墙钟依赖；生产静默规则本身完全不改。
    """
    admin = tokens["admin"]
    audiences = [{"type": "CLASS", "includeOrExclude": "INCLUDE",
                  "targetIds": [facts["classId"]], "includeChildren": True}]
    draft = _call("/admin/message-campaigns", admin, "POST", {
        "title": ACK_TITLE,
        "contentPlain": "请在本周内确认学生证年度注册信息无误，确认后即完成回执。",
        "summary": "学生证年度注册确认",
        "category": "ANNOUNCEMENT",
        "priority": "IMPORTANT",
        "requireAck": True,
        "publishMode": "SCHEDULED",
        "scheduledAt": _past_non_quiet_delivery_slot(),
        "audiences": audiences,
        "channels": ["IN_APP"],
        "idempotencyKey": f"{MARK}-ack-v2-{facts['classId']}",
    })
    campaign_id = str(draft["campaignId"])
    if str(draft.get("status") or "").upper() == "DRAFT":
        preview = _call("/admin/message-campaigns/audience-preview", admin, "POST",
                        {"audiences": audiences})
        if int(preview.get("recipientCount") or 0) <= 0:
            raise SystemExit("S9-RT ack audience resolved to zero recipients")
        published = _call(f"/admin/message-campaigns/{campaign_id}/publish", admin, "POST", {
            "previewToken": preview["previewToken"],
            "audienceFingerprint": preview["audienceFingerprint"],
            "version": int(draft.get("version") or 0),
            "requestId": f"{MARK}-ack-publish-{campaign_id}",
        })
        if int(published.get("recipientCount") or 0) <= 0:
            raise SystemExit("S9-RT ack publish accepted zero recipients")
        if str(published.get("status") or "").upper() == "SCHEDULED":
            raise SystemExit("S9-RT ack campaign unexpectedly remained scheduled")

    # HTTP publish 只负责受理；用正式 delivery worker 确定性排空当前租户作业，再以学生
    # 收件箱 server truth 作为 seed 成功条件。这样不依赖 workflow 里 worker 的抢占时序。
    from app.services import message_delivery_service as delivery_svc
    set_tenant(facts["tenantId"])
    for _ in range(20):
        delivery_svc.claim_and_process_delivery_jobs(limit=40, worker_id="e2e-s9-rt")
        inbox = _call("/student-mini/messages?page=1&pageSize=50", tokens["student"])
        item = next(
            (row for row in (inbox.get("items") or []) if row.get("title") == ACK_TITLE),
            None,
        )
        if item:
            return {
                "campaignId": campaign_id,
                "messageId": str(item.get("messageId") or ""),
                "title": ACK_TITLE,
            }
    raise SystemExit("S9-RT ack message was not materialized into the student inbox")


# ── 4. Agenda 考试（ORM 直插，原因见下） ──

def _seed_exam(facts: dict) -> dict:
    """排考座位没有正式写接口，只能直插。

    教务的考试编排在真实学校里是教务处在 PC 端排的，仓库当前没有暴露"给某个学生排一个
    考场座位"的正式写 API（只有查询与考务流程内部服务）。所以这四条链路里只有这一条
    用 ORM 直插，且严格照抢 Agenda 投影真正消费的四张表与状态：
    AaExamBatch(PUBLISHED) → AaExamCourse(CONFIRMED) → AaExamRoom → AaExamRoomStudent。
    Agenda 读的是这条链，不是本夹具自造的字段。
    """
    from app.models import AaExamBatch, AaExamCourse, AaExamRoom, AaExamRoomStudent
    db = _session()
    try:
        set_tenant(facts["tenantId"])
        exam_day = date.today() + timedelta(days=2)
        batch = db.scalars(select(AaExamBatch).where(
            AaExamBatch.tenant_id == facts["tenantId"],
            AaExamBatch.batch_name == EXAM_BATCH_NAME,
            AaExamBatch.is_deleted.is_(False),
        )).first()
        if not batch:
            batch = AaExamBatch(tenant_id=facts["tenantId"], batch_name=EXAM_BATCH_NAME,
                                exam_type="FINAL", status="PUBLISHED", published_at=datetime.now())
            db.add(batch)
            db.flush()

        course = db.scalars(select(AaExamCourse).where(
            AaExamCourse.tenant_id == facts["tenantId"],
            AaExamCourse.batch_id == batch.id,
            AaExamCourse.is_deleted.is_(False),
        )).first()
        if not course:
            course = AaExamCourse(tenant_id=facts["tenantId"], batch_id=batch.id,
                                  course_name=f"{MARK} 数据结构", class_id=facts["classId"],
                                  college_id=facts["collegeId"], status="CONFIRMED",
                                  exam_date=exam_day.isoformat(), start_time="09:00",
                                  end_time="11:00", duration_minutes=120, expected_students=1)
            db.add(course)
            db.flush()
        else:
            course.exam_date = exam_day.isoformat()
            course.status = "CONFIRMED"

        room = db.scalars(select(AaExamRoom).where(
            AaExamRoom.tenant_id == facts["tenantId"],
            AaExamRoom.exam_course_id == course.id,
            AaExamRoom.is_deleted.is_(False),
        )).first()
        if not room:
            room = AaExamRoom(tenant_id=facts["tenantId"], exam_course_id=course.id, room_seq=1,
                              classroom_text=f"{MARK} 教学楼A-301", capacity=60, planned_count=1,
                              seat_mode="SEQUENTIAL", source="MANUAL", status="CONFIRMED")
            db.add(room)
            db.flush()

        seat = db.scalars(select(AaExamRoomStudent).where(
            AaExamRoomStudent.tenant_id == facts["tenantId"],
            AaExamRoomStudent.exam_course_id == course.id,
            AaExamRoomStudent.student_id == facts["studentId"],
            AaExamRoomStudent.is_deleted.is_(False),
        )).first()
        if not seat:
            db.add(AaExamRoomStudent(tenant_id=facts["tenantId"], exam_room_id=room.id,
                                     exam_course_id=course.id, student_id=facts["studentId"],
                                     student_no=STUDENT_NO, student_name=facts["studentName"],
                                     seat_no=1, attendance_status="NORMAL"))
        db.commit()
        return {
            "batchId": int(batch.id), "examCourseId": int(course.id), "examRoomId": int(room.id),
            "examDate": exam_day.isoformat(), "courseName": f"{MARK} 数据结构",
            "classroom": f"{MARK} 教学楼A-301",
        }
    finally:
        db.close()


# ── 辅导员任职：请假审批链的前置事实（正式 API） ──

def _ensure_counselor_assignment(facts: dict, tokens: dict) -> dict:
    admin = tokens["admin"]
    ledger = _call(f"/student-affairs/counselor-assignments?classId={facts['classId']}&pageSize=100", admin)
    for row in ledger.get("items") or []:
        if (str(row.get("userId")) == str(facts["counselorUserId"])
                and str(row.get("status") or "").upper() == "ACTIVE"):
            return {"assignmentId": str(row["id"]), "created": False}
    created = _call("/student-affairs/counselor-assignments", admin, "POST", {
        "classId": str(facts["classId"]),
        "userId": str(facts["counselorUserId"]),
        "dutyType": "PRIMARY",
        "effectiveFrom": (date.today() - timedelta(days=30)).isoformat() + "T00:00:00",
        "reason": f"{MARK} 真实点击回放需要固定审批人",
    })
    return {"assignmentId": str(created["id"]), "created": True}


def seed() -> dict:
    facts = _student_facts()
    tokens = {
        "admin": _login(*ADMIN_LOGIN),
        "counselor": _login(*COUNSELOR_LOGIN),
        "student": _login(*STUDENT_LOGIN),
    }
    funding = _seed_funding_batch(facts, tokens)
    _clear_in_flight_funding(facts, funding["batchId"])
    state = {
        "mark": MARK,
        "tenantCode": TENANT_CODE,
        "student": {"loginName": STUDENT_LOGIN[0], "studentNo": STUDENT_NO,
                    "studentId": facts["studentId"], "name": facts["studentName"]},
        "classId": facts["classId"],
        "counselor": _ensure_counselor_assignment(facts, tokens),
        "leave": _seed_returned_leave(facts, tokens),
        "funding": funding,
        "ackMessage": _seed_ack_message(facts, tokens),
        "exam": _seed_exam(facts),
        "seededAt": datetime.now().isoformat(timespec="seconds"),
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[s9-rt] seeded leave={state['leave']['leaveId']} exam={state['exam']['examCourseId']} "
          f"batch={state['funding']['batchId']} campaign={state['ackMessage']['campaignId']}")
    return state


def cleanup() -> None:
    """只删本夹具打了 MARK 的数据；不按表清空，也不碰其他夹具的账号与组织。"""
    if not STATE_PATH.exists():
        print("[s9-rt] nothing to clean")
        return
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    from app.models import (AaExamBatch, AaExamCourse, AaExamRoom, AaExamRoomStudent,
                            CsLeave, MessageCampaign, UnifiedMessage, UnifiedTodo)
    db = _session()
    try:
        tenant_id = _student_facts()["tenantId"]
        set_tenant(tenant_id)
        exam = state.get("exam") or {}
        for model, column, value in (
            (AaExamRoomStudent, "exam_course_id", exam.get("examCourseId")),
            (AaExamRoom, "exam_course_id", exam.get("examCourseId")),
            (AaExamCourse, "batch_id", exam.get("batchId")),
            (AaExamBatch, "id", exam.get("batchId")),
        ):
            if not value:
                continue
            for row in db.scalars(select(model).where(
                model.tenant_id == tenant_id, getattr(model, column) == int(value)
            )).all():
                db.delete(row)

        leave_id = (state.get("leave") or {}).get("leaveId")
        if leave_id:
            for row in db.scalars(select(UnifiedTodo).where(
                UnifiedTodo.tenant_id == tenant_id,
                UnifiedTodo.source_module == "student-affairs",
                UnifiedTodo.source_biz_id == int(leave_id),
            )).all():
                db.delete(row)
            leave = db.get(CsLeave, int(leave_id))
            if leave is not None and leave.tenant_id == tenant_id:
                db.delete(leave)

        batch_id = (state.get("funding") or {}).get("batchId")
        if batch_id:
            from app.models import FundingApplication
            from app.models.file import FileBinding
            for row in db.scalars(select(FundingApplication).where(
                FundingApplication.tenant_id == tenant_id,
                FundingApplication.batch_id == int(batch_id),
                FundingApplication.student_id == int(state["student"]["studentId"]),
            )).all():
                for binding in db.scalars(select(FileBinding).where(
                    FileBinding.tenant_id == tenant_id,
                    FileBinding.biz_type == "FUNDING",
                    FileBinding.biz_id == str(row.id),
                )).all():
                    db.delete(binding)
                db.delete(row)

        campaign_id = (state.get("ackMessage") or {}).get("campaignId")
        if campaign_id:
            for row in db.scalars(select(UnifiedMessage).where(
                UnifiedMessage.tenant_id == tenant_id,
                UnifiedMessage.campaign_id == int(campaign_id),
            )).all():
                db.delete(row)
            campaign = db.get(MessageCampaign, int(campaign_id))
            if campaign is not None and campaign.tenant_id == tenant_id:
                db.delete(campaign)
        db.commit()
    finally:
        db.close()
    STATE_PATH.unlink(missing_ok=True)
    print("[s9-rt] cleaned")


def main() -> int:
    assert_safe_target()
    command = (sys.argv[1] if len(sys.argv) > 1 else "seed").strip().lower()
    if command == "seed":
        seed()
    elif command == "cleanup":
        cleanup()
    else:
        raise SystemExit(f"unknown command: {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
