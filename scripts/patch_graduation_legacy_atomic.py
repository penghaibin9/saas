from pathlib import Path

path = Path("backend/app/modules/graduation/materials/command_service.py")
text = path.read_text(encoding="utf-8")
old_query = '''    file_obj = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
        FileObject.is_deleted.is_(False),
    )).first()
'''
new_query = '''    file_obj = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
        FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
'''
if text.count(old_query) != 1:
    raise SystemExit(f"legacy FileObject lock replacement count={text.count(old_query)}")
text = text.replace(old_query, new_query, 1)
old_check = '''    _validate_file(item, file_obj)
    assert_file_ready_for_business(str(file_obj.id), user=user)
    version = _append_version(
'''
new_check = '''    _assert_locked_file_ready(item, file_obj, user)
    version = _append_version(
'''
if text.count(old_check) != 1:
    raise SystemExit(f"legacy locked security replacement count={text.count(old_check)}")
path.write_text(text.replace(old_check, new_check, 1), encoding="utf-8")
