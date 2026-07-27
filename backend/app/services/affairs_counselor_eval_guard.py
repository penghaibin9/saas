"""辅导员考评安全门：修复旧采集接口必失败、跨学院评分与未完成评分直接发布。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import AffairsCounselorAssessment, AffairsCounselorAssessmentPeriod, SchoolClass
    from app.services import affairs_class_service as classes

    old_collect = classes.collect_assessments
    old_list = classes.list_assessments
    old_score = classes.score_assessment
    old_publish = classes.publish_period

    def allowed_counselors(db, user):
        allowed, _scope = classes._allowed_class_ids(db, user)
        if allowed is None:
            return None
        return set(int(value) for value in db.scalars(select(SchoolClass.counselor_id).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(allowed or {-1}),
            SchoolClass.counselor_id.is_not(None), SchoolClass.is_deleted.is_(False),
        )).all())

    def collect_assessments(period_id, user, expected_version=None):
        # 旧接口未传 version 时，以服务端刚读取的版本执行 CAS；并发第二个请求仍会 409。
        if expected_version is None:
            with session() as db:
                period = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
                if not period or period.is_deleted or period.tenant_id != _tid():
                    raise not_found("考评周期不存在")
                expected_version = int(period.version or 0)
        return old_collect(period_id, user, expected_version)

    def list_assessments(period_id, user):
        rows = old_list(period_id, user)
        with session() as db:
            permitted = allowed_counselors(db, user)
        if permitted is None:
            return rows
        return [row for row in rows if str(row.get("counselorId") or "").isdigit()
                and int(row["counselorId"]) in permitted]

    def score_assessment(assessment_id, user, college_score, expected_version=None):
        with session() as db:
            assessment = db.get(AffairsCounselorAssessment, int(assessment_id))
            if not assessment or assessment.is_deleted or assessment.tenant_id != _tid():
                raise not_found("考评记录不存在")
            permitted = allowed_counselors(db, user)
            if permitted is not None and int(assessment.counselor_id or 0) not in permitted:
                raise AppException("NO_DATA_SCOPE", "该辅导员不在您的学院或班级数据范围内")
        return old_score(assessment_id, user, college_score, expected_version)

    def publish_period(period_id, user, expected_version=None):
        from app.core.affairs_security import build_affairs_context
        with session() as db:
            if build_affairs_context(user, db).scope_type != "TENANT_ALL":
                raise AppException("NO_PERMISSION", "仅学校/学工处全域管理员可发布全校辅导员考评")
            period = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
            if not period or period.is_deleted or period.tenant_id != _tid():
                raise not_found("考评周期不存在")
            rows = db.scalars(select(AffairsCounselorAssessment).where(
                AffairsCounselorAssessment.tenant_id == _tid(),
                AffairsCounselorAssessment.period_id == int(period_id),
                AffairsCounselorAssessment.is_deleted.is_(False),
            )).all()
            if not rows:
                raise AppException("DATA_CONFLICT", "考评周期尚未生成任何辅导员记录")
            pending = [row for row in rows if row.status != "SCORED" or row.college_score is None]
            if pending:
                raise AppException("DATA_CONFLICT", f"仍有{len(pending)}名辅导员未完成学院评分，不能发布")
        return old_publish(period_id, user, expected_version)

    classes.collect_assessments = collect_assessments
    classes.list_assessments = list_assessments
    classes.score_assessment = score_assessment
    classes.publish_period = publish_period
    _INSTALLED = True
