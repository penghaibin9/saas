from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDENT_API = ROOT / "app" / "api" / "v1" / "student.py"
FRONTEND_API = ROOT.parent / "frontend" / "src" / "modules" / "student" / "api" / "student.api.js"


def test_stage_b_identity_capability_is_server_owned_and_route_order_is_safe():
    backend = STUDENT_API.read_text(encoding="utf-8")
    frontend = FRONTEND_API.read_text(encoding="utf-8")

    fixed_route = '@router.get("/identity-records", summary="身份核验能力与记录")'
    dynamic_route = '@router.get("/{student_id}", summary="学生 360 详情")'
    assert fixed_route in backend
    assert dynamic_route in backend
    assert backend.index(fixed_route) < backend.index(dynamic_route)

    endpoint = backend[backend.index(fixed_route):backend.index(dynamic_route)]
    assert 'if not _can_view_profile(user):' in endpoint
    assert 'http_status=403' in endpoint
    assert '"capabilityStatus": "NOT_CONFIGURED"' in endpoint
    assert '当前仓库尚未接入第三方实名/人脸核验 provider' in endpoint

    assert "request('/students/identity-records'" in frontend
    get_identity = frontend[frontend.index('async getIdentityRecords(params = {})'):frontend.index('reviewIdentityRecord()')]
    assert "capabilityStatus: 'NOT_CONFIGURED'" not in get_identity
    assert "capabilityStatus: String(data?.capabilityStatus || 'ERROR').toUpperCase()" in get_identity
