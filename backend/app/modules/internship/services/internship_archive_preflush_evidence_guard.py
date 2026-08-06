"""包 8：强制归档原始依据不得在归档主记录 ID 稳定前参与文件绑定。

归档命令为了取得 ``InternshipArchive.id`` 会先 flush 两次。旧的通用证据钩子会在
这些预备 flush 中看到原始 fileId 列表，并错误地把文件绑定到实习记录 ID；随后
正式快照再按归档记录 ID 绑定就被正确的防改绑规则拒绝。

本守卫只在预备 flush 期间暂存“纯 fileId 列表”，flush 完成后原样恢复。冻结后的
字典快照不处理，最终绑定仍由强制归档快照守卫使用稳定 archive.id 完成。
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


def _before_flush(db, flush_context, instances) -> None:
    from app.models import InternshipArchive

    stash = []
    for obj in list(db.new) + list(db.dirty):
        if not isinstance(obj, InternshipArchive):
            continue
        raw = getattr(obj, "force_evidence_file_ids", None)
        if not _is_raw_file_ids(raw):
            continue
        stash.append((obj, list(raw)))
        obj.force_evidence_file_ids = None
    if stash:
        db.info[_STASH_KEY] = stash


def _after_flush_postexec(db, flush_context) -> None:
    for obj, raw in db.info.pop(_STASH_KEY, []):
        obj.force_evidence_file_ids = raw


def _clear(db) -> None:
    db.info.pop(_STASH_KEY, None)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    # insert=True makes this run before generic file-binding listeners.
    event.listen(OrmSession, "before_flush", _before_flush, insert=True)
    event.listen(OrmSession, "after_flush_postexec", _after_flush_postexec)
    event.listen(OrmSession, "after_commit", _clear)
    event.listen(OrmSession, "after_rollback", _clear)
    _INSTALLED = True
