"""离校（Departure）跨域只读投影（V3 施工手册 SP-D01~SP-D04）。

定位
────────────────────────────────────────────────────────────
离校不是一个新的业务域，而是对**已有各域真实事实**的编排：毕业设计、岗位实习、
就业去向、学工违纪各自是自己的权威，本模块只读取它们已经产生的结论，投影成
「离校清单」。**不复制各域真值表**，不在这里另建一套判定，也不写任何业务状态。

结果语义（SP-D03：UNKNOWN 与 ERROR 必须分开）
────────────────────────────────────────────────────────────
- ``PASS``            该环节已按各域权威完成。
- ``FAIL``            各域权威给出了明确的未通过结论。
- ``NOT_REQUIRED``    该学生本就不涉及这一环节（例如没有毕设任务）。
- ``NOT_STARTED``     该环节需要学生先发起，但学生还没做（例如没登记就业去向）。
- ``MANUAL_PENDING``  事实齐全但结论要学校按自身制度判定，系统不替学校下结论。
- ``UNKNOWN``         查得到数据源但无法判定（数据不完整），**不是**故障。
- ``ERROR``           读取该域时真的出错了。与 UNKNOWN 严格区分：跨域聚合一旦把
                      源故障当成"没数据"，用户就无法判断是"没办"还是"系统坏了"。

每个环节独立异常边界：任一域抛错只把该环节标成 ERROR，不影响其他环节，也不会
让整张清单打不开。

就绪判定（SP-D02 的核心）
────────────────────────────────────────────────────────────
``READY`` 只在**所有 blocking 环节都是 PASS 或 NOT_REQUIRED** 时成立。
任何 blocking 环节处于 FAIL / UNKNOWN / ERROR / MANUAL_PENDING / NOT_STARTED
都不 READY——尤其不能因为"存在 EmpStudent 行且 destination_type 有值"就判就业
已办：该列默认值就是 UNEMPLOYED，那代表"系统默认未就业"，不是"学生声明了去向"。

阻断策略的边界
────────────────────────────────────────────────────────────
「哪些环节阻断离校」本质是学校制度，不同学校不同。本模块只给出保守默认：
学业类结论（毕设/实习/就业）阻断，纪律类交由学校人工判定（MANUAL_PENDING）。
真正的校本策略配置尚未建立，这一点在 DTO 的 ``policySource`` 里如实标注，
不假装这是学校已确认的规则。
"""
from __future__ import annotations

from typing import Any, Callable

from app.services.db_service import _tid

PASS = "PASS"
FAIL = "FAIL"
NOT_REQUIRED = "NOT_REQUIRED"
NOT_STARTED = "NOT_STARTED"
MANUAL_PENDING = "MANUAL_PENDING"
UNKNOWN = "UNKNOWN"
ERROR = "ERROR"

#: 可以判定为"这一项不挡路"的结果。
_CLEARED = frozenset({PASS, NOT_REQUIRED})

DEPARTURE_VERSION = 1


def _item(
    key: str,
    title: str,
    source: str,
    *,
    result: str,
    blocking: bool,
    detail: str = "",
    evidence_version: Any = None,
    action: dict | None = None,
) -> dict:
    return {
        "key": key,
        "title": title,
        # source 指明这条结论来自哪个域的哪张权威表，便于追责与复核。
        "source": source,
        "result": result,
        "blocking": bool(blocking),
        "detail": detail,
        # 各域自己的版本/主键，用于证明这条结论对应的是哪一份事实快照。
        "evidenceVersion": None if evidence_version is None else str(evidence_version),
        # 学生可以去哪里处理这一项；没有真实落点时为 None，前端据此禁用而不是猜路由。
        "action": action,
    }


def _safe(build: Callable[[], dict], *, key: str, title: str, source: str, blocking: bool) -> dict:
    """每个环节独立异常边界：该域读失败只把这一项标 ERROR。

    SP-D03：这里**不能**把异常吞成 UNKNOWN——"没数据"和"系统坏了"对学生是完全
    不同的处置，混在一起会让人以为自己没办手续。
    """
    try:
        return build()
    except Exception as exc:  # noqa: BLE001 —— 跨域聚合必须隔离单域故障
        return _item(
            key, title, source,
            result=ERROR,
            blocking=blocking,
            detail=f"该环节数据暂时读取失败（{type(exc).__name__}），请稍后重试或联系学校",
        )


# ── 各环节 ────────────────────────────────────────────────

