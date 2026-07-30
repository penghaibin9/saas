from pathlib import Path

path = Path(__file__).with_name("patch_phase6_prod_closeout.py")
text = path.read_text(encoding="utf-8")
old = '''    '    security_level: str = "NORMAL",\\n) -> dict:\\n',
    '    security_level: str = "NORMAL",\\n    db=None,\\n) -> dict:\\n',
'''
new = '''    ''' + "'''" + '''def store_bytes(
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
''' + "'''" + ''',
    ''' + "'''" + '''def store_bytes(
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
''' + "'''" + ''',
'''
if text.count(old) != 1:
    raise RuntimeError(f"patch bootstrap expected one signature block, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Narrowed store_bytes signature patch")
