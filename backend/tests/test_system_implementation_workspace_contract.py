"""SYS-02 实施项目、开局、变更与验收（真库）。

对应必测 SYS02-T01～T04：
状态机非法转换拒绝 / 未购买模块不能安装启用 / 同一快照重复应用幂等 / 验收后普通修改拒绝。
"""
import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.services import platform_service as platform
from app.services import system_implementation_service as impl

MAIN_TENANT_ID = 1000000000000000001
ADMIN = {"userId": "db-1", "realName": "实施管理员", "currentRoleCode": "SCHOOL_ADMIN"}


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


@pytest.fixture()
def tenant_ctx(db_mode):
    """所有实施接口都读上下文租户，这里显式钉住，并建好真实租户行。"""
    from app.models import Tenant

    with _session() as db:
        if db.get(Tenant, MAIN_TENANT_ID) is None:
            db.add(Tenant(id=MAIN_TENANT_ID, tenant_code="demo",
                          school_name="实施测试学校", status="ACTIVE"))
            db.commit()
    platform.put_config_json(MAIN_TENANT_ID, "TENANT_META", "-",
                             {"status": "active", "packageCode": "professional"})
    set_tenant({"tenantId": str(MAIN_TENANT_ID)})
    try:
        yield MAIN_TENANT_ID
    finally:
        set_tenant(None)


def _new_project(profile: str = "HIGHER_VOCATIONAL") -> int:
    impl.create_project(ADMIN, {"projectName": "实施验收测试项目", "profileCode": profile})
    current = impl.current_project()
    return int(current["id"])


def _project_row(project_id: int):
    from app.models import SystemImplementationProject

    with _session() as db:
        return db.get(SystemImplementationProject, int(project_id))


def _set_status(project_id: int, status: str) -> None:
    from app.models import SystemImplementationProject

    with _session() as db:
        row = db.get(SystemImplementationProject, int(project_id))
        row.status = status
        db.commit()


# ── SYS02-T01：状态机非法转换必须被拒绝 ─────────────────────────────────────
def test_t01_illegal_state_transitions_are_rejected(tenant_ctx):
    project_id = _new_project()

    # 没预览就应用
    with pytest.raises(AppException) as no_preview:
        impl.apply_snapshot(ADMIN, project_id, {"confirmText": "确认应用", "reason": "跳过预览直接应用"})
    assert no_preview.value.code == "DATA_CONFLICT"

    # 没应用就跑上线检查
    with pytest.raises(AppException) as no_apply:
        impl.run_checks(ADMIN, project_id)
    assert no_apply.value.code == "DATA_CONFLICT"

    # 没通过检查就验收
    with pytest.raises(AppException) as no_check:
        impl.accept_project(ADMIN, project_id, {"confirmText": "确认验收", "comment": "还没检查就验收"})
    assert no_check.value.code == "DATA_CONFLICT"

    # 确认文案错了也不许过
    impl.preview_project(ADMIN, project_id)
    with pytest.raises(AppException):
        impl.apply_snapshot(ADMIN, project_id, {"confirmText": "应用", "reason": "确认文案不对"})


def test_t01b_preview_requires_configurable_state(tenant_ctx):
    project_id = _new_project()
    impl.preview_project(ADMIN, project_id)
    _set_status(project_id, "VERIFYING")
    with pytest.raises(AppException) as caught:
        impl.preview_project(ADMIN, project_id)
    assert caught.value.code == "DATA_CONFLICT"


# ── SYS02-T02：未购买模块不能安装启用 ───────────────────────────────────────
def test_t02_unentitled_module_cannot_be_installed(tenant_ctx):
    # 高职标准版默认勾选毕设；把平台侧的毕设功能关掉
    platform.put_config_json(MAIN_TENANT_ID, "FEATURES", "-", {"graduation": False})
    project_id = _new_project("HIGHER_VOCATIONAL")

    preview = impl.preview_project(ADMIN, project_id)
    entitlement = preview["preview"]["entitlement"]
    assert entitlement["blocked"] is True
    assert "GRADUATION" in entitlement["blockedModules"]
    assert preview["preview"]["blocked"] is True, "未授权必须让预览整体阻断"

    with pytest.raises(AppException) as caught:
        impl.apply_snapshot(ADMIN, project_id, {"confirmText": "确认应用", "reason": "尝试安装未购买模块"})
    assert caught.value.code == "DATA_CONFLICT"

    # 即使强行把状态摆到 PREVIEW_READY 且预览未标阻断，应用前也会重算授权
    from app.models import SystemImplementationProject

    with _session() as db:
        row = db.get(SystemImplementationProject, project_id)
        payload = dict(row.preview_json or {})
        payload["blocked"] = False
        row.preview_json = payload
        row.status = "PREVIEW_READY"
        db.commit()
    with pytest.raises(AppException) as recheck:
        impl.apply_snapshot(ADMIN, project_id, {"confirmText": "确认应用", "reason": "绕过预览阻断再试"})
    assert "未获得平台商业授权" in recheck.value.message
    assert "GRADUATION" in recheck.value.message

    assert _project_row(project_id).status != "APPLIED", "未授权不得留下任何安装痕迹"