def _employment_item(db, student) -> dict:
    """就业去向：SP-D02 —— 默认 UNEMPLOYED 不等于学生已声明去向。"""
    from app.models import EmpStudent
    from app.services.mobile_student_service import _resolve_domain_student

    emp = _resolve_domain_student(db, EmpStudent, student)
    action = {"client": "studentPc", "path": "/employment", "query": {}, "label": "去就业去向登记"}
    if not emp:
        return _item("employment", "就业去向登记", "employment:EmpStudent",
                     result=NOT_STARTED, blocking=True,
                     detail="尚未建立就业档案，请先登记就业去向", action=action)

    destination = str(emp.destination_type or "").upper()
    verify = str(emp.verify_status or "PENDING_VERIFY").upper()

    # 关键：destination_type 的数据库默认值就是 UNEMPLOYED。"有一行 EmpStudent
    # 且 destination_type 非空"完全不能证明学生声明过去向。只有核验状态真的推进过
    # （VERIFIED / RETURNED），才说明这条记录被学校实际处理过。
    if destination in ("", "UNEMPLOYED") and verify == "PENDING_VERIFY":
        return _item("employment", "就业去向登记", "employment:EmpStudent",
                     result=NOT_STARTED, blocking=True,
                     evidence_version=emp.version,
                     detail="系统默认为未就业，尚未收到你本人的去向声明", action=action)

    if verify == "VERIFIED":
        return _item("employment", "就业去向登记", "employment:EmpStudent",
                     result=PASS, blocking=True, evidence_version=emp.version,
                     detail="去向已通过学校核验", action=action)
    if verify == "RETURNED":
        return _item("employment", "就业去向登记", "employment:EmpStudent",
                     result=FAIL, blocking=True, evidence_version=emp.version,
                     detail="去向材料被退回补正，请按学校要求补充后重新提交", action=action)
    return _item("employment", "就业去向登记", "employment:EmpStudent",
                 result=MANUAL_PENDING, blocking=True, evidence_version=emp.version,
                 detail="去向已提交，等待学校核验", action=action)


def _graduation_item(db, student) -> dict:
    """毕业设计：以 GraduationGrade（已发布成绩）为权威，不自己算分。"""
    from sqlalchemy import select
    from app.models import GraduationGrade, GraduationStudent
    from app.services.mobile_student_service import _resolve_domain_student

    gd = _resolve_domain_student(db, GraduationStudent, student)
    action = {"client": "studentPc", "path": "/graduation", "query": {}, "label": "去毕业设计"}
    if not gd:
        # 没有毕设任务的学生（例如部分专业）本就不涉及这一环节。
        return _item("graduation", "毕业设计", "graduation:GraduationStudent",
                     result=NOT_REQUIRED, blocking=True,
                     detail="本次未安排毕业设计任务")

    grade = db.scalar(select(GraduationGrade).where(
        GraduationGrade.tenant_id == _tid(),
        GraduationGrade.gd_student_id == gd.id,
        GraduationGrade.is_deleted.is_(False),
    ).order_by(GraduationGrade.id.desc()))
    if not grade:
        return _item("graduation", "毕业设计", "graduation:GraduationGrade",
                     result=MANUAL_PENDING, blocking=True, evidence_version=gd.version,
                     detail="毕业设计尚未产生最终成绩", action=action)

    status = str(grade.status or "").upper()
    level = str(grade.grade_level or "").strip()
    if status != "PUBLISHED":
        return _item("graduation", "毕业设计", "graduation:GraduationGrade",
                     result=MANUAL_PENDING, blocking=True, evidence_version=grade.version,
                     detail="毕业设计成绩尚未发布", action=action)
    if not level:
        # 已发布但没有等第：事实不完整，无法判定——这是 UNKNOWN，不是故障。
        return _item("graduation", "毕业设计", "graduation:GraduationGrade",
                     result=UNKNOWN, blocking=True, evidence_version=grade.version,
                     detail="成绩已发布但缺少等第信息，无法判定是否通过", action=action)
    if level == "不及格":
        return _item("graduation", "毕业设计", "graduation:GraduationGrade",
                     result=FAIL, blocking=True, evidence_version=grade.version,
                     detail=f"毕业设计成绩为{level}", action=action)
    return _item("graduation", "毕业设计", "graduation:GraduationGrade",
                 result=PASS, blocking=True, evidence_version=grade.version,
                 detail=f"毕业设计成绩{level}", action=action)


