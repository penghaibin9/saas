from __future__ import annotations
from sqlalchemy import select
from app.core.context import get_current_user_ctx
from app.models import College,Major,SchoolClass,TeacherStudentScope
from app.services.db_service import _tid,session
_ADVISOR_ROLES=frozenset({"INTERN_MENTOR","TEACHER","INTERNSHIP_ADVISOR"})
def _role(user):return str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or (user or {}).get("userType") or "").upper()
def resolve_teacher_scope(user=None):
    u=user or get_current_user_ctx() or {};role=_role(u)
    if role in {"SCHOOL_ADMIN","PLATFORM_SUPER_ADMIN"}:
        return {"mode":"ADMIN_TENANT","roleCode":role,"by":"ROLE","studentNos":set(),"classNames":set(),"collegeNames":set(),"majorNames":set(),"advisorNames":set(),"advisorUserIds":set()}
    scope={"mode":"SCOPED","roleCode":role,"by":"DEFAULT_DENY","studentNos":set(),"classNames":set(),"collegeNames":set(),"majorNames":set(),"advisorNames":set(),"advisorUserIds":set()}
    try:
        if u.get("userId") or u.get("id"):scope["advisorUserIds"].add(int(u.get("userId") or u.get("id")))
    except Exception:pass
    if str(u.get("realName") or "").strip():scope["advisorNames"].add(str(u.get("realName")).strip())
    keys={str(u.get("loginName") or "").strip(),str(u.get("userId") or u.get("id") or "").strip(),str(u.get("realName") or "").strip()}-{""}
    if not keys:return scope
    try:
        with session() as db:
            rows=db.scalars(select(TeacherStudentScope).where(TeacherStudentScope.tenant_id==_tid(),TeacherStudentScope.teacher_key.in_(keys),TeacherStudentScope.status=="ACTIVE",TeacherStudentScope.is_deleted.is_(False))).all()
        for row in rows:
            typ=str(row.scope_type or "").upper();value=str(row.ref_value or "").strip()
            if typ=="STUDENT":scope["studentNos"].add(value)
            elif typ=="CLASS":scope["classNames"].add(value)
            elif typ=="COLLEGE":scope["collegeNames"].add(value)
            elif typ=="MAJOR":scope["majorNames"].add(value)
            elif typ=="ADVISOR":scope["advisorNames"].add(value)
        if rows:scope["by"]="TEACHER_STUDENT_SCOPE"
    except Exception:pass
    return scope
def scope_match_row(scope,student_no=None,class_name=None,advisor_name=None,college_name=None,major_name=None,advisor_user_id=None):
    if scope.get("mode")!="SCOPED":return True
    ids=set(scope.get("advisorUserIds") or set())
    id_hit=False
    try:id_hit=advisor_user_id is not None and int(advisor_user_id) in ids
    except Exception:pass
    name_hit=bool(advisor_name and str(advisor_name) in set(scope.get("advisorNames") or set()))
    if str(scope.get("roleCode") or "").upper() in _ADVISOR_ROLES:return id_hit or name_hit
    return bool((student_no and str(student_no) in set(scope.get("studentNos") or set())) or (class_name and str(class_name) in set(scope.get("classNames") or set())) or (college_name and str(college_name) in set(scope.get("collegeNames") or set())) or (major_name and str(major_name) in set(scope.get("majorNames") or set())) or id_hit or name_hit)
def can_teacher_view_student(user,student,scope=None,db=None):
    scope=scope or resolve_teacher_scope(user)
    if scope.get("mode")!="SCOPED":return True
    own=db is None
    if own:db=session()
    try:
        class_name=college_name=major_name=None
        school_class=None
        if getattr(student,"class_id",None):
            school_class=db.get(SchoolClass,student.class_id);class_name=school_class.class_name if school_class else None
        major_id=getattr(student,"major_id",None) or (school_class.major_id if school_class else None)
        major=db.get(Major,major_id) if major_id else None
        major_name=major.major_name if major else None
        cid=getattr(student,"college_id",None) or (major.college_id if major else None)
        if cid:
            college=db.get(College,cid);college_name=college.college_name if college else None
        return scope_match_row(scope,student_no=getattr(student,"student_no",None),class_name=class_name,college_name=college_name,major_name=major_name)
    finally:
        if own:db.close()
