"""13A-D 心理健康自评（学生自填，移动端首创）。

红线（与既有 affairs_mental_service.py 一致）：系统不做任何自动诊断，本模块只做算术汇总分登记；
命中阈值或学生主动求助信号时，直接落一条 t_affairs_psy_referral（GENERAL 级、referrer 标注"学生自评"），
供既有心理关注名单/回访/升级/关闭全流程消费——本模块不复用 affairs_mental_service.create_referral()，
因为该函数按"心理授权教职工调用"设计权限门（psy_scope_ids 对学生身份必 403），此处改为直接落库并复用
其字段结构/状态机语义，读侧（list_attention/get_referral 等）无需任何改动即可看到本模块生成的记录。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _iso, _tid, session
from app.services.mobile_student_service import _require_student, resolve_student

# 题目：通用情绪/睡眠/压力自评，非临床诊断量表；每题 0(很好/无)-3(很差/严重)
SURVEY_QUESTIONS = [
    {"key": "mood", "text": "最近两周，你的情绪状态整体如何？",
     "options": ["很好", "一般", "欠佳", "很差"]},
    {"key": "sleep", "text": "最近两周，你的睡眠质量如何？",
     "options": ["很好", "一般", "欠佳", "很差"]},
    {"key": "interest", "text": "最近两周，你对学习/生活的兴趣和动力如何？",
     "options": ["很好", "一般", "欠佳", "很差"]},
    {"key": "stress", "text": "最近两周，你是否感到明显的压力或焦虑？",
     "options": ["没有", "偶尔", "经常", "持续"]},
    {"key": "social", "text": "最近两周，你是否有想找人倾诉但找不到合适对象的情况？",
     "options": ["没有", "偶尔", "经常", "持续"]},
]
_TOTAL_MAX = len(SURVEY_QUESTIONS) * 3
_ALERT_THRESHOLD = 9  # 15分制，≥9(60%)触发人工关注登记，非诊断结论


def get_questions() -> dict:
    return {"questions": SURVEY_QUESTIONS, "maxScorePerItem": 3}


def _me(db, user):
    from app.core.exceptions import no_permission
    stu = resolve_student(db, _require_student(user))
    if not stu:
        raise no_permission("尚未建立你的学生档案")
    return stu


def submit_survey(user, answers, wants_contact=False) -> dict:
    """提交自评：answers=[{qKey,score}]；score 须 0-3。命中阈值或主动求助 → 落一条人工关注记录。"""
    valid_keys = {q["key"] for q in SURVEY_QUESTIONS}
    scores = {}
    for a in (answers or []):
        k = (a.get("qKey") if isinstance(a, dict) else getattr(a, "qKey", None))
        v = (a.get("score") if isinstance(a, dict) else getattr(a, "score", None))
        if k not in valid_keys:
            raise AppException("VALIDATION_ERROR", f"未知题目：{k}")
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", f"题目 {k} 分值非法")
        if v < 0 or v > 3:
            raise AppException("VALIDATION_ERROR", f"题目 {k} 分值须为 0-3")
        scores[k] = v
    if set(scores.keys()) != valid_keys:
        raise AppException("VALIDATION_ERROR", "请完成全部题目")
    total = sum(scores.values())
    wants_contact = bool(wants_contact)
    with session() as db:
        from app.models import AffairsAuditTrail, PsyReferral, PsySurveySubmission, StudentProfile
        stu = _me(db, user)
        # 同一学生的并发提交必须串行，避免一次求助在心理名单中生成多条未关闭转介。
        stu = db.scalar(
            select(StudentProfile)
            .where(StudentProfile.id == stu.id, StudentProfile.tenant_id == _tid())
            .with_for_update()
        )
        referral_id = None
        if total >= _ALERT_THRESHOLD or wants_contact:
            ref = db.scalar(select(PsyReferral).where(
                PsyReferral.tenant_id == _tid(),
                PsyReferral.student_id == stu.id,
                PsyReferral.referrer == "学生自评（系统自动登记）",
                PsyReferral.status.in_(("REFERRED", "FOLLOWING", "ESCALATED")),
                PsyReferral.is_deleted.is_(False),
            ).order_by(PsyReferral.id.desc()).limit(1))
            created = ref is None
            if created:
                ref = PsyReferral(
                    tenant_id=_tid(), student_id=stu.id, level="GENERAL", channel="校内咨询",
                    reason_summary=("学生自评问卷主动求助" if wants_contact else "学生自评问卷得分较高，建议关注"),
                    note=f"自评算术汇总分 {total}/{_TOTAL_MAX}（非诊断，仅供参考）；系统不做自动诊断结论。",
                    referrer="学生自评（系统自动登记）", status="REFERRED")
                db.add(ref)
                db.flush()
            referral_id = ref.id
            db.add(AffairsAuditTrail(
                tenant_id=_tid(), biz_type="PSY_REFERRAL", biz_id=ref.id,
                action="SELF_SURVEY_REFER" if created else "SELF_SURVEY_REUSE",
                operator=stu.real_name or stu.student_no, role_name="STUDENT",
                detail="学生主动申请联系" if wants_contact else "自评触发人工关注",
                occurred_at=datetime.utcnow(),
            ))
        sub = PsySurveySubmission(
            tenant_id=_tid(), student_id=stu.id, answers_json=json.dumps(scores, ensure_ascii=False),
            total_score=total, wants_contact=wants_contact, triggered_referral_id=referral_id,
            submitted_at=datetime.utcnow())
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return {"submissionId": str(sub.id), "totalScore": total, "maxScore": _TOTAL_MAX,
                "triggeredAttention": referral_id is not None}


def my_submissions(user) -> dict:
    """本人历史提交（仅本人可见，仅返回总分与是否触发关注，不回具体单题作答明细摘要之外内容）。"""
    with session() as db:
        from app.models import PsySurveySubmission
        stu = _me(db, user)
        rows = db.scalars(select(PsySurveySubmission).where(
            PsySurveySubmission.tenant_id == _tid(), PsySurveySubmission.student_id == stu.id,
            PsySurveySubmission.is_deleted.is_(False)
            ).order_by(PsySurveySubmission.id.desc())).all()
        return {"items": [{"submissionId": str(r.id), "totalScore": r.total_score,
                           "maxScore": _TOTAL_MAX, "wantsContact": bool(r.wants_contact),
                           "triggeredAttention": r.triggered_referral_id is not None,
                           "submittedAt": _iso(r.submitted_at)} for r in rows]}
