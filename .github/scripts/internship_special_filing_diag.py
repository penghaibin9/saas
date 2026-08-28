from pathlib import Path

path = Path("tests/test_internship_v93_special_filing_review_flow.py")
text = path.read_text(encoding="utf-8")
old = '''    created = svc.create({
        "internshipId": str(ids["internship"]), "filingType": "OTHER",
        "triggerReason": "企业临时调整岗位安排，需补充备案说明情况。",
        "fileIds": [ids["file"]],
    }, user=REQUESTER)
    return created["id"], created["version"]
'''
new = '''    created = svc.create({
        "internshipId": str(ids["internship"]), "filingType": "OTHER",
        "triggerReason": "企业临时调整岗位安排，需补充备案说明情况。",
        "fileIds": [ids["file"]],
    }, user=REQUESTER)

    from app.core.context import current_tenant_id
    from app.models.file import FileBinding, FileObject
    from app.services import file_service
    from app.services.file_access_resolvers import _owner_allows, scoped_binding_resolver
    from app.services.file_access_service import (
        _RESOLVERS,
        _actor_id,
        authorize_file_object,
        resolver_registry_snapshot,
    )
    from app.services.message_identity import resolve_message_user_id
    from sqlalchemy import select

    diag_db = _session()
    try:
        file_obj = diag_db.scalar(select(FileObject).where(FileObject.id == int(ids["file"])))
        bindings = list(diag_db.scalars(select(FileBinding).where(
            FileBinding.file_id == int(ids["file"]),
            FileBinding.is_deleted.is_(False),
        )).all())
        print("SPECIAL_FILING_DIAG tenant", current_tenant_id())
        print("SPECIAL_FILING_DIAG actor", REQUESTER, "actor_id", _actor_id(REQUESTER),
              "resolved", resolve_message_user_id(REQUESTER))
        print("SPECIAL_FILING_DIAG file", {
            "id": getattr(file_obj, "id", None),
            "tenant_id": getattr(file_obj, "tenant_id", None),
            "owner_user_id": getattr(file_obj, "owner_user_id", None),
            "created_by": getattr(file_obj, "created_by", None),
            "biz_type": getattr(file_obj, "biz_type", None),
            "biz_id": getattr(file_obj, "biz_id", None),
            "visibility": getattr(file_obj, "visibility", None),
            "status": getattr(file_obj, "status", None),
            "scan_status": getattr(file_obj, "scan_status", None),
            "is_deleted": getattr(file_obj, "is_deleted", None),
        })
        print("SPECIAL_FILING_DIAG bindings", [{
            "id": b.id,
            "biz_type": b.biz_type,
            "biz_id": b.biz_id,
            "subject_type": b.subject_type,
            "subject_id": b.subject_id,
            "batch_id": b.batch_id,
            "status": b.status,
            "scope_json": b.scope_json,
        } for b in bindings])
        print("SPECIAL_FILING_DIAG registry", resolver_registry_snapshot())
        registered = _RESOLVERS.get("INTERNSHIP")
        print("SPECIAL_FILING_DIAG registered_intership", registered, getattr(registered, "__module__", None), getattr(registered, "__name__", None))
        print("SPECIAL_FILING_DIAG owner_allows", _owner_allows(file_obj, REQUESTER))
        print("SPECIAL_FILING_DIAG direct_scoped", scoped_binding_resolver(diag_db, file_obj, bindings, REQUESTER, "meta"))
        for action in ("meta", "bind", "submit"):
            try:
                print("SPECIAL_FILING_DIAG authorize_object", action,
                      authorize_file_object(file_obj, bindings, REQUESTER, action, db=diag_db))
            except Exception as exc:
                print("SPECIAL_FILING_DIAG authorize_object_exc", action, repr(exc))
            try:
                print("SPECIAL_FILING_DIAG legacy_authorize", action,
                      file_service.authorize_file_access(REQUESTER, file_obj, action))
            except Exception as exc:
                print("SPECIAL_FILING_DIAG legacy_authorize_exc", action, repr(exc))
        try:
            print("SPECIAL_FILING_DIAG meta_no_ready",
                  file_service.get_file_meta(str(ids["file"]), user=REQUESTER, require_ready=False))
        except Exception as exc:
            print("SPECIAL_FILING_DIAG meta_no_ready_exc", repr(exc))
        try:
            print("SPECIAL_FILING_DIAG meta_ready",
                  file_service.get_file_meta(str(ids["file"]), user=REQUESTER))
        except Exception as exc:
            print("SPECIAL_FILING_DIAG meta_ready_exc", repr(exc))
    finally:
        diag_db.close()
    return created["id"], created["version"]
'''
actual = text.count(old)
if actual != 1:
    raise SystemExit(f"diagnostic anchor expected once, got {actual}")
path.write_text(text.replace(old, new), encoding="utf-8")
print("special filing diagnostic injected")
