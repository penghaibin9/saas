from pathlib import Path

path = Path(__file__).with_name("patch_phase6_prod_closeout.py")
text = path.read_text(encoding="utf-8")
start_marker = """replace_once(
    \"backend/app/services/file_service.py\",
    '''        db = get_sessionmaker()()
"""
end_marker = "\n# Proposal and template system snapshots share the FileVersion transaction."
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("unable to locate store_bytes DB patch section")
replacement = """replace_once(
    \"backend/app/services/file_service.py\",
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
                sha256=meta[\"sha256\"],
                biz_type=biz_type,
                biz_id=biz_id,
                owner_user_id=owner_id,
                created_by=owner_id,
                visibility=visibility or \"PRIVATE\",
                security_level=security_level or \"NORMAL\",
                status=FILE_STATUS_AVAILABLE,
                storage_backend=str(settings.FILE_STORAGE_BACKEND or \"local\").lower(),
                storage_zone=\"ACTIVE\",
                upload_source=\"SYSTEM\",
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
                sha256=meta[\"sha256\"],
                biz_type=biz_type,
                biz_id=biz_id,
                owner_user_id=owner_id,
                created_by=owner_id,
                visibility=visibility or \"PRIVATE\",
                security_level=security_level or \"NORMAL\",
                status=FILE_STATUS_AVAILABLE,
                storage_backend=str(settings.FILE_STORAGE_BACKEND or \"local\").lower(),
                storage_zone=\"ACTIVE\",
                upload_source=\"SYSTEM\",
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
"""
text = text[:start] + replacement + text[end:]
needle = '            assert routes.index(name) < routes.index("graduation, graduation_batch")'
if text.count(needle) != 1:
    raise RuntimeError(f"round5 matcher expected once, found {text.count(needle)}")
text = text.replace(needle, '        assert routes.index(name) < routes.index("graduation, graduation_batch")', 1)
path.write_text(text, encoding="utf-8")
print("Scoped store_bytes and Round5 patch sections")
