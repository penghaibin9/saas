from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

service_path = ROOT / "backend/app/modules/internship/services/internship_evidence_package_service.py"
text = service_path.read_text(encoding="utf-8")
old = '''            generated_at=datetime.utcnow(), row_count=len(records), file_count=0,
            source_module="system",
        )
'''
new = '''            generated_at=datetime.utcnow(), row_count=len(records), file_count=0,
        )
'''
if old not in text:
    if "source_module=\"system\"" in text:
        raise SystemExit("unexpected evidence package source_module anchor")
else:
    text = text.replace(old, new, 1)
    service_path.write_text(text, encoding="utf-8")

init_text = (ROOT / "backend/app/modules/internship/services/__init__.py").read_text(encoding="utf-8")
if "InternshipEvidencePackage.source_module" in init_text or "_InternshipEvidencePackage.source_module" in init_text:
    raise SystemExit("non-persistent ORM monkey patch remains")
if "source_module=\"system\"" in text:
    raise SystemExit("fake evidence package constructor field remains")
ast.parse(text, filename=str(service_path))

test_path = ROOT / "backend/tests/test_internship_evidence_package_contract_static.py"
test_path.write_text('''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_evidence_package_has_no_non_persistent_source_module_shim():
    package_service = (ROOT / "backend/app/modules/internship/services/internship_evidence_package_service.py").read_text(encoding="utf-8")
    service_init = (ROOT / "backend/app/modules/internship/services/__init__.py").read_text(encoding="utf-8")
    assert 'source_module="system"' not in package_service
    assert "InternshipEvidencePackage.source_module" not in service_init
    assert "_InternshipEvidencePackage.source_module" not in service_init
    assert "package_type=typ" in package_service
    assert '"packageType": typ' in package_service
''', encoding="utf-8")
print("evidence package fake field removed")