def test_t02b_entitled_modules_pass_the_gate(tenant_ctx):
    platform.put_config_json(MAIN_TENANT_ID, "FEATURES", "-", {})
    project_id = _new_project("HIGHER_VOCATIONAL")
    preview = impl.preview_project(ADMIN, project_id)
    entitlement = preview["preview"]["entitlement"]
    assert entitlement["blocked"] is False
    assert {row["module"] for row in entitlement["items"]} >= {"GRADUATION", "INTERNSHIP"}
    assert all(row["capabilityKey"] for row in entitlement["items"]), "每个实施模块都要映射到能力键"


def test_t02c_entitlement_read_failure_blocks_install(tenant_ctx, monkeypatch):
    """授权状态读不出来时必须拒绝安装，绝不能默认放行。"""
    from app.services import tenant_capability_setting_service as caps

    project_id = _new_project()
    monkeypatch.setattr(caps, "capability_states",
                        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("capability store down")))
    from app.models import SystemImplementationSection

    with _session() as db:
        sections = db.scalars(
            __import__("sqlalchemy").select(SystemImplementationSection).where(
                SystemImplementationSection.project_id == project_id)).all()
    report = impl._entitlement_report(sections, MAIN_TENANT_ID)
    assert report["blocked"] is True
    assert report["error"]


# ── SYS02-T03：同一快照重复应用幂等 ─────────────────────────────────────────
def test_t03_apply_is_idempotent_for_the_same_snapshot(tenant_ctx):
    from app.models import SystemPresetInstallation

    project_id = _new_project()
    preview = impl.preview_project(ADMIN, project_id)
    key = preview["idempotencyKey"]
    assert key and key == preview["previewHash"]

    first = impl.apply_snapshot(ADMIN, project_id, {
        "confirmText": "确认应用", "reason": "首次应用", "idempotencyKey": key})
    assert first["idempotent"] is False
    installation_no = first["installationNo"]

    second = impl.apply_snapshot(ADMIN, project_id, {
        "confirmText": "确认应用", "reason": "重复提交（网络重试）", "idempotencyKey": key})
    assert second["idempotent"] is True
    assert second["installationNo"] == installation_no, "同一快照必须返回同一安装版本"

    with _session() as db:
        rows = db.scalars(
            __import__("sqlalchemy").select(SystemPresetInstallation).where(
                SystemPresetInstallation.tenant_id == MAIN_TENANT_ID,
                SystemPresetInstallation.is_deleted.is_(False))).all()
    assert len(rows) == 1, "重复应用不得产生第二份安装"


def test_t03b_stale_idempotency_key_is_rejected(tenant_ctx):
    project_id = _new_project()
    impl.preview_project(ADMIN, project_id)
    with pytest.raises(AppException) as caught:
        impl.apply_snapshot(ADMIN, project_id, {
            "confirmText": "确认应用", "reason": "拿着别的快照哈希来应用",
            "idempotencyKey": "0" * 64})
    assert caught.value.code == "DATA_CONFLICT"
    assert "快照" in caught.value.message


def test_t03c_preview_exposes_impact_objects(tenant_ctx):
    project_id = _new_project()
    preview = impl.preview_project(ADMIN, project_id)["preview"]
    impact = preview["impact"]
    assert impact["workflows"]["planned"] > 0
    assert impact["workbenches"]["planned"] > 0
    assert impact["selectedModules"], "影响预览必须说明本次涉及哪些模块"

    impl.apply_snapshot(ADMIN, project_id, {"confirmText": "确认应用", "reason": "应用以验证影响口径"})
    from app.models import WorkflowDefinition

    with _session() as db:
        installed = db.scalars(
            __import__("sqlalchemy").select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == MAIN_TENANT_ID,
                WorkflowDefinition.is_deleted.is_(False))).all()
    assert len(installed) == len(impact["workflows"]["toCreate"]), "预告要装几个，就真的装几个"


