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
        ("POST", "/api/v1/portal/affairs/leave"),
        ("POST", "/api/v1/mobile/affairs/leave"),
        ("GET", "/api/v1/mobile/affairs/leave/my"),
        ("GET", "/api/v1/mobile/affairs/leave/{leave_id}/editable"),
        ("PUT", "/api/v1/mobile/affairs/leave/{leave_id}/returned"),
        ("POST", "/api/v1/mobile/affairs/leave/{leave_id}/resubmit"),
        ("POST", "/api/v1/mobile/affairs/leave/{leave_id}/cancel"),
        ("POST", "/api/v1/mobile/affairs/leave/{leave_id}/extension"),
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
        ("GET", "/api/v1/mobile/teacher/affairs/appeals/{kind}"),
        ("POST", "/api/v1/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review"),
        ("POST", "/api/v1/mobile/teacher/affairs/appeals/repair"),
        ("GET", "/api/v1/mobile/affairs/dorm/my"),
        ("POST", "/api/v1/mobile/affairs/dorm/beds/{bed_id}/self-select"),
        ("GET", "/api/v1/mobile/affairs/dorm/transfer-options"),
        ("POST", "/api/v1/mobile/affairs/dorm/transfers"),
        ("GET", "/api/v1/mobile/affairs/dorm/transfers/my"),
        ("GET", "/api/v1/mobile/teacher/affairs/dorm/pending"),
        ("POST", "/api/v1/mobile/teacher/affairs/dorm/transfers/{transfer_id}/review"),
        ("POST", "/api/v1/mobile/teacher/affairs/dorm/exceptions/{exception_id}/handle"),
        ("GET", "/api/v1/mobile/affairs/my-activities"),
        ("POST", "/api/v1/mobile/affairs/activities/{activity_id}/enroll"),
        ("POST", "/api/v1/mobile/affairs/activities/{activity_id}/secure-checkin"),
        ("GET", "/api/v1/mobile/affairs/second-class/report"),
        ("POST", "/api/v1/mobile/affairs/second-class/appeals"),
        ("GET", "/api/v1/mobile/affairs/second-class/appeals/my"),
        ("GET", "/api/v1/mobile/teacher/affairs/activities/ongoing"),
        ("GET", "/api/v1/mobile/teacher/affairs/activities/{activity_id}/checkin-token"),
        ("GET", "/api/v1/mobile/teacher/mental-stats"),
        ("GET", "/api/v1/mobile/teacher/mental"),
        ("GET", "/api/v1/mobile/teacher/mental/{referral_id}"),
        ("POST", "/api/v1/mobile/teacher/mental/{referral_id}/follow"),
        ("POST", "/api/v1/mobile/teacher/mental/{referral_id}/escalate"),
        ("POST", "/api/v1/mobile/teacher/mental/{referral_id}/close"),
        ("GET", "/api/v1/mobile/teacher/talk"),
        ("GET", "/api/v1/mobile/teacher/talk/{talk_id}"),
        ("POST", "/api/v1/mobile/teacher/talk/{talk_id}/record"),
        ("POST", "/api/v1/mobile/teacher/talk/{talk_id}/follow-up"),
    }
    assert sorted(expected - routes) == []


def test_student_pc_and_miniapp_use_same_core_contract_paths():
    portal = (ROOT / "student-portal/src/services/affairsFourEndApi.js").read_text(encoding="utf-8")
    mini = "\n".join([
        (ROOT / "miniapp/src/services/affairsContractApi.js").read_text(encoding="utf-8"),
        (ROOT / "miniapp/src/services/affairsReturnedApi.js").read_text(encoding="utf-8"),
    ])
    for fragment in (
        "/mobile/affairs/leave/", "/mobile/affairs/aid/", "/mobile/affairs/funding/",
        "/mobile/affairs/dorm/transfer-options", "/mobile/affairs/dorm/transfers",
        "/mobile/affairs/second-class/report",
    ):
        assert fragment in portal
        assert fragment in mini


def test_all_teacher_mobile_state_changes_send_visible_version():
    source = (ROOT / "miniapp/src/services/affairsContractApi.js").read_text(encoding="utf-8")
    for name in (
        "approveLeave", "rejectLeave", "returnLeave", "confirmCancelLeave",
        "proxyCancelLeave", "reviewLeaveExtension", "handleLeaveOverdue",
        "reviewAid", "reviewFunding", "reviewDiscipline", "processRisk", "closeRisk",
        "reviewDormTransfer", "handleDormException", "recordTalk", "followTalk",
        "followMental", "escalateMental", "closeMental",
    ):
        start = source.index(f"{name}:")
        end = source.find("\n  }),", start)
        assert end > start, f"{name} 契约块无法解析"
        block = source[start:end + len("\n  }),")]
        assert "version" in block, f"{name} 未携带可见 version"
