from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_formal_student_facade_has_no_mock_dependency_or_memory_business_writes():
    source = read("frontend/src/modules/student/api/student.api.js")

    assert "from '@/mocks/" not in source
    assert 'from "@/mocks/' not in source
    assert "withFallback(" not in source
    assert "_mockGet" not in source
    assert "_mockCreate" not in source

    # 无真实服务端合同的旧批量动作必须 fail-closed，不能修改浏览器数组后返回成功。
    assert "batchAssignClass()" in source
    assert "ACADEMIC_STATUS_CHANGE_REQUIRED" in source
    assert "batchAssignCounselor()" in source
    assert "COUNSELOR_ASSIGNMENT_REQUIRED" in source
    assert "batchRemind()" in source
    assert "NOT_IMPLEMENTED" in source
    assert "confirmImport()" in source
    assert "MOVED_TO_AUTHORITATIVE_IMPORT" in source


def test_student_frontend_never_fills_verified_bound_or_fixed_90_when_backend_fact_missing():
    source = read("frontend/src/modules/student/api/student.api.js")

    assert "identityVerifyStatus: row.identityVerifyStatus || 'NOT_CONFIGURED'" in source
    assert "accountBindStatus: row.accountBindStatus || 'UNKNOWN'" in source
    assert "dataCompleteness: 90" not in source
    assert "identityVerifyStatus: 'VERIFIED'" not in source
    assert "accountBindStatus: 'BOUND'" not in source


def test_student_backend_is_db_fail_closed_and_computes_authoritative_facts():
    source = read("backend/app/services/student_service.py")

    assert "_MOCK_STUDENTS" not in source
    assert "STUDENT_BACKEND_UNAVAILABLE" in source
    assert "if not db_enabled()" in source
    assert "StudentAccountLink" in source
    assert 'link_status[sid] = "BOUND"' in source
    assert 'link_status.get(sid, "UNBOUND")' in source
    assert 'IDENTITY_CAPABILITY_STATUS = "NOT_CONFIGURED"' in source
    assert '"dataCompleteness": completeness' in source
    assert '"missingFields": missing' in source
    assert '"supportedActions": actions' in source


def test_student_backend_clears_historical_fake_phone_placeholder_when_no_contact_fact():
    source = read("backend/app/services/student_service.py")

    assert 'item["phoneMasked"] = ""' in source
    assert '"phoneRegistered": sid in phone_present' in source


def test_student_profile_org_changes_remain_routed_to_academic_status_change():
    frontend = read("frontend/src/modules/student/api/student.api.js")
    backend = read("backend/app/services/db_service.py")

    assert "ACADEMIC_STATUS_CHANGE_REQUIRED" in frontend
    assert "学院/专业/班级属于学籍事实" in frontend
    assert "必须走学籍异动" in backend
