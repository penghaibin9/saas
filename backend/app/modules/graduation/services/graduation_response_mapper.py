"""毕业设计四端 DTO 契约归一化。

稳定评委席位以对象保存，但旧 PC/小程序页面按字符串数组展示。统一保留 memberDetails
作为稳定身份对象，同时返回 members/memberNames 字符串数组，避免四端各自猜字段。
"""
from __future__ import annotations

def normalize_defense_members(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    raw = result.get("memberDetails") or result.get("members") or []
    details, names = [], []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            name = item.strip()
            detail = {"name": name} if name else None
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("teacherName") or item.get("displayName") or "").strip()
            detail = dict(item)
            if name:
                detail["name"] = name
        else:
            name, detail = "", None
        if detail:
            details.append(detail)
        if name and name not in names:
            names.append(name)
    result["memberDetails"] = details
    result["members"] = names
    result["memberNames"] = names
    return result


_normalize_members = normalize_defense_members
