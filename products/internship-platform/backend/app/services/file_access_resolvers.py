"""Small compatibility surface for standalone file binding code."""
from __future__ import annotations

from app.services.message_identity import resolve_message_user_id


def _owner_allows(file_obj, user: dict) -> bool:
    owner = str(file_obj.owner_user_id or file_obj.created_by or "").strip()
    if not owner:
        return False
    actor = resolve_message_user_id(user or {})
    values = {str(actor) if actor else "", str((user or {}).get("userId") or "").replace("db-", "")}
    return owner in {item for item in values if item}
