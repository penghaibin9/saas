"""Browser-session-scoped role switching for real DB accounts.

The generic auth service keeps user-wide refresh revocation for legacy/native semantics. Browser PC
surfaces need a narrower rule: switching one browser session must invalidate the old role only for
that session, without signing the user out of another browser or a teacher/student miniapp.
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.core.token_store import block_jti, revoke_refresh_by_session, revoke_refresh_by_user
from app.db.session import get_sessionmaker
from app.services import auth_service_db
from app.services.browser_auth_session_blocklist import block_auth_session


def switch_role(
    user_ctx: dict,
    context_id: str,
    client_type: str,
    *,
    auth_session_id: str | None,
) -> dict:
    db = get_sessionmaker()()
    try:
        user = auth_service_db._load_token_user(db, user_ctx)
        contexts = auth_service_db._role_contexts(db, user)
        target = auth_service_db._pick_context(contexts, context_id=context_id)
        if target is None or target["contextId"] != context_id:
            raise AppException("ROLE_NOT_FOUND", "身份不存在、已停用或不属于当前用户")

        # The access JTI and the whole old browser session must stop authorizing the previous role.
        block_jti(str(user_ctx.get("tokenJti") or ""), user_ctx.get("tokenExp"))

        user_id = f"db-{user.id}"
        session_id = str(auth_session_id or "")
        if session_id:
            block_auth_session(session_id)
            revoke_refresh_by_session(user_id, session_id)
        else:
            # One-time compatibility for pre-hotfix browser access tokens that do not yet carry a
            # session id. Fail safe here rather than allowing an old refresh to restore the role.
            revoke_refresh_by_user(user_id)

        result = auth_service_db._login_result(db, user, target, contexts, client_type)
        result.update({
            "contextType": target["roleCode"],
            "contextName": target["roleName"],
            "dataScope": target["dataScope"],
            "menusChanged": True,
        })
        return result
    finally:
        db.close()
