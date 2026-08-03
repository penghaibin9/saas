from pathlib import Path

path = Path("backend/tests/test_graduation_material_closeout_regressions.py")
text = path.read_text(encoding="utf-8")
old = '''def test_student_mobile_review_is_real_403_and_handler_never_runs(monkeypatch):
    from app.api.v1 import mobile_graduation_material_center as mobile
    from app.core.security import get_current_user

    called = {"value": False}

    def forbidden_handler(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("student request reached material review command")

    monkeypatch.setattr(mobile.commands, "review_material", forbidden_handler)
    app = FastAPI()
    app.include_router(mobile.router)
    app.dependency_overrides[get_current_user] = _student
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/mobile/graduation/material-center/materials/1/review",
            json={"action": "APPROVE", "fileVersionId": 2, "expectedVersion": 3},
        )
    assert response.status_code == 403
    assert called["value"] is False
'''
new = '''def test_student_mobile_review_is_real_403_and_handler_never_runs(monkeypatch):
    from app.api.v1 import mobile_graduation_material_center as mobile
    from app.core.security import get_current_user
    from app.main import app as production_app

    called = {"value": False}

    def forbidden_handler(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("student request reached material review command")

    monkeypatch.setattr(mobile.commands, "review_material", forbidden_handler)
    production_app.dependency_overrides[get_current_user] = _student
    try:
        with TestClient(production_app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/mobile/graduation/material-center/materials/1/review",
                json={"action": "APPROVE", "fileVersionId": 2, "expectedVersion": 3},
            )
    finally:
        production_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    assert called["value"] is False
'''
if text.count(old) != 1:
    raise SystemExit(f"real-route test replacement count={text.count(old)}")
text = text.replace(old, new, 1)
old_assert = '    assert command.count("_assert_locked_file_ready(item, file_obj, user)") >= 4\n'
new_assert = '''    append_calls = command.count("_append_version(") - 1  # exclude the function definition
    locked_checks = command.count("_assert_locked_file_ready(item, file_obj, user)")
    assert append_calls == locked_checks == 3
'''
if text.count(old_assert) != 1:
    raise SystemExit(f"locked-writer assertion replacement count={text.count(old_assert)}")
path.write_text(text.replace(old_assert, new_assert, 1), encoding="utf-8")