def _internship_item(db, student) -> dict:
    """岗位实习：以 InternshipFinalScore（已发布总评）为权威。"""
    from sqlalchemy import select
    from app.models import InternshipFinalScore

    action = {"client": "studentPc", "path": "/internship", "query": {}, "label": "去岗位实习"}
    score = db.scalar(select(InternshipFinalScore).where(
        InternshipFinalScore.tenant_id == _tid(),
        InternshipFinalScore.student_id == int(student.id),
        InternshipFinalScore.is_deleted.is_(False),
    ).order_by(InternshipFinalScore.id.desc()))
    if not score:
        return _item("internship", "岗位实习", "internship:InternshipFinalScore",
                     result=NOT_REQUIRED, blocking=True,
                     detail="本次未安排岗位实习总评")

    status = str(score.status or "").upper()
    if status != "PUBLISHED":
        return _item("internship", "岗位实习", "internship:InternshipFinalScore",
                     result=MANUAL_PENDING, blocking=True, evidence_version=score.version,
                     detail="实习总评尚未发布", action=action)
    if score.incomplete:
        return _item("internship", "岗位实习", "internship:InternshipFinalScore",
                     result=UNKNOWN, blocking=True, evidence_version=score.version,
                     detail=f"实习考核存在缺项：{score.incomplete_reason or '未说明'}", action=action)
    if not score.is_pass:
        return _item("internship", "岗位实习", "internship:InternshipFinalScore",
                     result=FAIL, blocking=True, evidence_version=score.version,
                     detail="实习总评未达合格线", action=action)
    return _item("internship", "岗位实习", "internship:InternshipFinalScore",
                 result=PASS, blocking=True, evidence_version=score.version,
                 detail="实习总评合格", action=action)


def _discipline_item(db, student) -> dict:
    """违纪处理：是否阻断离校属于校本制度，系统不替学校下结论。"""
    from sqlalchemy import select
    from app.models import DisciplineCase

    rows = db.scalars(select(DisciplineCase).where(
        DisciplineCase.tenant_id == _tid(),
        DisciplineCase.student_id == int(student.id),
        DisciplineCase.is_deleted.is_(False),
    ).order_by(DisciplineCase.id.desc())).all()
    active = [r for r in rows if r.removed_at is None
              and str(r.status or "").upper() not in ("REMOVED", "VOIDED", "REJECTED")]
    if not active:
        return _item("discipline", "违纪处理", "affairs:DisciplineCase",
                     result=PASS, blocking=False, detail="无未解除的违纪处分")
    latest = active[0]
    return _item("discipline", "违纪处理", "affairs:DisciplineCase",
                 result=MANUAL_PENDING, blocking=False, evidence_version=latest.version,
                 detail=f"存在 {len(active)} 条未解除的违纪处分，是否影响离校由学校按制度判定",
                 action={"client": "studentPc", "path": "/campus-service",
                         "query": {"tab": "discipline"}, "label": "查看违纪与申诉"})


_BUILDERS: tuple[tuple[str, str, str, bool, Callable], ...] = (
    ("graduation", "毕业设计", "graduation:GraduationGrade", True, _graduation_item),
    ("internship", "岗位实习", "internship:InternshipFinalScore", True, _internship_item),
    ("employment", "就业去向登记", "employment:EmpStudent", True, _employment_item),
    ("discipline", "违纪处理", "affairs:DisciplineCase", False, _discipline_item),
)


def build_my_departure(user: dict) -> dict:
    """学生本人的离校清单。"""
    from app.services.mobile_student_service import _require_student, _session, resolve_student

    u = _require_student(user)
    with _session() as db:
        student = resolve_student(db, u)
        if not student:
            return {
                "departureVersion": DEPARTURE_VERSION,
                "hasData": False,
                "note": "尚未建立你的学生档案，无法生成离校清单",
                "readiness": UNKNOWN,
                "items": [],
                "blockingCount": 0,
                "policySource": "default_conservative",
            }

        items = [
            _safe(lambda b=builder: b(db, student), key=key, title=title, source=source, blocking=blocking)
            for key, title, source, blocking, builder in _BUILDERS
        ]

    blocking_items = [x for x in items if x["blocking"]]
    unresolved = [x for x in blocking_items if x["result"] not in _CLEARED]
    readiness = "READY" if not unresolved else "NOT_READY"
    return {
        "departureVersion": DEPARTURE_VERSION,
        "hasData": True,
        "readiness": readiness,
        "items": items,
        "blockingCount": len(unresolved),
        # 如实标注：阻断策略目前是本模块的保守默认，不是学校已配置的校本规则。
        "policySource": "default_conservative",
        "policyNote": "当前离校阻断口径为系统保守默认；学校自定义离校环节与阻断规则尚未开放配置。",
    }
