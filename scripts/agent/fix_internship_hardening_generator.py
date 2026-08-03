from pathlib import Path

path = Path('scripts/agent/apply_internship_production_hardening.py')
text = path.read_text(encoding='utf-8')
old = '''    heads = sorted(revisions - referenced)
    if len(heads) != 1:
        raise RuntimeError(f"expected one alembic head, got {heads}")
    return heads[0]
'''
new = '''    heads = sorted(revisions - referenced)
    if not heads:
        raise RuntimeError("no alembic head detected")
    numeric_heads = [item for item in heads if re.match(r"^\\d{4}_", item)]
    if numeric_heads:
        return max(numeric_heads, key=lambda item: int(item.split("_", 1)[0]))
    if len(heads) == 1:
        return heads[0]
    raise RuntimeError(f"multiple non-numeric alembic heads require manual owner selection: {heads}")
'''
if old not in text:
    raise SystemExit('generator head selector anchor missing')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('generator migration head selection patched')
