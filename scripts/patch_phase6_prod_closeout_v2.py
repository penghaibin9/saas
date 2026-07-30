from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# File service: optional caller-owned transaction for trusted system snapshots.
replace_once(
    "backend/app/services/file_service.py",
    '''def store_bytes(
    data: bytes,
    filename: str,
    biz_type: str = "ATTACHMENT",
    mime_type: str | None = None,
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "PRIVATE",
    security_level: str = "NORMAL",
) -> dict:
''',
    '''def store_bytes(
    data: bytes,
    filename: str,
    biz_type: str = "ATTACHMENT",
    mime_type: str | None = None,
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "PRIVATE",
    security_level: str = "NORMAL",
    db=None,
) -> dict:
''',
)
replace_once(
    "backend/app/services/file_service.py",
    '''        db = get_sessionmaker()()
        try:
            row = FileObject(
''',
    '''        owns_db = db is None
        working_db = db or get_sessionmaker()()
        try:
            row = FileObject(
''',
)
replace_once("backend/app/services/file_service.py", "            db.add(row)\n            db.flush()\n", "            working_db.add(row)\n            working_db.flush()\n")
replace_once("backend/app/services/file_service.py", "                db=db,\n            )\n            db.commit()\n            db.refresh(row)\n", "                db=working_db,\n            )\n            if owns_db:\n                working_db.commit()\n                working_db.refresh(row)\n")
replace_once(
    "backend/app/services/file_service.py",
    '''        finally:
            db.close()
    else:
''',
    '''        except Exception:
            if owns_db:
                working_db.rollback()
            raise
        finally:
            if owns_db:
                working_db.close()
    else:
''',
)

# Proposal and template system snapshots share the FileVersion transaction.
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    "def _store_proposal_snapshot(record: GraduationProposal, student: GraduationStudent, user: dict) -> FileObject:\n",
    "def _store_proposal_snapshot(db, record: GraduationProposal, student: GraduationStudent, user: dict) -> FileObject:\n",
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE",
    )
    from app.db.session import get_sessionmaker
    lookup = get_sessionmaker()()
    try:
        row = lookup.get(FileObject, int(meta["fileId"]))
        if not row or row.tenant_id != _tid():
            raise AppException("DATA_CONFLICT", "开题正文快照写入失败")
        lookup.expunge(row)
        return row
    finally:
        lookup.close()
''',
    '''        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE", db=db,
    )
    row = db.get(FileObject, int(meta["fileId"]))
    if not row or row.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "开题正文快照写入失败")
    return row
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    "        snapshot = _store_proposal_snapshot(record, student, user)\n",
    "        snapshot = _store_proposal_snapshot(db, record, student, user)\n",
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''                user=user, visibility="BIZ_SCOPED", security_level="NORMAL",
            )
            file_obj = db.get(FileObject, int(meta["fileId"]))
''',
    '''                user=user, visibility="BIZ_SCOPED", security_level="NORMAL", db=db,
            )
            file_obj = db.get(FileObject, int(meta["fileId"]))
''',
)

# Route ordering: exact sensitive routes, then legacy fixed routes, then Stage-6 dynamic routes.
replace_once(
    "backend/app/api/v1/route_registration.py",
    '''    api_router.include_router(graduation_p0_guard.router, dependencies=d)
    # 先注册旧聚合 Router 中的 /proposals/stats、/finals/stats 等固定路径；
    # 其同 URL 详情/审核函数已直接委托 Stage-6 权威 Service，不再依赖路由抢占。
    api_router.include_router(graduation.router, dependencies=d)
    api_router.include_router(graduation_material_center.router, dependencies=d)
    api_router.include_router(graduation_sensitive_router.router, dependencies=d)
    api_router.include_router(graduation_archive_sensitive_router.router, dependencies=d)
    api_router.include_router(graduation_material_sensitive_router.router, dependencies=d)
''',
    '''    api_router.include_router(graduation_p0_guard.router, dependencies=d)
    api_router.include_router(graduation_sensitive_router.router, dependencies=d)
    api_router.include_router(graduation_archive_sensitive_router.router, dependencies=d)
    api_router.include_router(graduation_material_sensitive_router.router, dependencies=d)
    # Legacy fixed paths precede Stage-6 dynamic detail paths; legacy detail/review
    # endpoints already delegate to the authoritative public-version service.
    api_router.include_router(graduation.router, dependencies=d)
    api_router.include_router(graduation_material_center.router, dependencies=d)
''',
)
replace_once(
    "scripts/check/check-graduation-production-gates.mjs",
    "const legacyPos = routeRegistration.indexOf('graduation, graduation_batch, graduation_student')",
    "const legacyPos = routeRegistration.indexOf('api_router.include_router(graduation.router')",
)
replace_once(
    "backend/tests/test_graduation_p0_cross_client.py",
    '        "graduation, graduation_batch, graduation_student"\n',
    '        "api_router.include_router(graduation.router"\n',
)
replace_once(
    "backend/tests/test_graduation_round5_contracts.py",
    '            assert routes.index(name) < routes.index("graduation, graduation_batch")\n',
    '            assert routes.index(name) < routes.index("api_router.include_router(graduation.router")\n',
)

# Stable defense identities are explicit in the DTO.
replace_once(
    "backend/app/modules/graduation/services/graduation_service.py",
    '''            "members": members or (g.members_json or []),
            "secretary": g.secretary or "待指定",
''',
    '''            "members": members or (g.members_json or []),
            "memberDetails": members,
            "secretary": g.secretary or "待指定",
''',
)

# Signed batch preview may use the server-generated archive number.
replace_once(
    "backend/app/modules/graduation/routers/graduation_material_center.py",
    '''    archive_no = str((body or {}).get("archiveBatchNo") or "").strip()
    preview_token = str((body or {}).get("previewToken") or "").strip()
    if not archive_no or not preview_token:
        raise AppException("VALIDATION_ERROR", "归档批次号和预览凭证不能为空")
    legacy_result = center.batch_file(archive_no, batchId, preview_token, user)
''',
    '''    archive_no = str((body or {}).get("archiveBatchNo") or "").strip()
    preview_token = str((body or {}).get("previewToken") or "").strip()
    if not preview_token:
        raise AppException("VALIDATION_ERROR", "执行前必须先完成归档预览")
    legacy_result = center.batch_file(archive_no or None, batchId, preview_token, user)
    archive_no = str(legacy_result.get("archiveBatchNo") or archive_no).strip()
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    "def batch_file(archive_batch_no: str, batch_id: int, preview_token: str, user: dict) -> dict:\n",
    "def batch_file(archive_batch_no: str | None, batch_id: int, preview_token: str, user: dict) -> dict:\n",
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''    archive_no = _archive_no(archive_batch_no)
    with session() as db:
        batch = archive_service._require_batch(db, batch_id)
        snapshot = consistency._snapshot(db, batch, "FILE", lock=True)
        snapshot["archiveBatchNo"] = archive_no
        consistency._verify_token(preview_token, consistency._token_payload("FILE", batch, snapshot))
''',
    '''    archive_no = _archive_no(archive_batch_no or f"GDARCH-{datetime.now():%Y%m%d}")
    with session() as db:
        batch = archive_service._require_batch(db, batch_id)
        snapshot = consistency._snapshot(db, batch, "FILE", lock=True)
        consistency._verify_token(preview_token, consistency._token_payload("FILE", batch, snapshot))
''',
)

print("Stage 6 production closeout v2 patch applied")
