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
        # 实习在岗率（口径 ai_proposal：InternshipRecord.status=ONBOARD 为在岗，分母=全部未删实习记录；口径待学校校准）
        intern_onboard = _count(db, InternshipRecord, InternshipRecord.is_deleted.is_(False),
                                InternshipRecord.status == "ONBOARD")
        # 毕设通过率（口径 existing_code：grad_qual_status PASS/FAIL，分母=已出结果者，避免把 PENDING/UNKNOWN 计入）
        grad_pass = _count(db, GraduationStudent, GraduationStudent.is_deleted.is_(False),
                           GraduationStudent.record_status == "ACTIVE",
                           GraduationStudent.grad_qual_status == "PASS")
        grad_judged = _count(db, GraduationStudent, GraduationStudent.is_deleted.is_(False),
                             GraduationStudent.record_status == "ACTIVE",
                             GraduationStudent.grad_qual_status.in_(["PASS", "FAIL"]))

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
                {"key": "internshipOnboardRate", "label": "实习在岗率", "value": rate(intern_onboard, intern), "unit": "%",
                 "trend": f"在岗 {intern_onboard}/{intern}", "trendQuality": "good", "sourceModule": "岗位实习",
                 "description": "实习记录中在岗（ONBOARD）占比（真实）", "drillRoute": "/admin/data-center/lifecycle",
                 "drillLabel": "生命周期总览"},
                {"key": "graduationPassRate", "label": "毕设通过率", "value": rate(grad_pass, grad_judged), "unit": "%",
                 "trend": f"通过 {grad_pass}/{grad_judged}", "trendQuality": "good", "sourceModule": "毕业设计",
                 "description": "毕设资格已出结果中通过（PASS）占比（真实）", "drillRoute": "/admin/data-center/lifecycle",
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


# ─────────────────────────────────────────────────────────────────────────────
# 领导驾驶舱专用聚合（board 版）：返回结构与前端 dataCenter.mock 同构，供前端
# withFallback 真分支直接消费。原则——有真实数据源的字段实时聚合，无数据源的字段
# 诚实占位（_NO_SOURCE），绝不编造数字；时间趋势依赖统计快照表（P3），未建表前返回空。
# 独立于 get_lifecycle / get_risk_stats（供 dashboard/stats 简单版消费），互不影响。
# ─────────────────────────────────────────────────────────────────────────────
_NO_SOURCE = "该指标需对应业务域统计支撑（待接入）"


def _pct(a: int, b: int) -> str:
    return f"{(a / b * 100):.1f}%" if b else "0.0%"


def get_lifecycle_board(caliber: str = "REGISTERED") -> dict:
    """生命周期总览驾驶舱聚合：六阶段漏斗 + 各域细分（同构 mock lifecycleFunnel + *Stats）。"""
    from app.models import (AcademicStudent, AcademicWarning, CsServiceStudent, EmpStudent,
                            GraduationStudent, InternshipRecord, OrientationStudent, StudentProfile)
    with session() as db:
        stu_total = _count(db, StudentProfile, StudentProfile.is_deleted.is_(False))
        ori = _count(db, OrientationStudent, OrientationStudent.is_deleted.is_(False),
                     OrientationStudent.record_status == "ACTIVE")
        ori_reported = _count(db, OrientationStudent, OrientationStudent.is_deleted.is_(False),
                              OrientationStudent.record_status == "ACTIVE",
                              OrientationStudent.report_status.in_(["CHECKED_IN", "COLLEGE_CONFIRMED"]))
        cs = _count(db, CsServiceStudent, CsServiceStudent.is_deleted.is_(False),
                    CsServiceStudent.record_status == "ACTIVE")
        acad = _count(db, AcademicStudent, AcademicStudent.is_deleted.is_(False),
                      AcademicStudent.record_status == "ACTIVE")
        warn = _count(db, AcademicWarning, AcademicWarning.is_deleted.is_(False),
                      AcademicWarning.record_status == "ACTIVE",
                      AcademicWarning.status.in_(["PENDING_HANDLE", "PROCESSING", "ESCALATED"]))
        intern = _count(db, InternshipRecord, InternshipRecord.is_deleted.is_(False))
        intern_onboard = _count(db, InternshipRecord, InternshipRecord.is_deleted.is_(False),
                                InternshipRecord.status == "ONBOARD")
        grad = _count(db, GraduationStudent, GraduationStudent.is_deleted.is_(False),
                      GraduationStudent.record_status == "ACTIVE")
        grad_pass = _count(db, GraduationStudent, GraduationStudent.is_deleted.is_(False),
                           GraduationStudent.record_status == "ACTIVE",
                           GraduationStudent.grad_qual_status == "PASS")
        grad_fail = _count(db, GraduationStudent, GraduationStudent.is_deleted.is_(False),
                           GraduationStudent.record_status == "ACTIVE",
                           GraduationStudent.grad_qual_status == "FAIL")
        emp_total = _count(db, EmpStudent, EmpStudent.is_deleted.is_(False),
                           EmpStudent.record_status == "ACTIVE")
        emp_impl = _count(db, EmpStudent, EmpStudent.is_deleted.is_(False),
                          EmpStudent.record_status == "ACTIVE",
                          EmpStudent.destination_type != "UNEMPLOYED")
        unemployed = max(emp_total - emp_impl, 0)
        ori_pending = max(ori - ori_reported, 0)
        intern_off = max(intern - intern_onboard, 0)

        base = stu_total or 1

        def r(n):
            return round(n / base * 1000) / 10

        stages = [
            {"key": "ORIENTATION", "label": "迎新报到", "count": ori, "rate": r(ori),
             "abnormal": ori_pending, "note": f"未报到 {ori_pending} 人（真实）"},
            {"key": "SERVICE", "label": "在校服务", "count": cs, "rate": r(cs),
             "abnormal": 0, "note": "工单超时/宿舍异动闭环需在校服务域统计支撑（待接入）"},
            {"key": "ACADEMIC", "label": "学业过程", "count": acad, "rate": r(acad),
             "abnormal": warn, "note": f"学业预警在办 {warn} 人（真实）"},
            {"key": "INTERNSHIP", "label": "岗位实习", "count": intern, "rate": r(intern), "active": True,
             "abnormal": intern_off, "note": f"非在岗 {intern_off} 人（含准备/考核/归档）"},
            {"key": "GRADUATION", "label": "毕业设计", "count": grad, "rate": r(grad),
             "abnormal": grad_fail, "note": f"毕设资格未通过 {grad_fail} 人（真实）"},
            {"key": "EMPLOYMENT", "label": "就业去向", "count": emp_impl, "rate": r(emp_impl),
             "abnormal": unemployed, "note": f"未落实去向 {unemployed} 人（真实）"},
        ]

        def stat(title, items):
            return {"title": title, "scopeNote": "全校口径 · 实时聚合", "items": items}

        def it(label, value):
            return {"label": label, "value": value}

        stage_stats = {
            "ORIENTATION": stat("迎新报到", [
                it("应报到", f"{ori} 人"), it("完成报到", f"{ori_reported} 人（{_pct(ori_reported, ori)}）"),
                it("未报到跟进", f"{ori_pending} 人")]),
            "SERVICE": stat("在校服务", [
                it("在册在校服务学生", f"{cs} 人"), it("工单按时办结率", _NO_SOURCE),
                it("服务满意度", _NO_SOURCE)]),
            "ACADEMIC": stat("学业过程", [
                it("学业在册学生", f"{acad} 人"), it("学业预警在办", f"{warn} 人"),
                it("课程及格率", _NO_SOURCE)]),
            "INTERNSHIP": stat("岗位实习", [
                it("实习记录", f"{intern} 条"), it("当前在岗", f"{intern_onboard} 人（{_pct(intern_onboard, intern)}）"),
                it("今日打卡率", _NO_SOURCE)]),
            "GRADUATION": stat("毕业设计", [
                it("毕设在册", f"{grad} 人"), it("资格通过", f"{grad_pass} 人"),
                it("资格未通过", f"{grad_fail} 人")]),
            "EMPLOYMENT": stat("就业去向", [
                it("去向落实", f"{emp_impl} 人（{_pct(emp_impl, emp_total)}）"), it("待落实", f"{unemployed} 人"),
                it("在册毕业生", f"{emp_total} 人")]),
        }

        return {
            "funnel": {"cohortLabel": "全校在册学生", "totalCount": stu_total,
                       "updatedAt": _iso(datetime.now()), "stages": stages},
            "stageStats": stage_stats,
            "scopeLabel": "全校",
            "timeRangeLabel": "实时聚合",
            "trendCharts": [],  # 时间序列依赖统计快照表（P3），未建表前不提供，前端按空态渲染
        }


def get_risk_board() -> dict:
    """风险预警驾驶舱聚合：来源分布 + 等级分布（真实）；处理进度/趋势待接入（同构 mock riskStats）。"""
    raw = get_risk_stats()  # 复用各域 HIGH/MEDIUM/LOW 真实聚合
    code_map = {"迎新": ("ORIENTATION", "迎新报到"), "在校服务": ("SERVICE", "在校服务"),
                "学业": ("ACADEMIC", "学业过程"), "毕业设计": ("GRADUATION", "毕业设计"),
                "就业": ("EMPLOYMENT", "就业去向")}
    by_source, total = [], 0
    for d in raw["byDomain"]:
        cnt = d["high"] + d["medium"] + d["low"]
        total += cnt
        code, name = code_map.get(d["domain"], (d["domain"], d["domain"]))
        by_source.append({"moduleCode": code, "moduleName": name, "count": cnt})
    by_source.sort(key=lambda x: x["count"], reverse=True)
    high = sum(d["high"] for d in raw["byDomain"])
    medium = sum(d["medium"] for d in raw["byDomain"])
    low = sum(d["low"] for d in raw["byDomain"])
    top = by_source[0]["moduleName"] if by_source and by_source[0]["count"] else "—"
    return {
        "updatedAt": _iso(datetime.now()),
        "total": total,
        # 注：实习域风险为独立处置表，暂未并入本聚合（待接入 internship 风险处置表）
        "bySource": by_source,
        "byLevel": [{"level": "HIGH", "label": "高风险", "count": high},
                    {"level": "MEDIUM", "label": "中风险", "count": medium},
                    {"level": "LOW", "label": "低风险", "count": low}],
        "byStatus": [],  # 处理进度（待处理/跟进中/已关闭）跨域状态口径未统一，暂不提供，前端空态
        "trend": {"months": [], "total": [], "high": []},  # 时间趋势依赖快照表（P3）
        "suggestion": (f"当前风险来源最高：{top}；建议对该域重点巡检" if total else "当前无在办风险"),
    }


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