# ── SYS02-T04：验收封板后普通修改一律拒绝 ───────────────────────────────────
def test_t04_after_acceptance_only_change_projects_are_allowed(tenant_ctx):
    project_id = _new_project()
    impl.preview_project(ADMIN, project_id)
    impl.apply_snapshot(ADMIN, project_id, {"confirmText": "确认应用", "reason": "应用后走验收"})
    _set_status(project_id, "ACCEPTED")

    with pytest.raises(AppException) as edit:
        impl.save_section(ADMIN, project_id, "school_opening",
                          {"config": {"schoolLevel": "HIGHER_VOCATIONAL",
                                      "deliveryMode": "STANDARD_WEEK", "targetDays": 7}})
    assert edit.value.code == "DATA_CONFLICT"

    with pytest.raises(AppException) as re_preview:
        impl.preview_project(ADMIN, project_id)
    assert "变更项目" in re_preview.value.message

    with pytest.raises(AppException) as re_apply:
        impl.apply_snapshot(ADMIN, project_id, {"confirmText": "确认应用", "reason": "封板后再应用"})
    assert "变更项目" in re_apply.value.message

    with pytest.raises(AppException) as mapping:
        impl.apply_mapping(ADMIN, project_id, {"confirmText": "确认安装组织与角色", "reason": "封板后装组织"})
    assert mapping.value.code == "DATA_CONFLICT"

    from app.services import runtime_preset_install_service as runtime

    with pytest.raises(AppException) as preset:
        runtime.update_workflow(ADMIN, project_id, "AFFAIRS_LEAVE", {"timeoutHours": 24})
    assert preset.value.code == "DATA_CONFLICT"


def test_t04b_change_project_is_the_only_way_forward(tenant_ctx):
    from app.models import SystemPresetInstallation

    project_id = _new_project()
    impl.preview_project(ADMIN, project_id)
    impl.apply_snapshot(ADMIN, project_id, {"confirmText": "确认应用", "reason": "应用后封板"})
    _set_status(project_id, "ACCEPTED")

    with _session() as db:
        installation = db.scalars(
            __import__("sqlalchemy").select(SystemPresetInstallation).where(
                SystemPresetInstallation.tenant_id == MAIN_TENANT_ID,
                SystemPresetInstallation.is_deleted.is_(False))).first()

    changed = impl.create_change_project(ADMIN, int(installation.id), {"projectName": "开学变更项目"})
    assert changed["status"] == "CONFIGURING"
    assert changed["id"] != str(project_id), "变更必须是新项目，不是改旧项目"

    # 已有进行中的变更项目时，不允许再开一个
    with pytest.raises(AppException) as second:
        impl.create_change_project(ADMIN, int(installation.id), {"projectName": "再开一个"})
    assert second.value.code == "DATA_CONFLICT"


# ── 接口层：仍然是同一套 /system/implementation/projects/*，没有 v2 ────────────
def test_no_v2_route_and_workspace_contract(client, auth_headers, tenant_ctx):
    # 用 OpenAPI 全量路径核对，而不是 app.routes（顶层拿不到被 include 的子路由）
    schema = client.get("/openapi.json").json()
    paths = set(schema.get("paths") or {})
    assert not any("/implementation/v2" in p for p in paths), "禁止另建 v2 路由"
    assert "/api/v1/system/implementation/projects" in paths
    assert "/api/v1/system/implementation/projects/{project_id}/apply" in paths

    created = client.post("/api/v1/system/implementation/projects", headers=auth_headers,
                          json={"projectName": "接口层实施项目",
                                "profileCode": "PILOT_FAST"}).json()
    assert created["code"] == 0
    project_id = created["data"]["id"]

    preview = client.post(f"/api/v1/system/implementation/projects/{project_id}/preview",
                          headers=auth_headers).json()
    assert preview["code"] == 0
    data = preview["data"]
    # 工作区首屏合同：快照哈希 + 幂等键 + 影响对象 + 授权结论，缺一不可
    assert data["previewHash"]
    assert data["idempotencyKey"] == data["previewHash"]
    assert "impact" in data["preview"] and "entitlement" in data["preview"]
