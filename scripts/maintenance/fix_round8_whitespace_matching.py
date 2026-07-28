from pathlib import Path


path = Path("scripts/maintenance/repair_affairs_runtime_tests_round8.py")
text = path.read_text(encoding="utf-8")
if "import re\n" not in text:
    text = text.replace("from pathlib import Path\n", "from pathlib import Path\nimport re\n", 1)

original = '''def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"round8 anchor missing: {path}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")
'''
unsafe = '''def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old in text:
        file.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    # 测试源码经格式化后只可能改变空白；忽略空白匹配，仍要求唯一命中，避免误改业务文本。
    tokens = re.split(r"(\\s+)", old)
    pattern = "".join(r"\\s+" if token and token.isspace() else re.escape(token) for token in tokens)
    matches = list(re.finditer(pattern, text, flags=re.S))
    if len(matches) != 1:
        raise RuntimeError(
            f"round8 anchor missing/ambiguous: {path}: matches={len(matches)} old={old[:120]!r}"
        )
    match = matches[0]
    file.write_text(text[:match.start()] + new + text[match.end():], encoding="utf-8")
'''
safe = '''def _whitespace_tolerant_pattern(value: str) -> str:
    """Ignore indentation changes without allowing spaces to consume neighbouring newlines."""
    parts = re.split(r"(\\n|[ \\t]+)", value)
    out = []
    for part in parts:
        if part == "\\n":
            out.append(r"[ \\t]*\\n[ \\t]*")
        elif part and all(char in " \\t" for char in part):
            out.append(r"[ \\t]+")
        else:
            out.append(re.escape(part))
    return "".join(out)


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old in text:
        file.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    pattern = _whitespace_tolerant_pattern(old)
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise RuntimeError(
            f"round8 anchor missing/ambiguous: {path}: matches={len(matches)} old={old[:120]!r}"
        )
    match = matches[0]
    file.write_text(text[:match.start()] + new + text[match.end():], encoding="utf-8")
'''

if safe not in text:
    if unsafe in text:
        text = text.replace(unsafe, safe, 1)
    elif original in text:
        text = text.replace(original, safe, 1)
    else:
        raise RuntimeError("round8 replace_once implementation anchor missing")

path.write_text(text, encoding="utf-8")
print("round8 newline-safe matcher installed", flush=True)
