from __future__ import annotations

import io
import tokenize
from pathlib import Path

ROOT = Path('.')
CONFTEST = ROOT / 'backend/tests/conftest.py'
PORTAL = ROOT / 'backend/tests/test_portal_graduation.py'

old_fixture = '''@pytest.fixture()\ndef client() -> GraduationBatchAwareClient:\n    return GraduationBatchAwareClient(TestClient(app))\n'''
new_fixture = '''@pytest.fixture()\ndef client() -> TestClient:\n    \"\"\"通用 HTTP 客户端：不得自动补参数、改身份或写业务数据。\"\"\"\n    return TestClient(app)\n\n\n@pytest.fixture()\ndef graduation_client() -> GraduationBatchAwareClient:\n    \"\"\"毕业设计旧测试显式使用的兼容客户端；禁止其他业务测试隐式继承。\"\"\"\n    return GraduationBatchAwareClient(TestClient(app))\n'''
text = CONFTEST.read_text(encoding='utf-8')
if old_fixture not in text:
    raise SystemExit('client fixture block not found')
CONFTEST.write_text(text.replace(old_fixture, new_fixture, 1), encoding='utf-8')


def rename_name_token(path: Path, old: str, new: str) -> None:
    raw = path.read_text(encoding='utf-8')
    tokens = []
    for tok in tokenize.generate_tokens(io.StringIO(raw).readline):
        if tok.type == tokenize.NAME and tok.string == old:
            tok = tokenize.TokenInfo(tok.type, new, tok.start, tok.end, tok.line)
        tokens.append(tok)
    path.write_text(tokenize.untokenize(tokens), encoding='utf-8')


for path in sorted((ROOT / 'backend/tests').glob('test_graduation*.py')):
    rename_name_token(path, 'client', 'graduation_client')

portal = PORTAL.read_text(encoding='utf-8')
replacements = {
    '"plan": "需求分析→设计→实现→测试", "outcome": "系统+论文", "attachments": []})':
        '"plan": "需求分析→设计→实现→测试", "outcome": "系统+论文", "attachments": [], "expectedVersion": 0})',
    'json={"background": "", "plan": "", "outcome": ""})':
        'json={"background": "", "plan": "", "outcome": "", "expectedVersion": 0})',
    'json={"background": "x内容"})':
        'json={"background": "x内容", "expectedVersion": 0})',
    'json={"finalType": "初稿", "attachments": [fid]})':
        'json={"finalType": "初稿", "attachments": [fid], "expectedVersion": 0})',
    'json={"finalType": "初稿", "attachments": []})':
        'json={"finalType": "初稿", "attachments": [], "expectedVersion": 0})',
    'json={"finalType": "xyz", "attachments": ["f1"]})':
        'json={"finalType": "xyz", "attachments": ["f1"], "expectedVersion": 0})',
}
for old, new in replacements.items():
    if old not in portal:
        raise SystemExit(f'portal pattern not found: {old}')
    portal = portal.replace(old, new, 1)
PORTAL.write_text(portal, encoding='utf-8')

guard = ROOT / 'backend/tests/test_pytest_client_contract.py'
guard.write_text('''\"\"\"Shared pytest client must never mutate requests or fabricate domain data.\"\"\"\nfrom fastapi.testclient import TestClient\n\n\ndef test_shared_client_is_plain_testclient(client):\n    assert type(client) is TestClient\n    assert not hasattr(client, \"_active_batch_id\")\n''', encoding='utf-8')
