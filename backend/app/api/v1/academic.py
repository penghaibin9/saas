"""学业过程域 API（/api/v1/academic/*）。真实走库；写操作落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import require_staff
from app.schemas.academic import (AssignBody, GradeCreate, GradeUpdate, IdsBody, InterventionBody,
                                   LevelBody, MakeupCreate, ReasonBody, ResultBody, StatusBody,
                                   StudentCreate, StudentUpdate, WarningCreate)
from app.services import academic_service as svc

router = APIRouter(prefix="/academic", tags=["学业过程"])


def _p(i, t, page, ps):
    return success(paginate(i, t, page, ps))


@router.get("/dashboard", summary="学业看板")
def dashboard(user=Depends(require_staff)):
    return success(svc.get_dashboard())


# 学生
@router.get("/students", summary="学业台账列表")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             warningLevel: Optional[str] = None, academicStatus: Optional[str] = None,
             user=Depends(require_staff)):
    i, t = svc.list_students(page, pageSize, keyword=keyword, class_id=classId,
                             warning_level=warningLevel, academic_status=academicStatus)
    return _p(i, t, page, pageSize)


@router.get("/students/{sid}", summary="学生学业详情")
def student_detail(sid: str, user=Depends(require_staff)):
    return success(svc.get_student_detail(sid))


@router.post("/students", summary="新增学业记录")
def student_create(body: StudentCreate, user=Depends(require_staff)):
    return success(svc.create_student(body.model_dump()), message="已新增")


@router.put("/students/{sid}", summary="编辑学业记录")
def student_update(sid: str, body: StudentUpdate, user=Depends(require_staff)):
    return success(svc.update_student(sid, body.model_dump()), message="已保存")


@router.post("/students/{sid}/void", summary="作废学业记录（原因≥5字）")
def student_void(sid: str, body: ReasonBody, user=Depends(require_staff)):
    return success(svc.void_student(sid, body.reason), message="已作废")


# 成绩
@router.get("/grades", summary="成绩列表")
def grades(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, term: Optional[str] = None,
           passStatus: Optional[str] = None, examType: Optional[str] = None,
           user=Depends(require_staff)):
    i, t = svc.list_grades(page, pageSize, keyword=keyword, term=term, pass_status=passStatus,
                           exam_type=examType)
    return _p(i, t, page, pageSize)


@router.post("/grades", summary="新增成绩")
def grade_create(body: GradeCreate, user=Depends(require_staff)):
    return success(svc.create_grade(body.model_dump()), message="已新增")


@router.put("/grades/{gid}", summary="修改成绩（变更原因≥5字）")
def grade_update(gid: str, body: GradeUpdate, user=Depends(require_staff)):
    return success(svc.update_grade(gid, body.score, body.reason), message="已修改")


@router.post("/grades/{gid}/void", summary="作废成绩（原因≥5字）")
def grade_void(gid: str, body: ReasonBody, user=Depends(require_staff)):
    return success(svc.void_grade(gid, body.reason), message="已作废")


# 学分
@router.get("/credits", summary="学分修读列表（聚合）")
def credits(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            user=Depends(require_staff)):
    i, t = svc.list_credits(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


# 补考 / 重修
@router.get("/makeups", summary="补考列表")
def makeups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            user=Depends(require_staff)):
    i, t = svc.list_makeups(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.post("/makeups", summary="新增补考")
def makeup_create(body: MakeupCreate, user=Depends(require_staff)):
    return success(svc.create_makeup(body.model_dump()), message="已新增")


@router.put("/makeups/{mid}/status", summary="更新补考状态")
def makeup_status(mid: str, body: StatusBody, user=Depends(require_staff)):
    return success(svc.update_makeup_status(mid, body.status), message="已更新")


@router.get("/retakes", summary="重修列表")
def retakes(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            user=Depends(require_staff)):
    i, t = svc.list_retakes(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.put("/retakes/{rid}/status", summary="更新重修状态")
def retake_status(rid: str, body: StatusBody, user=Depends(require_staff)):
    return success(svc.update_retake_status(rid, body.status), message="已更新")


# 预警
@router.get("/warnings", summary="学业预警列表")
def warnings(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, type: Optional[str] = None, level: Optional[str] = None,
             status: Optional[str] = None, classId: Optional[str] = None,
             user=Depends(require_staff)):
    i, t = svc.list_warnings(page, pageSize, keyword=keyword, type=type, level=level, status=status,
                             class_id=classId)
    return _p(i, t, page, pageSize)


@router.get("/warnings/{wid}", summary="预警详情")
def warning_detail(wid: str, user=Depends(require_staff)):
    return success(svc.get_warning_detail(wid))


@router.post("/warnings", summary="新增预警（原因≥5字）")
def warning_create(body: WarningCreate, user=Depends(require_staff)):
    return success(svc.create_warning(body.model_dump()), message="已创建")


@router.put("/warnings/{wid}/level", summary="调整预警等级（原因≥5字）")
def warning_level(wid: str, body: LevelBody, user=Depends(require_staff)):
    return success(svc.update_warning_level(wid, body.level, body.reason), message="已调整")


@router.post("/warnings/{wid}/void", summary="作废预警（误报原因≥5字）")
def warning_void(wid: str, body: ReasonBody, user=Depends(require_staff)):
    return success(svc.void_warning(wid, body.reason), message="已作废")


@router.post("/warnings/assign", summary="分配预警跟进人")
def warning_assign(body: AssignBody, user=Depends(require_staff)):
    return success(svc.assign_warnings(body.ids, body.ownerName, body.ownerId), message="已分配")


@router.post("/warnings/remind", summary="批量提醒预警")
def warning_remind(body: IdsBody, user=Depends(require_staff)):
    return success(svc.remind_warnings(body.ids), message="已提醒")


@router.post("/warnings/{wid}/interventions", summary="新增预警干预（内容≥5字）")
def warning_intervention(wid: str, body: InterventionBody, user=Depends(require_staff)):
    return success(svc.create_intervention(wid, body.model_dump()), message="已记录")


@router.post("/warnings/{wid}/close", summary="关闭预警（说明≥5字）")
def warning_close(wid: str, body: ResultBody, user=Depends(require_staff)):
    return success(svc.close_warning(wid, body.result), message="已关闭")


@router.post("/warnings/{wid}/escalate", summary="升级预警（说明≥5字）")
def warning_escalate(wid: str, body: ReasonBody, user=Depends(require_staff)):
    return success(svc.escalate_warning(wid, body.reason), message="已升级")


@router.get("/audit-logs", summary="学业域审计")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(require_staff)):
    i, t = svc.list_audit(page, pageSize, biz_type=bizType, keyword=keyword)
    return _p(i, t, page, pageSize)
