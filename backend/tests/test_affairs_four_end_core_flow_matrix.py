"""学工四端核心业务流程路由矩阵。

目标不是重复业务状态机单测，而是机械证明学生 PC、学生小程序、教师小程序与
PC 核心服务之间的关键入口全部真实注册，方法一致，未出现前端有按钮但后端无路由。
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _route_matrix(app) -> set[tuple[str, str]]:
    rows: set[tuple[str, str]] = set()
    for route in app.routes:
        path = str(getattr(route, "path", "") or "")
        for method in set(getattr(route, "methods", set()) or set()):
            method = str(method).upper()
            if method not in ("HEAD", "OPTIONS"):
                rows.add((method, path))
    return rows


def test_four_end_core_flow_routes_are_all_registered(client, db_mode):
    routes = _route_matrix(client.app)
    expected = {
        # 学生请假：申请由既有 campus-service 入口承担；以下覆盖本人视图、退回重提、销假续假。
        ("GET", "/api/v1/mobile/affairs/leave/my"),
        ("GET", "/api/v1/mobile/affairs/leave/{leave_id}/editable"),
        ("PUT", "/api/v1/mobile/affairs/leave/{leave_id}/returned"),
        ("POST", "/api/v1/mobile/affairs/leave/{leave_id}/resubmit"),
        ("POST", "/api/v1/mobile/affairs/leave/{leave_id}/cancel"),
        ("POST", "/api/v1/mobile/affairs/leave/{leave_id}/extension"),
        # 教师请假全链。
        ("GET", "/api/v1/mobile/teacher/affairs/leaves/pending"),
        ("GET", "/api/v1/mobile/teacher/affairs/leaves/followup"),
        ("GET", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}"),
        ("POST", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}/approve"),
        ("POST", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}/reject"),
        ("POST", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}/return"),
        ("POST", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}/cancel-confirm"),
        ("POST", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}/proxy-cancel"),
        ("POST", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}/extension-approve"),
        ("POST", "/api/v1/mobile/teacher/affairs/leaves/{leave_id}/overdue-handle"),
        # 困难认定与奖助：学生申请/退回/异议，教师待办/详情/审批。
        ("GET", "/api/v1/mobile/affairs/aid/my"),
        ("POST", "/api/v1/mobile/affairs/aid/apply"),
        ("GET", "/api/v1/mobile/affairs/aid/{apply_id}/editable"),
        ("PUT", "/api/v1/mobile/affairs/aid/{apply_id}/returned"),
        ("POST", "/api/v1/mobile/affairs/aid/{apply_id}/resubmit"),
        ("POST", "/api/v1/mobile/affairs/aid/objection"),
        ("GET", "/api/v1/mobile/teacher/affairs/aid/pending"),
        ("GET", "/api/v1/mobile/teacher/affairs/aid/{apply_id}"),
        ("POST", "/api/v1/mobile/teacher/affairs/aid/{apply_id}/review"),
        ("GET", "/api/v1/mobile/affairs/funding/my"),
        ("POST", "/api/v1/mobile/affairs/funding/apply"),
        ("GET", "/api/v1/mobile/affairs/funding/{app_id}/editable"),
        ("PUT", "/api/v1/mobile/affairs/funding/{app_id}/returned"),
        ("POST", "/api/v1/mobile/affairs/funding/{app_id}/resubmit"),
        ("POST", "/api/v1/mobile/affairs/funding/appeal"),
        ("GET", "/api/v1/mobile/teacher/affairs/funding/pending"),
        ("GET", "/api/v1/mobile/teacher/affairs/funding/{app_id}"),
        ("POST", "/api/v1/mobile/teacher/affairs/funding/{app_id}/review"),
        # 统一申诉待办、复核、补偿。
        ("GET", "/api/v1/mobile/teacher/affairs/appeals/{kind}"),
        ("POST", "/api/v1/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review"),
        ("POST", "/api/v1/mobile/teacher/affairs/appeals/repair"),
        # 宿舍首次入住与正式调宿。
        ("GET", "/api/v1/mobile/affairs/dorm/my"),
        ("POST", "/api/v1/mobile/affairs/dorm/beds/{bed_id}/self-select"),
        ("GET", "/api/v1/mobile/affairs/dorm/transfer-options"),
        ("POST", "/api/v1/mobile/affairs/dorm/transfers"),
        ("GET", "/api/v1/mobile/affairs/dorm/transfers/my"),
        ("GET", "/api/v1/mobile/teacher/affairs/dorm/pending"),
        ("POST", "/api/v1/mobile/teacher/affairs/dorm/transfers/{transfer_id}/review"),
        ("POST", "/api/v1/mobile/teacher/affairs/dorm/exceptions/{exception_id}/handle"),
        # 活动报名、可信签到、成绩单与积分申诉。
        ("GET", "/api/v1/mobile/affairs/my-activities"),
        ("POST", "/api/v1/mobile/affairs/activities/{activity_id}/enroll"),
        ("POST", "/api/v1/mobile/affairs/activities/{activity_id}/secure-checkin"),
        ("GET", "/api/v1/mobile/affairs/second-class/report"),
        ("POST", "/api/v1/mobile/affairs/second-class/appeals"),
        ("GET", "/api/v1/mobile/affairs/second-class/appeals/my"),
        ("GET", "/api/v1/mobile/teacher/affairs/activities/ongoing"),
        ("GET", "/api/v1/mobile/teacher/affairs/activities/{activity_id}/checkin-token"),
        # 心理：统计与个体明细分权，处置继续走同一核心服务。
        ("GET", "/api/v1/mobile/teacher/mental-stats"),
        ("GET", "/api/v1/mobile/teacher/mental"),
        ("GET", "/api/v1/mobile/teacher/mental/{referral_id}"),
        ("POST", "/api/v1/mobile/teacher/mental/{referral_id}/follow"),
        ("POST", "/api/v1/mobile/teacher/mental/{referral_id}/escalate"),
        ("POST", "/api/v1/mobile/teacher/mental/{referral_id}/close"),
        # 谈心谈话。
        ("GET", "/api/v1/mobile/teacher/talk"),
        ("GET", "/api/v1/mobile/teacher/talk/{talk_id}"),
        ("POST", "/api/v1/mobile/teacher/talk/{talk_id}/record"),
        ("POST", "/api/v1/mobile/teacher/talk/{talk_id}/follow-up"),
    }
    missing = sorted(expected - routes)
    assert missing == []


def test_student_pc_and_miniapp_use_same_core_contract_paths():
    portal = (ROOT / "student-portal/src/services/affairsFourEndApi.js").read_text(encoding="utf-8")
    mini = (ROOT / "miniapp/src/services/affairsContractApi.js").read_text(encoding="utf-8")
    shared_fragments = (
        "/mobile/affairs/leave/",
        "/mobile/affairs/aid/",
        "/mobile/affairs/funding/",
        "/mobile/affairs/dorm/transfer-options",
        "/mobile/affairs/dorm/transfers",
        "/mobile/affairs/second-class/report",
    )
    for fragment in shared_fragments:
        assert fragment in portal
        assert fragment in mini


def test_all_teacher_mobile_state_changes_send_visible_version():
    source = (ROOT / "miniapp/src/services/affairsContractApi.js").read_text(encoding="utf-8")
    state_change_names = (
        "approveLeave", "rejectLeave", "returnLeave", "confirmCancelLeave",
        "proxyCancelLeave", "reviewLeaveExtension", "handleLeaveOverdue",
        "reviewAid", "reviewFunding", "reviewDiscipline", "processRisk", "closeRisk",
        "reviewDormTransfer", "handleDormException", "recordTalk", "followTalk",
        "followMental", "escalateMental", "closeMental",
    )
    for name in state_change_names:
        start = source.index(f"{name}:")
        end = source.find("\n  ", start + len(name) + 1)
        block = source[start:] if end < 0 else source[start:end]
        assert "version" in block, f"{name} 未携带可见 version"
