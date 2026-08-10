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

    assert "batchAssignClass()" in source
    assert "ACADEMIC_STATUS_CHANGE_REQUIRED" in source
    assert "batchAssignCounselor()" in source
    assert "COUNSELOR_ASSIGNMENT_REQUIRED" in source
    assert "batchRemind()" in source
    assert "NOT_IMPLEMENTED" in source
    assert "confirmImport()" in source
    assert "MOVED_TO_AUTHORITATIVE_IMPORT" in source


def test_formal_student_route_graph_cannot_import_mock_directly():
    roots = [
        ROOT / "frontend/src/views/admin/student",
        ROOT / "frontend/src/modules/student",
    ]
    offenders = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".vue", ".js", ".ts"}:
                continue
            lower_parts = {part.lower() for part in path.parts}
            lower_name = path.name.lower()
            if "mock" in lower_parts or ".mock." in lower_name or ".example." in lower_name:
                continue
            source = path.read_text(encoding="utf-8")
            if "@/mocks/" in source or "../mocks/" in source or "/mock/" in source or "withFallback(" in source:
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"正式学生路由仍可直达 mock/fallback: {offenders}"


def test_legacy_student_provider_delegates_to_real_facade():
    provider = read("frontend/src/modules/student/provider/student.provider.js")

    assert "import studentApi from '../api/student.api'" in provider
    assert "student.api.mock" not in provider
    assert "const impl = mockApi" not in provider


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


def test_student_dashboard_uses_server_authoritative_summary_and_scope_timestamp():
    api = read("backend/app/api/v1/student.py")
    service = read("backend/app/services/student_service.py")
    frontend = read("frontend/src/modules/student/api/student.api.js")

    assert '@router.get("/summary"' in api
    assert "svc.summary(class_ids=class_ids, student_ids=student_ids)" in api
    assert "def summary(*, class_ids=None, student_ids=None)" in service
    assert '"totalStudents": total' in service
    assert '"accountBinding": {' in service
    assert '"scopeType": scope_type' in service
    assert '"asOf": datetime.utcnow()' in service
    assert "request('/students/summary')" in frontend
    assert "asOf: summary?.asOf" in frontend


def test_identity_filter_is_server_side_and_never_page_local():
    api = read("backend/app/api/v1/student.py")
    frontend = read("frontend/src/modules/student/api/student.api.js")

    assert "identityVerifyStatus: params.identityVerifyStatus" in frontend
    assert "rows.filter((row) => row.identityVerifyStatus" not in frontend
    assert 'requested_identity != "NOT_CONFIGURED"' in api
    assert "paginate([], 0, page, pageSize)" in api


def test_student_writes_use_stable_idempotency_header_and_server_guard():
    client = read("frontend/src/services/http/client.js")
    frontend = read("frontend/src/modules/student/api/student.api.js")
    api = read("backend/app/api/v1/student.py")

    assert "headers: extraHeaders" in client
    assert "...(extraHeaders || {})" in client
    assert "function idempotencyHeaders" in frontend
    assert "'Idempotency-Key'" in frontend
    assert "idempotencyHeaders('create'" in frontend
    assert "idempotencyHeaders('update'" in frontend
    assert "idempotencyHeaders('void'" in frontend
    assert "idempotencyHeaders('restore'" in frontend
    assert "idempotency_guard" in api
    assert "require_store=True" in api


def test_unimplemented_student_business_actions_are_not_advertised_as_enabled():
    source = read("frontend/src/modules/student/api/student.api.js")

    assert "importStudents: action(false, false" in source
    assert "changeStatus: action(false, false" in source
    assert "batchChangeStatus: action(false, false" in source
    assert "exportStatusRecords: action(false, false" in source
