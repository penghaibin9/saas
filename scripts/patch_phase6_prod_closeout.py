from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1. System-generated files can join the caller's business transaction.
replace_once(
    "backend/app/services/file_service.py",
    '''    visibility: str = "PRIVATE",
    security_level: str = "NORMAL",
) -> dict:
''',
    '''    visibility: str = "PRIVATE",
    security_level: str = "NORMAL",
    db=None,
) -> dict:
''',
)
replace_once(
    "backend/app/services/file_service.py",
    '''    if db_enabled():
        from app.models.file import FileObject

        db = get_sessionmaker()()
        try:
            row = FileObject(
                tenant_id=tenant_id,
                file_key=key,
                file_name=filename,
                ext=ext,
                mime_type=detected_mime,
                size_bytes=len(data),
                sha256=meta["sha256"],
                biz_type=biz_type,
                biz_id=biz_id,
                owner_user_id=owner_id,
                created_by=owner_id,
                visibility=visibility or "PRIVATE",
                security_level=security_level or "NORMAL",
                status=FILE_STATUS_AVAILABLE,
                storage_backend=str(settings.FILE_STORAGE_BACKEND or "local").lower(),
                storage_zone="ACTIVE",
                upload_source="SYSTEM",
                scan_required=False,
                scan_status=SCAN_NOT_REQUIRED,
                available_at=now,
            )
            db.add(row)
            db.flush()
            _register_binding(
                str(row.id),
                biz_type=biz_type,
                biz_id=biz_id,
                actor=actor,
                db=db,
            )
            db.commit()
            db.refresh(row)
            meta.update(_row_meta(row))
        finally:
            db.close()
    else:
''',
    '''    if db_enabled():
        from app.models.file import FileObject

        owns_db = db is None
        working_db = db or get_sessionmaker()()
        try:
            row = FileObject(
                tenant_id=tenant_id,
                file_key=key,
                file_name=filename,
                ext=ext,
                mime_type=detected_mime,
                size_bytes=len(data),
                sha256=meta["sha256"],
                biz_type=biz_type,
                biz_id=biz_id,
                owner_user_id=owner_id,
                created_by=owner_id,
                visibility=visibility or "PRIVATE",
                security_level=security_level or "NORMAL",
                status=FILE_STATUS_AVAILABLE,
                storage_backend=str(settings.FILE_STORAGE_BACKEND or "local").lower(),
                storage_zone="ACTIVE",
                upload_source="SYSTEM",
                scan_required=False,
                scan_status=SCAN_NOT_REQUIRED,
                available_at=now,
            )
            working_db.add(row)
            working_db.flush()
            _register_binding(
                str(row.id),
                biz_type=biz_type,
                biz_id=biz_id,
                actor=actor,
                db=working_db,
            )
            if owns_db:
                working_db.commit()
                working_db.refresh(row)
            meta.update(_row_meta(row))
        except Exception:
            if owns_db:
                working_db.rollback()
            raise
        finally:
            if owns_db:
                working_db.close()
    else:
''',
)

# 2. Proposal snapshots must be visible in the exact FileVersion transaction.
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''def _store_proposal_snapshot(record: GraduationProposal, student: GraduationStudent, user: dict) -> FileObject:
    safe_student = re.sub(r"[\\/:*?\"<>|]+", "_", student.name or "学生")
    meta = file_service.store_bytes(
        _proposal_snapshot_bytes(record, student),
        f"开题报告_{safe_student}_{record.version or 'v1'}_正文快照.txt",
        biz_type="GRADUATION_MATERIAL", biz_id=str(record.id), mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE",
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
    '''def _store_proposal_snapshot(
    db, record: GraduationProposal, student: GraduationStudent, user: dict,
) -> FileObject:
    safe_student = re.sub(r"[\\/:*?\"<>|]+", "_", student.name or "学生")
    meta = file_service.store_bytes(
        _proposal_snapshot_bytes(record, student),
        f"开题报告_{safe_student}_{record.version or 'v1'}_正文快照.txt",
        biz_type="GRADUATION_MATERIAL", biz_id=str(record.id), mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE", db=db,
    )
    row = db.get(FileObject, int(meta["fileId"]))
    if not row or row.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "开题正文快照写入失败")
    return row
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''        snapshot = _store_proposal_snapshot(record, student, user)
        # snapshot 已在独立写会话提交并从该会话分离；旧业务事务处于 MySQL
        # REPEATABLE READ 时不得再次 db.get，否则可能得到 None。
''',
    '''        snapshot = _store_proposal_snapshot(db, record, student, user)
        # FileObject、FileVersion 与 FileBinding 在同一事务内可见，避免
        # MySQL REPEATABLE READ 下跨会话快照不可见。
''',
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

# 3. Sensitive routers remain ahead of legacy; legacy fixed paths remain ahead of Stage-6 dynamics.
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
    # 旧聚合 Router 中的固定路径先于 Stage-6 动态详情路径；其详情和审核函数
    # 已直接委托 Stage-6 权威 Service，因此不会绕过公共文件安全门。
    api_router.include_router(graduation.router, dependencies=d)
    api_router.include_router(graduation_material_center.router, dependencies=d)
''',
)

# 4. Production/static gates identify the actual legacy include boundary, not a tuple formatting detail.
replace_once(
    "scripts/check/check-graduation-production-gates.mjs",
    "const legacyPos = routeRegistration.indexOf('graduation, graduation_batch, graduation_student')",
    "const legacyPos = routeRegistration.indexOf('api_router.include_router(graduation.router')",
)
replace_once(
    "backend/tests/test_graduation_p0_cross_client.py",
    '''        "graduation, graduation_batch, graduation_student"
''',
    '''        "api_router.include_router(graduation.router"
''',
)
replace_once(
    "backend/tests/test_graduation_round5_contracts.py",
    '''            assert routes.index(name) < routes.index("graduation, graduation_batch")
''',
    '''            assert routes.index(name) < routes.index("api_router.include_router(graduation.router")
''',
)

# 5. Stable defense identities are returned explicitly, while retaining legacy members.
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

# 6. Batch filing may use the server-generated default archive number from the signed preview flow.
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
    '''def batch_file(archive_batch_no: str, batch_id: int, preview_token: str, user: dict) -> dict:
''',
    '''def batch_file(archive_batch_no: str | None, batch_id: int, preview_token: str, user: dict) -> dict:
''',
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

print("Stage 6 production closeout patch applied")
