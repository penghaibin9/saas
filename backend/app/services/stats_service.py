"""跨域真实统计聚合（工作台 + 数据中心 BI）。从各域真实表实时聚合，租户过滤。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.services.db_service import _iso, _tid, session


_CALIBER_LABELS = {"REGISTERED": "在册口径", "NATURAL": "自然口径"}


def _count(db, model, *conds):
    q = select(func.count()).select_from(model).where(model.tenant_id == _tid(), *conds)
    return db.scalar(q) or 0


def get_overview(caliber: str = "REGISTERED") -> dict:
    from app.models import (AcademicStudent, AcademicWarning, CsServiceStudent, EmpStudent,
                            GraduationStudent, InternshipRecord, OrientationStudent, StudentProfile,
                            UnifiedTodo, WorkflowTask)
    with session() as db:
        stu_total = _count(db, StudentProfile, StudentProfile.is_deleted.is_(False))
        ori = _count(db, OrientationStudent, OrientationStudent.is_deleted.is_(False),
                     OrientationStudent.record_status == "ACTIVE")
        cs = _count(db, CsServiceStudent, CsServiceStudent.is_deleted.is_(False),
                    CsServiceStudent.record_status == "ACTIVE")
        acad = _count(db, AcademicStudent, AcademicStudent.is_deleted.is_(False),
                      AcademicStudent.record_status == "ACTIVE")
        intern = _count(db, InternshipRecord, InternshipRecord.is_deleted.is_(False))
        grad = _count(db, GraduationStudent, GraduationStudent.is_deleted.is_(False),
                      GraduationStudent.record_status == "ACTIVE")
        emp_total = _count(db, EmpStudent, EmpStudent.is_deleted.is_(False),
                           EmpStudent.record_status == "ACTIVE")
        # 就业落实
        emp_impl = _count(db, EmpStudent, EmpStudent.is_deleted.is_(False),
                          EmpStudent.record_status == "ACTIVE",
                          EmpStudent.destination_type != "UNEMPLOYED")
        # 迎新报到
        ori_reported = _count(db, OrientationStudent, OrientationStudent.is_deleted.is_(False),
                              OrientationStudent.record_status == "ACTIVE",
                              OrientationStudent.report_status.in_(["CHECKED_IN", "COLLEGE_CONFIRMED"]))
        warn = _count(db, AcademicWarning, AcademicWarning.is_deleted.is_(False),
                      AcademicWarning.record_status == "ACTIVE",
                      AcademicWarning.status.in_(["PENDING_HANDLE", "PROCESSING", "ESCALATED"]))
        todo = _count(db, UnifiedTodo, UnifiedTodo.is_deleted.is_(False), UnifiedTodo.status == "PENDING")
        approval = _count(db, WorkflowTask, WorkflowTask.is_deleted.is_(False), WorkflowTask.status == "PENDING")

        def rate(a, b):
            return f"{(a / b * 100):.1f}" if b else "0.0"

        caliber_label = _CALIBER_LABELS.get(caliber, "在册口径")
        return {
            "caliber": caliber, "caliberLabel": caliber_label,
            "caliberNote": f"{caliber_label}：当前各域按学籍在册（record_status=ACTIVE）实时聚合",
            "updatedAt": _iso(datetime.now()),
            "stageFlow": [
                {"label": "迎新报到", "value": ori},
                {"label": "在校服务", "value": cs},
                {"label": "学业过程", "value": acad},
                {"label": "岗位实习", "value": intern, "active": True},
                {"label": "毕业设计", "value": grad},
                {"label": "就业去向", "value": emp_total},
            ],
            "metrics": [
                {"key": "studentTotal", "label": "在册学生总数", "value": str(stu_total), "unit": "人",
                 "trend": "", "trendQuality": "neutral", "sourceModule": "学生主档",
                 "description": "全校在库学生主档数（真实）", "drillRoute": "/admin/data-center/lifecycle",
                 "drillLabel": "生命周期总览"},
                {"key": "orientationRate", "label": "迎新报到率", "value": rate(ori_reported, ori), "unit": "%",
                 "trend": f"已报到 {ori_reported}/{ori}", "trendQuality": "good", "sourceModule": "迎新报到",
                 "description": "迎新台账中已现场报到占比（真实）", "drillRoute": "/admin/data-center/lifecycle",
                 "drillLabel": "生命周期总览"},
                {"key": "employmentRate", "label": "就业去向落实率", "value": rate(emp_impl, emp_total), "unit": "%",
                 "trend": f"已落实 {emp_impl}/{emp_total}", "trendQuality": "good", "sourceModule": "就业去向",
                 "description": "就业台账中非待就业占比（真实）", "drillRoute": "/admin/data-center/lifecycle",
                 "drillLabel": "生命周期总览"},
                {"key": "academicWarning", "label": "学业预警在办", "value": str(warn), "unit": "人",
                 "trend": "", "trendQuality": "bad" if warn else "good", "sourceModule": "学业过程",
                 "description": "未关闭学业预警学生数（真实）", "drillRoute": "/admin/academic/warnings",
                 "drillLabel": "学业预警"},
                {"key": "pendingTodo", "label": "全校待办", "value": str(todo), "unit": "件",
                 "trend": f"待审批 {approval}", "trendQuality": "neutral", "sourceModule": "待办中心",
                 "description": "待办 + 待审批（真实）", "drillRoute": "/admin/workflow/tasks",
                 "drillLabel": "审批任务"},
            ],
        }


def get_lifecycle(caliber: str = "REGISTERED") -> dict:
    ov = get_overview(caliber)
    flow = ov["stageFlow"]
    total = flow[0]["value"] or 1
    return {"caliber": caliber, "updatedAt": ov["updatedAt"], "totalCount": flow[0]["value"],
            "stages": [{"key": s["label"], "label": s["label"], "count": s["value"],
                        "rate": round(s["value"] / total * 1000) / 10} for s in flow]}


def get_risk_stats() -> dict:
    from app.models import (AcademicStudent, CsServiceStudent, EmpStudent, GraduationStudent,
                            OrientationStudent)
    with session() as db:
        # 各域风险字段：多数用 risk_level；学业域用 warning_level（同为 HIGH/MEDIUM/LOW 口径，见 academic L_LEVEL）
        def by_risk(model, extra=(), field="risk_level"):
            col = getattr(model, field)
            out = {}
            for lvl in ("HIGH", "MEDIUM", "LOW"):
                out[lvl] = _count(db, model, model.is_deleted.is_(False), col == lvl, *extra)
            return out
        domains = {"迎新": by_risk(OrientationStudent, (OrientationStudent.record_status == "ACTIVE",)),
                   "在校服务": by_risk(CsServiceStudent, (CsServiceStudent.record_status == "ACTIVE",)),
                   "学业": by_risk(AcademicStudent, (AcademicStudent.record_status == "ACTIVE",),
                                 field="warning_level"),
                   "毕业设计": by_risk(GraduationStudent, (GraduationStudent.record_status == "ACTIVE",)),
                   "就业": by_risk(EmpStudent, (EmpStudent.record_status == "ACTIVE",))}
        high = sum(d["HIGH"] for d in domains.values())
        medium = sum(d["MEDIUM"] for d in domains.values())
        return {"summary": {"high": high, "medium": medium},
                "byDomain": [{"domain": k, "high": v["HIGH"], "medium": v["MEDIUM"], "low": v["LOW"]}
                             for k, v in domains.items()]}


def get_workbench_summary() -> dict:
    """工作台首页真实汇总卡片。"""
    from app.models import (AcademicWarning, EmpStudent, OrientationStudent, StudentProfile,
                            UnifiedMessage, UnifiedTodo, WorkflowTask)
    with session() as db:
        return {
            "studentTotal": _count(db, StudentProfile, StudentProfile.is_deleted.is_(False)),
            "pendingTodo": _count(db, UnifiedTodo, UnifiedTodo.is_deleted.is_(False),
                                  UnifiedTodo.status == "PENDING"),
            "pendingApproval": _count(db, WorkflowTask, WorkflowTask.is_deleted.is_(False),
                                      WorkflowTask.status == "PENDING"),
            "unreadMessage": _count(db, UnifiedMessage, UnifiedMessage.is_deleted.is_(False),
                                    UnifiedMessage.status == "UNREAD"),
            "academicWarning": _count(db, AcademicWarning, AcademicWarning.is_deleted.is_(False),
                                      AcademicWarning.record_status == "ACTIVE",
                                      AcademicWarning.status.in_(["PENDING_HANDLE", "PROCESSING", "ESCALATED"])),
            "unemployed": _count(db, EmpStudent, EmpStudent.is_deleted.is_(False),
                                 EmpStudent.record_status == "ACTIVE",
                                 EmpStudent.destination_type == "UNEMPLOYED"),
            "orientationPending": _count(db, OrientationStudent, OrientationStudent.is_deleted.is_(False),
                                         OrientationStudent.record_status == "ACTIVE",
                                         OrientationStudent.report_status == "NOT_REPORTED"),
            "updatedAt": _iso(datetime.now()),
        }
