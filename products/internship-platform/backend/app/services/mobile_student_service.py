from __future__ import annotations
from sqlalchemy import select
from app.core.exceptions import no_permission
from app.core.tenant_scoped import tenant_get
from app.models import StudentAccountLink,StudentProfile
from app.services.db_service import _tid

def _require_student(user):
    role=str((user or {}).get("currentRoleCode") or (user or {}).get("userType") or "").upper()
    if role!="STUDENT":raise no_permission("该接口仅学生本人可用")
    return user or {}
def resolve_student(db,user):
    sid=user.get("studentId") or user.get("student_id")
    if sid:
        try:return tenant_get(db,StudentProfile,int(sid))
        except Exception:pass
    uid=user.get("userId") or user.get("id")
    if uid:
        raw_uid=str(uid).strip()
        if raw_uid.startswith("db-"):
            raw_uid=raw_uid[3:]
        try:
            user_id=int(raw_uid)
        except (TypeError,ValueError):
            user_id=0
        if user_id>0:
            link=db.scalar(select(StudentAccountLink).where(
                StudentAccountLink.tenant_id==_tid(),
                StudentAccountLink.user_id==user_id,
                StudentAccountLink.link_status=="ACTIVE",
                StudentAccountLink.is_deleted.is_(False),
            ).order_by(StudentAccountLink.id.desc()))
            if link:return tenant_get(db,StudentProfile,link.student_id)
    sno=str(user.get("studentNo") or "").strip()
    if sno:return db.scalar(select(StudentProfile).where(StudentProfile.tenant_id==_tid(),StudentProfile.student_no==sno,StudentProfile.is_deleted.is_(False)))
    return None
