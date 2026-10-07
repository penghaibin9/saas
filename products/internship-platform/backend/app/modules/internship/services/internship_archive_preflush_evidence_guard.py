"""包 8：强制归档原始依据不得在归档主记录 ID 稳定前参与文件绑定。

归档命令为了取得 ``InternshipArchive.id`` 会先 flush 多次。原始 fileId 列表在
这些预备 flush 中必须持续隐藏；若在 ``after_flush_postexec`` 立刻恢复，后续自动
flush 仍可能把同一列表解释为以实习记录 ID 为目标的正式关系。

本守卫把原始列表保存在当前 Session 的事务暂存区，直到归档快照守卫在稳定的
``archive.id`` 上主动取出。正式归档记录最终只保存 file/version/hash/binding
快照；commit/rollback 后无条件清空暂存，绝不跨事务泄漏。
"""
from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session as OrmSession

_INSTALLED = False
_STASH_KEY = "internship_archive_raw_evidence_stash"


def _is_raw_file_ids(value) -> bool:
    return bool(value) and isinstance(value, list) and all(
        not isinstance(item, dict) for item in value
    )


def _stash(db, archive, raw) -> None:
    current = list(db.info.get(_STASH_KEY, []))
    for index, (existing, _existing_raw) in enumerate(current):
        if existing is archive:
            current[index] = (archive, list(raw))
            break
    else:
        current.append((archive, list(raw)))
    db.info[_STASH_KEY] = current


def _before_flush(db, flush_context, instances) -> None:
    from app.models import InternshipArchive

    for obj in list(db.new) + list(db.dirty):
        if not isinstance(obj, InternshipArchive):
            continue
        raw = getattr(obj, "force_evidence_file_ids", None)
        if not _is_raw_file_ids(raw):
            continue
        _stash(db, obj, raw)
        # 不在 after_flush 中恢复。原始 ID 只能由稳定 archive.id 的快照守卫取出。
        obj.force_evidence_file_ids = None


def pop_raw_evidence(db, archive) -> list | None:
    """取出指定归档对象的事务内原始依据；每份暂存只能消费一次。"""
    current = list(db.info.get(_STASH_KEY, []))
    found = None
    remaining = []
    for existing, raw in current:
        if existing is archive and found is None:
            found = list(raw)
        else:
            remaining.append((existing, raw))
    if remaining:
        db.info[_STASH_KEY] = remaining
    else:
        db.info.pop(_STASH_KEY, None)
    return found


def _clear(db) -> None:
    db.info.pop(_STASH_KEY, None)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    # insert=True 使隐藏动作先于其他 before_flush 文件监听器执行。
    event.listen(OrmSession, "before_flush", _before_flush, insert=True)
    event.listen(OrmSession, "after_commit", _clear)
    event.listen(OrmSession, "after_rollback", _clear)
    _INSTALLED = True
