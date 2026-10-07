"""老师毕设身份按业务关系自动生效（不落成固定角色，也不需要老师切换角色）。

规则（与 SYS-07 business_identity_service 的铁律一致）：
- 关系在 → 身份在；关系撤销、批次归档或导师台账停用 → 下一次请求立即失效。
- 只认稳定 ID：t_user.login_name == t_gd_mentor.teacher_no，再比 mentor_id；不按姓名。
- 身份来源：
  * 指导教师 GD_MENTOR：导师台账已认定（QUALIFIED），或在进行中的批次里被分配了学生；
  * 评阅教师 GD_REVIEWER：进行中批次里有分给他的评阅（t_gd_review.reviewer_mentor_id）；
  * 答辩评委 GD_DEFENSE_EXPERT：进行中批次的答辩组组长或评委席位；
  * 答辩秘书 GD_DEFENSE_SECRETARY：进行中批次的答辩组秘书。

生效方式：
1. 权限展示/判定：get_effective_permission_patterns 追加这些身份的 graduationDesign.* 权限
   （不进入基础权限，因此不能被再授权给别人）。
2. 每个毕设请求（PC 与教师小程序依赖）按本次接口所需权限，挑选老师实际持有、且能做这件事的身份，
   把本请求的 currentRoleCode 临时换成该身份。各服务原有的数据范围代码按该身份的业务关系收敛，
   所以老师只能看到、操作与自己有关系的学生。
管理员角色、学生、平台账号永远不会被替换身份。
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import select

logger = logging.getLogger(__name__)

IDENTITY_ORDER: tuple[str, ...] = ("GD_MENTOR", "GD_REVIEWER", "GD_DEFENSE_EXPERT", "GD_DEFENSE_SECRETARY")
IDENTITY_LABELS = {
    "GD_MENTOR": "指导教师",
    "GD_REVIEWER": "评阅教师",
    "GD_DEFENSE_EXPERT": "答辩评委",
    "GD_DEFENSE_SECRETARY": "答辩秘书",
}
# 这些身份保持原样：管理员自带更大的范围，学生和平台账号不属于教师。
NEVER_OVERLAY_ROLES = frozenset({
    "PLATFORM_SUPER_ADMIN", "SAAS_ADMIN", "SCHOOL_ADMIN", "SYS_ADMIN",
    "GRADUATION_ADMIN", "GD_ADMIN", "GD_COLLEGE_ADMIN", "GD_MAJOR_ADMIN", "GD_GRADE_ADMIN",
    "COLLEGE_ADMIN", "STUDENT",
})
ELIGIBLE_USER_TYPES = frozenset({"TEACHER", "STAFF", "ADMIN"})
ACTIVE_BATCH_STATUSES = ("RUNNING", "CLOSED")
BLOCKED_MENTOR_STATUSES = frozenset({"DISABLED", "ARCHIVED", "REJECTED"})
DYNAMIC_ORDER: tuple[str, ...] = ("GD_MENTOR", "GD_REVIEWER", "GD_DEFENSE_SECRETARY")
STUDENT_PATH_KEYS = ("gd_student_id", "gdStudentId", "student_id", "studentId", "sid")
# 没有目标学生可比对时的动作偏好：答辩类列表/评分优先评委、秘书，而不是指导教师（否则只剩自己学生）。
CODE_PREFERENCE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("graduationDesign.defense.", ("GD_DEFENSE_EXPERT", "GD_DEFENSE_SECRETARY", "GD_MENTOR")),
    ("graduationDesign.review.", ("GD_REVIEWER",)),
)

_CACHE_KEY = "_gdAutoIdentities"
_MENTOR_KEY = "_gdAutoMentorId"


def role_of(user: dict | None) -> str:
    return str((user or {}).get("currentRoleCode") or (user or {}).get("userType") or "").strip().upper()


def _base_role(user: dict) -> str:
    return str(user.get("gdBaseRoleCode") or user.get("currentRoleCode") or user.get("userType") or "").strip().upper()


def is_eligible(user: dict | None) -> bool:
    """只有教职工账号、且当前不是管理员/平台/学生身份时才会自动获得毕设老师身份。"""
    if not user:
        return False
    user_type = str(user.get("userType") or "").strip().upper()
    base = _base_role(user)
    if user_type not in ELIGIBLE_USER_TYPES:
        return False
    if base in NEVER_OVERLAY_ROLES or base.startswith("PLATFORM_"):
        return False
    return bool(str(user.get("loginName") or "").strip() and str(user.get("tenantId") or "").strip())


def compute_identities(db, tenant_id: int, login_name: str) -> tuple[frozenset[str], int | None]:
    """从业务表实时计算身份；返回 (身份集合, 导师台账 id)。"""
    from app.models import (
        GraduationBatch, GraduationDefenseGroup, GraduationMentor, GraduationReview, GraduationStudent,
    )
    from app.modules.graduation.services import graduation_identity as gid

    login = (login_name or "").strip()
    if not login:
        return frozenset(), None
    mentor = db.scalars(select(GraduationMentor).where(
        GraduationMentor.tenant_id == int(tenant_id),
        GraduationMentor.teacher_no == login,
        GraduationMentor.is_deleted.is_(False),
    ).limit(1)).first()
    if mentor is None:
        return frozenset(), None
    status = str(mentor.qualification_status or "").upper()
    if status in BLOCKED_MENTOR_STATUSES:
        return frozenset(), int(mentor.id)

    active_batches = select(GraduationBatch.id).where(
        GraduationBatch.tenant_id == int(tenant_id),
        GraduationBatch.is_deleted.is_(False),
        GraduationBatch.status.in_(ACTIVE_BATCH_STATUSES),
    )
    held: set[str] = set()
    has_students = db.scalar(select(GraduationStudent.id).where(
        GraduationStudent.tenant_id == int(tenant_id),
        GraduationStudent.mentor_id == mentor.id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.batch_id.in_(active_batches),
    ).limit(1)) is not None
    if status == "QUALIFIED" or has_students:
        held.add("GD_MENTOR")

    has_review = db.scalar(select(GraduationReview.id).join(
        GraduationStudent, GraduationStudent.id == GraduationReview.gd_student_id,
    ).where(
        GraduationReview.tenant_id == int(tenant_id),
        GraduationReview.reviewer_mentor_id == mentor.id,
        GraduationReview.is_deleted.is_(False),
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.batch_id.in_(active_batches),
    ).limit(1)) is not None
    if has_review:
        held.add("GD_REVIEWER")

    groups = db.scalars(select(GraduationDefenseGroup).where(
        GraduationDefenseGroup.tenant_id == int(tenant_id),
        GraduationDefenseGroup.is_deleted.is_(False),
        GraduationDefenseGroup.batch_id.in_(active_batches),
    )).all()
    for group in groups:
        if group.secretary_mentor_id is not None and int(group.secretary_mentor_id) == int(mentor.id):
            held.add("GD_DEFENSE_SECRETARY")
        if any(seat.get("mentorId") is not None and int(seat["mentorId"]) == int(mentor.id)
               for seat in gid.judge_panel_seats(group)):
            held.add("GD_DEFENSE_EXPERT")
    return frozenset(held), int(mentor.id)


def held_identities(user: dict | None) -> frozenset[str]:
    """当前请求用户持有的毕设老师身份（同一请求内缓存在 user 字典上）。"""
    if not user:
        return frozenset()
    cached = user.get(_CACHE_KEY)
    if isinstance(cached, frozenset):
        return cached
    result: set[str] = set()
    base = _base_role(user)
    if base in IDENTITY_ORDER:
        # 兼容学校已经手工授予的毕设老师角色。
        result.add(base)
    mentor_id = None
    if is_eligible(user):
        try:
            from app.db.session import db_enabled, get_sessionmaker
            if db_enabled():
                db = get_sessionmaker()()
                try:
                    derived, mentor_id = compute_identities(db, int(user.get("tenantId")), str(user.get("loginName") or ""))
                    result |= derived
                finally:
                    db.close()
        except Exception:  # noqa: BLE001 — 身份计算失败时不授予任何自动身份（fail closed）
            logger.exception("graduation auto identity computation failed")
    frozen = frozenset(result)
    user[_CACHE_KEY] = frozen
    user[_MENTOR_KEY] = mentor_id
    return frozen


def auto_permission_patterns(user: dict | None) -> set[str]:
    """自动身份带来的毕设权限（只含 graduationDesign.*，不含其它模块）。"""
    if not is_eligible(user):
        return set()
    from app.core.permissions import ROLE_PERMISSIONS
    out: set[str] = set()
    for identity in held_identities(user):
        out.update(p for p in ROLE_PERMISSIONS.get(identity, ()) if p.startswith("graduationDesign."))
    return out


def _relations_to_student(db, mentor_id: int, student_id: int) -> set[str]:
    from app.models import GraduationDefenseGroup, GraduationReview, GraduationStudent
    from app.modules.graduation.services import graduation_identity as gid

    student = db.get(GraduationStudent, int(student_id))
    if student is None or student.is_deleted:
        return set()
    rel: set[str] = set()
    if student.mentor_id is not None and int(student.mentor_id) == int(mentor_id):
        rel.add("GD_MENTOR")
    if db.scalar(select(GraduationReview.id).where(
        GraduationReview.tenant_id == student.tenant_id,
        GraduationReview.gd_student_id == student.id,
        GraduationReview.reviewer_mentor_id == int(mentor_id),
        GraduationReview.is_deleted.is_(False),
    ).limit(1)) is not None:
        rel.add("GD_REVIEWER")
    if student.defense_group_id:
        group = db.get(GraduationDefenseGroup, int(student.defense_group_id))
        if group is not None and not group.is_deleted and group.tenant_id == student.tenant_id:
            if group.secretary_mentor_id is not None and int(group.secretary_mentor_id) == int(mentor_id):
                rel.add("GD_DEFENSE_SECRETARY")
            if any(seat.get("mentorId") is not None and int(seat["mentorId"]) == int(mentor_id)
                   for seat in gid.judge_panel_seats(group)):
                rel.add("GD_DEFENSE_EXPERT")
    return rel


def _student_id_from(path_params: dict | None) -> int | None:
    keys = STUDENT_PATH_KEYS
    if (path_params or {}).get("__path__", "").find("/gd-students/") >= 0:
        # /gd-students/{record_id} 的 record_id 就是毕设学生 ID。
        keys = keys + ("record_id",)
    for key in keys:
        value = (path_params or {}).get(key)
        if value not in (None, ""):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _student_id_from_records(db, tenant_id: int, path_params: dict | None) -> int | None:
    """材料中心的文件/成果/开题/材料路径里只有记录号、没有学生号：按记录反查所属毕设学生。

    没有这一步，既是指导教师又是评阅教师的老师点开“自己评阅的论文”时，
    系统认不出是哪个学生，会默认按指导教师处理，结果被数据范围拒绝。
    """
    params = path_params or {}
    from app.models import GraduationFinal, GraduationProposal, GraduationStudentMaterial
    from app.models.file import FileBinding
    from app.modules.graduation.materials.definitions import MODULE_CODE

    file_id = _int_or_none(params.get("file_id"))
    if file_id:
        scopes = db.scalars(select(FileBinding.scope_json).where(
            FileBinding.tenant_id == int(tenant_id), FileBinding.file_id == file_id,
            FileBinding.module_code == MODULE_CODE, FileBinding.is_deleted.is_(False),
        )).all()
        ids = {sid for sid in (_int_or_none((scope or {}).get("gdStudentId")) for scope in scopes) if sid}
        return next(iter(ids)) if len(ids) == 1 else None
    for key, model in (("final_id", GraduationFinal), ("proposal_id", GraduationProposal),
                       ("material_id", GraduationStudentMaterial)):
        record_id = _int_or_none(params.get(key))
        if record_id:
            return _int_or_none(db.scalar(select(model.gd_student_id).where(
                model.tenant_id == int(tenant_id), model.id == record_id,
            )))
    return None


def identity_hint(request) -> str | None:
    """前端可用请求头 X-GD-Identity 或查询参数 gdIdentity 说明本次以哪个毕设身份处理。"""
    try:
        value = request.headers.get("x-gd-identity") or request.query_params.get("gdIdentity")
    except Exception:  # noqa: BLE001
        return None
    value = str(value or "").strip().upper()
    return value if value in IDENTITY_ORDER else None


def choose_identity(user: dict, code: str | None, *, dynamic: bool = False,
                    path_params: dict | None = None, hint: str | None = None) -> str | None:
    """挑选本次请求要用的身份：老师持有、能做这件事，多个时优先与目标学生有关系的那个。"""
    held = held_identities(user)
    if not held:
        return None
    from app.core.permissions import ROLE_PERMISSIONS, _match
    if dynamic:
        candidates = [i for i in DYNAMIC_ORDER if i in held]
    else:
        if not code:
            return None
        candidates = [i for i in IDENTITY_ORDER if i in held and _match(code, ROLE_PERMISSIONS.get(i, ()))]
    if not candidates:
        return None
    # 1) 前端明确说明“我正以某身份处理”（老师工作台/小程序队列会带上），且老师确实持有 → 用它。
    wanted = str(hint or "").strip().upper()
    if wanted in candidates:
        return wanted
    # 2) 按与目标学生的关系选；3) 否则按动作偏好（答辩类优先评委/秘书），最后按默认顺序。
    student_id = _student_id_from(path_params)
    mentor_id = user.get(_MENTOR_KEY)
    if len(candidates) > 1 and mentor_id:
        try:
            from app.db.session import get_sessionmaker
            db = get_sessionmaker()()
            try:
                # 路径里没有学生号时（文件/成果/开题/材料记录），按记录反查所属学生。
                student_id = student_id or _student_id_from_records(
                    db, int(user.get("tenantId")), path_params)
                related = _relations_to_student(db, int(mentor_id), student_id) if student_id else set()
            finally:
                db.close()
            for identity in candidates:
                if identity in related:
                    return identity
        except Exception:  # noqa: BLE001 — 选不出更合适的就用默认顺序，数据范围仍由各服务把关
            logger.exception("graduation auto identity student relation lookup failed")
    for prefix, order in CODE_PREFERENCE:
        if code and code.startswith(prefix):
            for identity in order:
                if identity in candidates:
                    return identity
    return candidates[0]


def _targets(user: dict) -> Iterable[dict]:
    from app.core.context import get_current_user_ctx
    yield user
    ctx = get_current_user_ctx()
    if isinstance(ctx, dict) and ctx is not user:
        yield ctx


def apply_identity(user: dict, identity: str) -> None:
    """把本请求的毕设身份换成 identity（依赖里拿到的 user 与上下文 user 同步修改）。"""
    held = held_identities(user)
    mentor_id = user.get(_MENTOR_KEY)
    for target in _targets(user):
        target.setdefault("gdBaseRoleCode", target.get("currentRoleCode"))
        target.setdefault("gdBaseContextId", target.get("activeContextId"))
        target["currentRoleCode"] = identity
        # 非 role:<id> 的上下文让权限读取走该身份的系统模板，而不是老师原岗位的数据库角色。
        target["activeContextId"] = f"gd-auto:{identity}"
        target["gdAutoIdentity"] = identity
        target[_CACHE_KEY] = held
        target[_MENTOR_KEY] = mentor_id


def overlay_for_request(user: dict | None, code: str | None, *, dynamic: bool = False,
                        path_params: dict | None = None, hint: str | None = None) -> str | None:
    """毕设请求入口调用：必要时为本请求换上合适的老师身份，返回换上的身份（未换返回 None）。"""
    if not user or not is_eligible(user):
        return None
    role = role_of(user)
    if dynamic:
        # 材料类动态权限：已是毕设老师身份（含手工授予）时保持原样。
        if role in IDENTITY_ORDER:
            return None
    elif code:
        from app.core.permissions import _match, get_base_permission_patterns
        # 当前身份自己就能做（例如学校手工授予的角色）时保持原样，避免改变既有行为。
        if _match(code, get_base_permission_patterns(user)):
            return None
    identity = choose_identity(user, code, dynamic=dynamic, path_params=path_params, hint=hint)
    if identity and identity != role:
        apply_identity(user, identity)
        return identity
    return None


def describe(user: dict | None) -> dict:
    """给前端/诊断用的身份说明。"""
    held = held_identities(user) if user else frozenset()
    return {
        "identities": [i for i in IDENTITY_ORDER if i in held],
        "labels": [IDENTITY_LABELS[i] for i in IDENTITY_ORDER if i in held],
        "auto": bool(user) and is_eligible(user),
    }
