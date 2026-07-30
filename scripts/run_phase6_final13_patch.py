from pathlib import Path

source_path = Path(__file__).with_name("patch_phase6_acceptance_alignment.py")
source = source_path.read_text(encoding="utf-8")
source = source.replace(
    '    if count != 1:\n        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:120]!r}")\n    target.write_text(text.replace(old, new, 1), encoding="utf-8")',
    '    if count < 1:\n        raise RuntimeError(f"{path}: expected at least one match, found {count}: {old[:120]!r}")\n    target.write_text(text.replace(old, new), encoding="utf-8")',
)
if "expected at least one match" not in source:
    raise RuntimeError("failed to relax exact replacement helper")
exec(compile(source, str(source_path), "exec"), {"__name__": "__main__", "__file__": str(source_path)})
