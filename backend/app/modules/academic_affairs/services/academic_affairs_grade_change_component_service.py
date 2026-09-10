"""Dynamic evidence for the canonical correction command; never commits grades."""
import hashlib
import json
import math

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models.academic_affairs_r10 import AaGradeComponentScore, AaGradeSchemeSnapshot
from app.services.db_service import _tid
from . import academic_affairs_dynamic_grade_service as dynamic


def conflict(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _number(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise conflict("动态成绩分项不是有效数值")
    if not math.isfinite(result):
        raise conflict("动态成绩分项不是有限数值")
    return result


def source(db, task, record, *, lock=False):
    def rows(model, *where):
        query = select(model).where(model.tenant_id == _tid(), model.is_deleted.is_(False),
                                    model.grade_task_id == task.id, *where).order_by(model.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return db.scalars(query).all()

    schemes = rows(AaGradeSchemeSnapshot)
    scores = rows(AaGradeComponentScore, AaGradeComponentScore.student_id == record.student_id)
    if len(schemes) != 1 or schemes[0].status != "LOCKED":
        raise conflict("动态更正缺少唯一已锁定正式成绩方案")
    scheme = schemes[0]
    if not scheme.scheme_version or scheme.scheme_version < 1:
        raise conflict("动态成绩方案版本无效")
    try:
        components = dynamic.normalize_components(json.loads(scheme.scheme_json))
    except (ValueError, TypeError, AttributeError, AppException):
        raise conflict("正式动态成绩方案无法核对")
    by_code = {row.component_code: row for row in scores}
    if len(by_code) != len(scores) or set(by_code) != {item["code"] for item in components}:
        raise conflict("正式动态分项缺失、重复或与锁定方案不一致")
    entries = []
    for component in components:
        row = by_code[component["code"]]
        value, weight = _number(row.score), _number(component["weight"])
        if (row.grade_record_id != record.id or row.scheme_version != scheme.scheme_version
                or row.component_name != component["name"] or not 0 <= value <= 100
                or abs(_number(row.weight) - weight) > 0.0001
                or abs(_number(row.weighted_score) - round(value * weight / 100, 4)) > 0.0001):
            raise conflict("动态分项的正式对象、版本或权重已变化")
        entries.append({**component, "rowId": str(row.id), "rowVersion": int(row.version or 0),
                        "score": value, "weightedScore": float(row.weighted_score)})
    total = round(sum(item["weightedScore"] for item in entries), 2)
    passed = "PASSED" if total >= float(task.pass_line or 60) else "FAILED"
    if round(total) != record.total_score or passed != record.pass_status:
        raise conflict("动态分项与当前正式总评或通过状态不一致")
    return {"gradeTaskId": str(task.id), "gradeRecordId": str(record.id), "studentId": str(record.student_id),
            "currentGradeId": str(record.acad_grade_id), "recordVersion": int(record.version_no or 1),
            "schemeId": str(scheme.id), "schemeVersion": int(scheme.scheme_version),
            "scheme": components, "components": entries, "totalScore": record.total_score,
            "passStatus": record.pass_status, "passLine": float(task.pass_line or 60)}


def propose(original, submitted):
    if not isinstance(submitted, dict) or not submitted:
        raise conflict("动态更正须提供实际变化的分项")
    known = {item["code"] for item in original["components"]}
    if set(submitted) - known:
        raise conflict("拟更正分项不属于原正式成绩方案")
    entries = []
    for item in original["components"]:
        value = dynamic._score(_number(submitted[item["code"]]), item["name"]) if item["code"] in submitted else item["score"]
        entries.append({**item, "score": value, "weightedScore": round(value * item["weight"] / 100, 4)})
    if all(a["score"] == b["score"] for a, b in zip(entries, original["components"])):
        raise conflict("动态更正没有实际分项变化")
    total = round(sum(item["weightedScore"] for item in entries), 2)
    return {"components": entries, "totalScore": round(total),
            "passStatus": "PASSED" if total >= original["passLine"] else "FAILED"}


def create(db, task, record, body):
    original = source(db, task, record, lock=True)
    if getattr(body, "expectedComponentHash", None) != digest(original):
        raise conflict("动态分项来源已变化，请重新读取后确认")
    if any(getattr(body, field, None) is not None for field in ("newUsualScore", "newMidtermScore", "newFinalScore")):
        raise conflict("动态方案须按正式分项代码更正，不能混入固定三段字段")
    proposed = propose(original, getattr(body, "newComponentScores", None))
    return {"format": 1, "before": original, "proposed": proposed}


def load(request):
    try:
        value = json.loads(request.score_snapshot_json)
        if (not isinstance(value, dict) or value.get("format") != 1 or digest(value) != request.score_snapshot_hash
                or not isinstance(value.get("before"), dict) or not isinstance(value.get("proposed"), dict)
                or not isinstance(value["before"].get("components"), list)
                or not isinstance(value["proposed"].get("components"), list)):
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise conflict("更正申请缺少完整的动态分项冻结证据")


def validate(db, task, record, request, *, lock=False, current=None):
    frozen = load(request)
    current = source(db, task, record, lock=lock) if current is None else current
    if current != frozen.get("before"):
        raise conflict("申请时的动态方案或分项已变化，请驳回后重新申请")
    try:
        proposed = propose(current, {e["code"]: e["score"] for e in frozen["proposed"]["components"]})
    except (KeyError, TypeError):
        raise conflict("拟更正动态分项证据无法核对")
    if proposed != frozen.get("proposed") or proposed["totalScore"] != request.proposed_total_score or proposed["passStatus"] != request.proposed_pass_status:
        raise conflict("拟更正动态分项与申请总评结论不一致")
    return frozen


def projection(db, task, record, request=None):
    current, frozen, problems = None, None, []
    try:
        if request is not None:
            frozen = load(request)
        current = source(db, task, record)
        if request is not None:
            if request.status == "PENDING":
                validate(db, task, record, request, current=current)
    except AppException as error:
        problems.append(str(error.message))
    return {"componentEvidenceHash": digest(current) if current else None,
            "componentProblems": problems,
            "components": current["components"] if current else [],
            "componentScores": {e["code"]: e["score"] for e in current["components"]} if current else {},
            "dynamicScores": {"before": frozen["before"]["components"] if frozen else [],
                              "proposed": frozen["proposed"]["components"] if frozen else [],
                              "current": current["components"] if current else []}}


def apply(db, task, record, request):
    frozen = validate(db, task, record, request, lock=True)
    for item in frozen["proposed"]["components"]:
        row = db.get(AaGradeComponentScore, int(item["rowId"]))
        row.score, row.weighted_score = item["score"], item["weightedScore"]
        row.version = int(row.version or 0) + 1
    # The caller updates GradeRecord, appends AcademicGrade and commits exactly once.
    return frozen
