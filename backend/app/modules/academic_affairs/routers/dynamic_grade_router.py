"""R10 动态成绩项接口。

C-W5 keeps the mature dynamic-grade state machine intact while installing the same
formal TeachingClassTeacher + effective-week authority used by fixed-score
execution. Teacher replacement / co-teaching therefore takes effect immediately
for scheme, roster, component score and score-read operations without rewriting
AaGradeTask.teacher_key history.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.permissions import require_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.academic_affairs.services import academic_affairs_dynamic_grade_live_authority as live_authority
from app.modules.academic_affairs.services import academic_affairs_dynamic_grade_service as service
from app.modules.academic_affairs.services import academic_affairs_dynamic_grade_roster_service as roster_service
from app.modules.academic_affairs.services import academic_affairs_grade_teacher_relation_guard as teacher_relation_guard

# Roster service resolves task scope through ``service._task`` too. Install the
# formal teacher-relation primitive before the mature dynamic-grade adapter so this
# router is safe even if it is imported before the fixed-score router.
teacher_relation_guard.install()
live_authority.install(service)

router = APIRouter(prefix="/academic-affairs/grade-tasks", tags=["教务中心-动态成绩"])


class GradeComponentBody(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)
    name: str = Field(..., min_length=1, max_length=80)
    weight: float = Field(..., gt=0, le=100, strict=True, allow_inf_nan=False)
    required: bool = True
    order: int | None = Field(default=None, ge=1, le=99)


class GradeSchemeBody(BaseModel):
    components: list[GradeComponentBody] = Field(..., min_length=1, max_length=12)


class DynamicScoreBody(BaseModel):
    studentId: int = Field(..., gt=0)
    scores: dict[str, Any] = Field(default_factory=dict)
    exceptionFlag: Literal["NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"] = "NORMAL"


@router.get("/{task_id}/scheme", summary="动态成绩项方案")
def dynamic_grade_scheme(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(service.get_scheme(task_id, user))


@router.put("/{task_id}/scheme", summary="配置动态成绩项（首次录分前）")
def dynamic_grade_scheme_update(
    body: GradeSchemeBody,
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(
        service.configure_scheme(task_id, user, [item.model_dump() for item in body.components]),
        message="成绩项方案已保存",
    )


@router.get("/{task_id}/component-roster", summary="动态成绩项正式名单与分项回显")
def dynamic_grade_component_roster(
    page: int | None = Query(default=None, ge=1),
    pageSize: int = Query(default=30, ge=1, le=100),
    expectedRosterVersionId: str | None = Query(default=None),
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(roster_service.component_roster(task_id, user, page=page, page_size=pageSize, expected_roster_version_id=expectedRosterVersionId))


@router.post("/{task_id}/component-scores", summary="录入学生动态分项成绩")
def dynamic_grade_enter(
    body: DynamicScoreBody,
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(
        service.enter_component_scores(
            task_id, user, body.studentId, body.scores, body.exceptionFlag,
        ),
        message="分项成绩已保存",
    )


@router.get("/{task_id}/students/{student_id}/component-scores", summary="查看学生动态分项成绩")
def dynamic_grade_student_scores(
    task_id: int = Path(..., gt=0),
    student_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(service.student_component_scores(task_id, user, student_id))


class DynamicRosterIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    teachingClassId: str = Field(min_length=1)
    rosterVersionId: str = Field(min_length=1)
    rosterVersionNo: int = Field(ge=1, strict=True)
    rosterHash: str = Field(min_length=64, max_length=64)
    memberCount: int = Field(ge=1, strict=True)


class DynamicExpectedIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedTaskVersion: int = Field(ge=0, strict=True)
    expectedSchemeId: str
    expectedSchemeVersion: int = Field(ge=1, strict=True)
    rosterIdentity: DynamicRosterIdentity


class DynamicBatchRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    studentId: int = Field(gt=0)
    expectedRecordId: str
    expectedRowVersion: int | None = Field(ge=0, strict=True)
    scores: dict[str, Any] = Field(default_factory=dict)
    exceptionFlag: Literal["NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"] = "NORMAL"

    @field_validator("studentId", mode="before")
    @classmethod
    def exact_student_id(cls, value):
        # IDs arrive as decimal strings on mobile to preserve bigint precision.
        # Reject booleans/floats before Pydantic can coerce them to another object.
        if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).isascii() or not str(value).isdigit():
            raise ValueError("studentId须为正整数或十进制整数字符串")
        return value


class DynamicCommandBody(DynamicExpectedIdentity):
    commandKey: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class DynamicBatchBody(DynamicCommandBody):
    rows: list[DynamicBatchRow] = Field(min_length=1, max_length=500)


@router.post("/{task_id}/component-batch-save", summary="动态分项整批原子保存")
def dynamic_grade_batch_save(body: DynamicBatchBody, task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input"))):
    expected = body.model_dump(exclude={"rows", "commandKey"})
    return success(service.enter_component_batch(task_id, user, [row.model_dump() for row in body.rows],
        expected, command_key=body.commandKey), message="动态分项已整批保存")


@router.post("/{task_id}/component-submit", summary="动态成绩按已核对版本提交正式学院审核")
def dynamic_grade_submit(body: DynamicCommandBody, task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.submit"))):
    from app.modules.academic_affairs.services import academic_affairs_grade_deadline_service as deadline
    return success(deadline.teacher_submit_task(task_id, user, expected=body.model_dump(exclude={"commandKey"}), command_key=body.commandKey),
                   message="已提交学院审核")


@router.get("/{task_id}/component-quality", summary="正式动态成绩完整性检查")
def dynamic_grade_quality(task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input"))):
    with service.session() as db:
        task = service._task(db, task_id, user)
        return success(service.quality_in_session(db, task, service.formal_roster(db, task)))


@router.get("/{task_id}/component-command-receipts/{command_key}", summary="只读核对原动态成绩命令回执")
def dynamic_grade_command_receipt(task_id: int, command_key: str,
    operation: Literal["GRADE_COMPONENT_BATCH_SAVE", "GRADE_TASK_SUBMIT"],
    user=Depends(get_current_user)):
    from app.modules.academic_affairs.services import academic_affairs_grade_command_receipt as receipts
    with service.session() as db:
        service._task(db, task_id, user)
    result = receipts.read(user, operation, command_key)
    if result.get("result") and str(result["result"].get("gradeTaskId")) != str(task_id):
        raise service._conflict("原命令不属于当前成绩任务")
    return success(result)
