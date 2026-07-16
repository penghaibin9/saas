"""通用用户偏好读写：按 tenant + user_key + pref_key 的 KV。

首个用途是新手引导「是否已看过」。引导已看过时写入 pref_value=引导版本号（如 "1"），
引导文案改版后调高版本号即可让老师重新看到一次，无需清库。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

MAX_KEYS = 200  # 单次批量读取上限，防止构造超长 keys 拖库


def _user_key(user) -> str:
    return str((user or {}).get("userId") or "")


def get_preferences(user, keys=None) -> dict:
    """读当前用户偏好。keys 为 None 时返回全部；否则只返回指定键。

    返回 {"items": {pref_key: pref_value}}；未设置过的键不出现在结果里，由调用方决定默认值。
    """
    uk = _user_key(user)
    if not uk:
        return {"items": {}}
    with session() as db:
        from app.models import UserPreference
        stmt = select(UserPreference).where(
            UserPreference.tenant_id == _tid(), UserPreference.user_key == uk,
            UserPreference.is_deleted.is_(False))
        if keys:
            stmt = stmt.where(UserPreference.pref_key.in_(list(keys)[:MAX_KEYS]))
        rows = db.scalars(stmt).all()
        return {"items": {r.pref_key: r.pref_value for r in rows}}


def set_preference(user, pref_key, pref_value) -> dict:
    """写单个偏好（存在则覆盖）。key 为空直接报错——不能既不落库又回「已保存」。"""
    uk = _user_key(user)
    key = str(pref_key or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "偏好键不能为空")
    if len(key) > 100:
        raise AppException("VALIDATION_ERROR", "偏好键过长（上限 100）")
    if not uk:
        raise AppException("VALIDATION_ERROR", "无法识别当前用户")
    val = str(pref_value if pref_value is not None else "")[:500]
    with session() as db:
        from app.models import UserPreference
        row = db.scalars(select(UserPreference).where(
            UserPreference.tenant_id == _tid(), UserPreference.user_key == uk,
            UserPreference.pref_key == key)).first()
        if row:
            row.pref_value = val
            row.is_deleted = False
        else:
            row = UserPreference(tenant_id=_tid(), user_key=uk, pref_key=key, pref_value=val)
            db.add(row)
        db.commit()
        return {"key": key, "value": val}
