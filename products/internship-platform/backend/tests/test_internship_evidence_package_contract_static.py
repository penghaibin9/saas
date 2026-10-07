from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_evidence_package_has_no_non_persistent_source_module_shim():
    package_service = (ROOT / "backend/app/modules/internship/services/internship_evidence_package_service.py").read_text(encoding="utf-8")
    service_init = (ROOT / "backend/app/modules/internship/services/__init__.py").read_text(encoding="utf-8")
    assert 'source_module="system"' not in package_service
    assert "InternshipEvidencePackage.source_module" not in service_init
    assert "_InternshipEvidencePackage.source_module" not in service_init
    assert "package_type=typ" in package_service
    assert '"packageType": typ' in package_service
