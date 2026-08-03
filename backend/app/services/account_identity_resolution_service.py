"""SYS-03：账号的稳定主体解析、身份绑定与绑定异常处置。

要解决的老问题
──────────────
历史实现把 ``login_name == student_no`` 当成身份权威：学号改一次，"这个账号是谁"
就换了一个人；同名同手机号的两个人，靠姓名/手机号匹配会直接串号。V6 的硬规则是
**权威关系只认稳定键**：``t_user.id``（账号主体）与 ``t_student_profile.id``（学籍主体），
学号、工号、登录名一律降级为可变属性。

本模块不新建表（本卡"优先复用现有账号/身份表"）：
- 学生：``t_student_account_link``（已存在，ACTIVE 唯一）是权威绑定；
- 教职工：当前系统没有独立人事主档，**staffId 就等于 userId**，工号只是 login_name
  的当前取值。这一点必须写明，否则下游会误以为存在一个独立的 staff 主键。

登录名匹配仍保留为**只读兜底**，但每次命中都会产出一条 ``LEGACY_LOGIN_MATCH`` 异常，
督促管理员点"修复绑定"把它转成结构化绑定——先双写、可对账、再退役，不一刀切。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

# 身份来源（越靠前越权威）
SOURCE_LINK = "STUDENT_ACCOUNT_LINK"   # 结构化绑定，稳定
SOURCE_LEGACY_LOGIN = "LEGACY_LOGIN_MATCH"  # 登录名==学号，历史兜底
SOURCE_SELF = "USER_ROW"               # 教职工：账号自身即主体
SOURCE_NONE = "NONE"

# 异常码
ISSUE_NO_BINDING = "NO_BINDING"                 # 学生账号没有任何学籍绑定
ISSUE_LEGACY_LOGIN_MATCH = "LEGACY_LOGIN_MATCH"  # 只能靠登录名猜出学籍
ISSUE_DANGLING_BINDING = "DANGLING_BINDING"     # 绑定指向已删除/不存在的学籍
ISSUE_STALE_SNAPSHOT = "STALE_SNAPSHOT"         # 绑定快照里的学号与当前学号不一致
ISSUE_AMBIGUOUS_LEGACY = "AMBIGUOUS_LEGACY"     # 登录名匹配到多条学籍，禁止自动认领
ISSUE_DUPLICATE_NAME_PHONE = "DUPLICATE_NAME_PHONE"  # 同名同手机号，人工核对
ISSUE_NO_ROLE = "NO_ROLE"                       # 账号无任何有效角色
ISSUE_CROSS_TENANT = "CROSS_TENANT"             # 绑定跨租户（越权数据，必须拦）

SEVERITY = {
    ISSUE_NO_BINDING: "HIGH",
    ISSUE_LEGACY_LOGIN_MATCH: "MEDIUM",
    ISSUE_DANGLING_BINDING: "HIGH",
    ISSUE_STALE_SNAPSHOT: "LOW",
    ISSUE_AMBIGUOUS_LEGACY: "HIGH",
    ISSUE_DUPLICATE_NAME_PHONE: "MEDIUM",
    ISSUE_NO_ROLE: "MEDIUM",
    ISSUE_CROSS_TENANT: "HIGH",
}

_ISSUE_TEXT = {
    ISSUE_NO_BINDING: "学生账号未绑定学籍主档，业务范围与本人数据无法解析",
    ISSUE_LEGACY_LOGIN_MATCH: "仅靠登录名与学号相同才找到学籍，学号一改就会失联，请修复为结构化绑定",
    ISSUE_DANGLING_BINDING: "绑定指向的学籍主档不存在或已删除",
    ISSUE_STALE_SNAPSHOT: "绑定时记录的学号与当前学号不一致（仅快照过期，主体未变）",
    ISSUE_AMBIGUOUS_LEGACY: "登录名匹配到多条学籍，已拒绝自动认领，请人工指定",
    ISSUE_DUPLICATE_NAME_PHONE: "存在同姓名且同手机号的其他账号，禁止按姓名/手机号匹配身份",
    ISSUE_NO_ROLE: "账号没有任何有效角色，登录后无可用功能",
    ISSUE_CROSS_TENANT: "绑定数据跨租户，已按安全策略拒绝",
}


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _issue(code: str, **extra: Any) -> dict:
    return {"code": code, "severity": SEVERITY.get(code, "LOW"),
            "message": _ISSUE_TEXT.get(code, code), **extra}


def _load_account(db, user_id: int, tenant_id: int):
    from app.models import User

    account = db.scalars(select(User).where(
        User.id == int(user_id), User.tenant_id == tenant_id,
        User.is_deleted.is_(False))).first()
    if account is None:
        raise AppException("DATA_NOT_FOUND", "账号不存在或不在当前数据范围内")
    return account


def _active_link(db, tenant_id: int, *, user_id: int | None = None, student_id: int | None = None):
    from app.models import StudentAccountLink

    stmt = select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == tenant_id,
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
    )
    if user_id is not None:
        stmt = stmt.where(StudentAccountLink.user_id == int(user_id))
    if student_id is not None:
        stmt = stmt.where(StudentAccountLink.student_id == int(student_id))
    return db.scalars(stmt).first()


def _is_student_account(db, account) -> bool:
    from app.models import Role, UserRole

    if str(account.user_type or "").upper() == "STUDENT":
        return True
    if _active_link(db, account.tenant_id, user_id=account.id) is not None:
        return True
    return bool(db.scalar(select(func.count(UserRole.id)).join(
        Role, Role.id == UserRole.role_id).where(
        UserRole.tenant_id == account.tenant_id, UserRole.user_id == account.id,
        UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
        Role.role_code == "STUDENT", Role.is_deleted.is_(False))))


def _legacy_candidates(db, tenant_id: int, login_name: str) -> list:
    """登录名当学号用的历史兜底。返回全部命中，多条时拒绝自动认领。"""
    from app.models import StudentProfile

    if not str(login_name or "").strip():
        return []
    return list(db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
        StudentProfile.student_no == str(login_name).strip(),
    )).all())


def effective_identity(user_id: int, *, tenant_id: int | None = None) -> dict:
    """一个账号的稳定主体解析结果。所有下游只应该引用这里的 userId/studentId/staffId。"""
    from app.models import Role, StudentProfile, User, UserRole

    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        account = _load_account(db, user_id, tid)
        issues: list[dict] = []
        is_student = _is_student_account(db, account)

        student_id: int | None = None
        student_no = ""
        source = SOURCE_SELF if not is_student else SOURCE_NONE
        link = _active_link(db, tid, user_id=account.id) if is_student else None
        profile: Any = None

        if link is not None:
            if int(link.tenant_id) != tid:
                issues.append(_issue(ISSUE_CROSS_TENANT, linkId=str(link.id)))
            else:
                profile = db.get(StudentProfile, int(link.student_id))
                if profile is None or profile.is_deleted or int(profile.tenant_id) != tid:
                    issues.append(_issue(ISSUE_DANGLING_BINDING, studentId=str(link.student_id)))
                    profile = None
                else:
                    student_id = int(profile.id)
                    student_no = profile.student_no or ""
                    source = SOURCE_LINK
                    if (link.bound_student_no or "") and link.bound_student_no != student_no:
                        issues.append(_issue(ISSUE_STALE_SNAPSHOT,
                                             boundStudentNo=link.bound_student_no,
                                             currentStudentNo=student_no))
        elif is_student:
            candidates = _legacy_candidates(db, tid, account.login_name)
            if len(candidates) > 1:
                issues.append(_issue(ISSUE_AMBIGUOUS_LEGACY,
                                     candidateIds=[str(c.id) for c in candidates]))
            elif len(candidates) == 1:
                profile = candidates[0]
                student_id = int(profile.id)
                student_no = profile.student_no or ""
                source = SOURCE_LEGACY_LOGIN
                issues.append(_issue(ISSUE_LEGACY_LOGIN_MATCH, studentId=str(student_id)))
            else:
                issues.append(_issue(ISSUE_NO_BINDING))

        roles = [r for _, r in db.execute(select(UserRole.user_id, Role).join(
            Role, Role.id == UserRole.role_id).where(
            UserRole.tenant_id == tid, UserRole.user_id == account.id,
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
            Role.is_deleted.is_(False))).all()]
        if not roles:
            issues.append(_issue(ISSUE_NO_ROLE))

        # 同名 + 同手机号：只做提示，绝不据此合并身份
        if account.phone_hash:
            twins = db.scalars(select(User).where(
                User.tenant_id == tid, User.is_deleted.is_(False),
                User.id != account.id,
                User.real_name == account.real_name,
                User.phone_hash == account.phone_hash)).all()
            if twins:
                issues.append(_issue(ISSUE_DUPLICATE_NAME_PHONE,
                                     otherUserIds=[str(t.id) for t in twins]))

        return {
            "userId": str(account.id),
            "subjectKey": f"user:{account.id}",
            "tenantId": str(tid),
            "loginName": account.login_name,
            "realName": account.real_name,
            "userType": account.user_type,
            "accountType": "STUDENT" if is_student else "STAFF",
            "status": str(account.status or "").upper(),
            "version": int(account.version or 0),
            "studentId": str(student_id) if student_id else "",
            "studentNo": student_no,
            # 教职工没有独立人事主档：staffId 恒等于 userId，工号只是 login_name 的当前值
            "staffId": "" if is_student else str(account.id),
            "staffNo": "" if is_student else account.login_name,
            "identitySource": source,
            "binding": {
                "linkId": str(link.id) if link is not None else "",
                "linkStatus": link.link_status if link is not None else "",
                "source": link.source if link is not None else "",
                "boundLoginName": (link.bound_login_name or "") if link is not None else "",
                "boundStudentNo": (link.bound_student_no or "") if link is not None else "",
                "boundAt": str(link.bound_at or "")[:19] if link is not None else "",
            },
            "roles": [{"code": r.role_code, "name": r.role_name} for r in roles],
            "issues": issues,
            "repairable": any(i["code"] in (ISSUE_NO_BINDING, ISSUE_LEGACY_LOGIN_MATCH,
                                            ISSUE_DANGLING_BINDING, ISSUE_AMBIGUOUS_LEGACY)
                              for i in issues),
        }
    finally:
        db.close()


def resolve_by_student(student_id: int, *, tenant_id: int | None = None) -> dict | None:
    """反向解析：学籍主体 → 登录账号。同样只走稳定绑定。"""
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        link = _active_link(db, tid, student_id=int(student_id))
        if link is None:
            return None
        user_id = int(link.user_id)
    finally:
        db.close()
    return effective_identity(user_id, tenant_id=tid)


def repair_binding(user_id: int, *, student_id: int, reason: str,
                   expected_version: int | None = None, tenant_id: int | None = None,
                   user: dict | None = None) -> dict:
    """把账号绑定到指定学籍主体（新建或改绑），旧绑定留痕为 REVOKED。"""
    from app.models import StudentAccountLink, StudentProfile

    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "修复绑定的原因不少于 5 个字")
    tid = _tid(tenant_id)
    actor = str((user or {}).get("userId") or "").replace("db-", "")
    actor_id = int(actor) if actor.isdigit() else None

    db = get_sessionmaker()()
    try:
        account = _load_account(db, user_id, tid)
        if expected_version is not None and int(expected_version) != int(account.version or 0):
            raise AppException("DATA_CONFLICT", "账号已被他人更新，请刷新后重试")
        profile = db.get(StudentProfile, int(student_id))
        if profile is None or profile.is_deleted or int(profile.tenant_id) != tid:
            raise AppException("DATA_NOT_FOUND", "学籍主档不存在或不在当前学校范围内")

        # 目标学籍已被别的账号占用 → 拒绝，避免一个学生两个可登录账号
        occupied = _active_link(db, tid, student_id=int(profile.id))
        if occupied is not None and int(occupied.user_id) != int(account.id):
            raise AppException("VALIDATION_ERROR",
                               f"该学籍已绑定其他账号（userId={occupied.user_id}），请先解绑")

        before = _active_link(db, tid, user_id=account.id)
        if before is not None and int(before.student_id) == int(profile.id):
            raise AppException("VALIDATION_ERROR", "该账号已绑定到此学籍，无需修复")
        if before is not None:
            before.link_status = "REVOKED"
            before.updated_by = actor_id
            before.version = int(before.version or 0) + 1
            db.flush()

        link = StudentAccountLink(
            tenant_id=tid, student_id=int(profile.id), user_id=int(account.id),
            link_status="ACTIVE", source="MANUAL",
            bound_login_name=account.login_name, bound_student_no=profile.student_no,
            bound_at=_now(), created_by=actor_id, updated_by=actor_id,
        )
        db.add(link)
        account.version = int(account.version or 0) + 1
        db.commit()
        payload = {
            "userId": str(account.id), "studentId": str(profile.id),
            "previousStudentId": str(before.student_id) if before is not None else "",
        }
    except AppException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AppException("INTERNAL_ERROR", f"修复绑定失败：{exc}") from exc
    finally:
        db.close()

    from app.services import audit_log

    audit_log.record("ACCOUNT_BINDING_REPAIR", f"账号 {payload['userId']} 绑定学籍 {payload['studentId']}",
                     detail={"reason": reason, **payload, "moduleCode": "systemAdmin"})
    # 绑定变化会改写数据范围解析结果，必须让下一次请求重新计算
    try:
        from app.services.auth_service_db import invalidate_subject_cache

        invalidate_subject_cache(f"db-{payload['userId']}", tid)
    except Exception:
        pass
    return effective_identity(int(payload["userId"]), tenant_id=tid)


def unbind(user_id: int, *, reason: str, expected_version: int | None = None,
           tenant_id: int | None = None, user: dict | None = None) -> dict:
    """解除绑定：历史行保留为 REVOKED，不物理删除。"""
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "解绑原因不少于 5 个字")
    tid = _tid(tenant_id)
    actor = str((user or {}).get("userId") or "").replace("db-", "")
    actor_id = int(actor) if actor.isdigit() else None
    db = get_sessionmaker()()
    try:
        account = _load_account(db, user_id, tid)
        if expected_version is not None and int(expected_version) != int(account.version or 0):
            raise AppException("DATA_CONFLICT", "账号已被他人更新，请刷新后重试")
        link = _active_link(db, tid, user_id=account.id)
        if link is None:
            raise AppException("DATA_NOT_FOUND", "该账号当前没有有效绑定")
        student_id = int(link.student_id)
        link.link_status = "REVOKED"
        link.updated_by = actor_id
        link.version = int(link.version or 0) + 1
        account.version = int(account.version or 0) + 1
        db.commit()
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services import audit_log

    audit_log.record("ACCOUNT_BINDING_REVOKE", f"账号 {user_id} 解除学籍绑定 {student_id}",
                     detail={"reason": reason, "userId": str(user_id),
                             "studentId": str(student_id), "moduleCode": "systemAdmin"})
    try:
        from app.services.auth_service_db import invalidate_subject_cache

        invalidate_subject_cache(f"db-{user_id}", tid)
    except Exception:
        pass
    return effective_identity(int(user_id), tenant_id=tid)


def batch_repair(items: list[dict], *, reason: str, tenant_id: int | None = None,
                 user: dict | None = None) -> dict:
    """批量修复绑定：**逐项**返回成功/失败，绝不因为一条失败就整批回滚或整批静默。"""
    results: list[dict] = []
    for raw in items or []:
        uid = str((raw or {}).get("userId") or "").strip()
        sid = str((raw or {}).get("studentId") or "").strip()
        if not uid.isdigit() or not sid.isdigit():
            results.append({"userId": uid, "studentId": sid, "status": "FAILED",
                            "message": "userId/studentId 必须是数字主键"})
            continue
        try:
            repair_binding(int(uid), student_id=int(sid), reason=reason,
                           tenant_id=tenant_id, user=user)
            results.append({"userId": uid, "studentId": sid, "status": "OK", "message": "已修复"})
        except AppException as exc:
            results.append({"userId": uid, "studentId": sid, "status": "FAILED",
                            "message": exc.message})
        except Exception as exc:  # noqa: BLE001
            results.append({"userId": uid, "studentId": sid, "status": "FAILED",
                            "message": str(exc)})
    ok = sum(1 for r in results if r["status"] == "OK")
    return {"total": len(results), "succeeded": ok, "failed": len(results) - ok,
            "results": results}


def identity_issues(*, tenant_id: int | None = None, issue_code: str = "",
                    page: int = 1, page_size: int = 50) -> dict:
    """绑定异常队列：只扫学生类账号（教职工主体恒等于账号本身，不存在绑定异常）。"""
    from app.models import User

    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        accounts = db.scalars(select(User).where(
            User.tenant_id == tid, User.is_deleted.is_(False)
        ).order_by(User.id)).all()
        candidate_ids = [a.id for a in accounts if _is_student_account(db, a)]
    finally:
        db.close()

    rows: list[dict] = []
    for uid in candidate_ids:
        identity = effective_identity(uid, tenant_id=tid)
        matched = [i for i in identity["issues"]
                   if not issue_code or i["code"] == issue_code]
        if not matched:
            continue
        rows.append({
            "userId": identity["userId"], "loginName": identity["loginName"],
            "realName": identity["realName"], "studentId": identity["studentId"],
            "identitySource": identity["identitySource"], "version": identity["version"],
            "issues": matched,
            "topSeverity": "HIGH" if any(i["severity"] == "HIGH" for i in matched)
            else ("MEDIUM" if any(i["severity"] == "MEDIUM" for i in matched) else "LOW"),
        })
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    start = (page - 1) * page_size
    return {"list": rows[start:start + page_size], "total": len(rows),
            "page": page, "pageSize": page_size,
            "counts": {code: sum(1 for r in rows for i in r["issues"] if i["code"] == code)
                       for code in SEVERITY}}
