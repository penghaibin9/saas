"""系统管理·实施与预设中心 API。"""
from fastapi import APIRouter, Body, Depends

from app.core.permissions import require_any_permission, require_permission
from app.core.response import success
from app.services import system_implementation_service as service

router = APIRouter(prefix="/system/implementation", tags=["实施与预设中心"])


@router.get("/preset-catalog")
def catalog(user=Depends(require_any_permission("systemAdmin.implementation.view",
                                                "systemAdmin.implementation.configure",
                                                "systemAdmin.implementation.preset.view"))):
    return success(service.preset_catalog())


@router.get("/projects/current")
def current(user=Depends(require_permission("systemAdmin.implementation.view"))):
    return success(service.current_project())


@router.post("/projects")
def create(body: dict = Body(default={}), user=Depends(require_permission("systemAdmin.implementation.create"))):
    return success(service.create_project(user, body), message="实施项目已创建")


@router.put("/projects/{project_id}/sections/{section_code}")
def save_section(project_id: int, section_code: str, body: dict = Body(...),
                 user=Depends(require_permission("systemAdmin.implementation.configure"))):
    return success(service.save_section(user, project_id, section_code, body), message="配置已保存")


@router.post("/projects/{project_id}/preview")
def preview(project_id: int, user=Depends(require_permission("systemAdmin.implementation.preview"))):
    return success(service.preview_project(user, project_id), message="安装预览已生成")


@router.post("/projects/{project_id}/apply")
def apply(project_id: int, body: dict = Body(...),
          user=Depends(require_permission("systemAdmin.implementation.apply"))):
    return success(service.apply_snapshot(user, project_id, body), message="预设快照已应用")


@router.post("/projects/{project_id}/mapping/discover")
def discover(project_id: int, body: dict = Body(...),
             user=Depends(require_permission("systemAdmin.implementation.mapping.manage"))):
    return success(service.discover_batch(user, project_id, str(body.get("batchNo") or "")))


@router.put("/projects/{project_id}/mapping/decisions")
def decisions(project_id: int, body: dict = Body(...),
              user=Depends(require_permission("systemAdmin.implementation.mapping.manage"))):
    return success(service.confirm_mapping(user, project_id, body), message="组织与角色匹配已确认")


@router.post("/projects/{project_id}/mapping/apply")
def apply_mapping(project_id: int, body: dict = Body(...),
                  user=Depends(require_permission("systemAdmin.implementation.mapping.apply"))):
    return success(service.apply_mapping(user, project_id, body), message="组织与角色已安装并重新校验导入批次")


@router.post("/projects/{project_id}/relations/discover")
def discover_relations(project_id: int, body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.implementation.relation.manage"))):
    from app.services import business_relation_install_service as relation_service
    return success(relation_service.discover(user, project_id, str(body.get("batchNo") or "")),
                   message="业务关系候选已生成")


@router.put("/projects/{project_id}/relations/decisions")
def confirm_relations(project_id: int, body: dict = Body(...),
                      user=Depends(require_permission("systemAdmin.implementation.relation.manage"))):
    from app.services import business_relation_install_service as relation_service
    return success(relation_service.confirm(user, project_id, body), message="业务关系决定已确认")


@router.post("/projects/{project_id}/relations/apply")
def apply_relations(project_id: int, body: dict = Body(...),
                    user=Depends(require_permission("systemAdmin.implementation.relation.apply"))):
    from app.services import business_relation_install_service as relation_service
    return success(relation_service.apply(user, project_id, body), message="业务关系已写入真实业务主表")


@router.get("/projects/{project_id}/relations/batches")
def relation_batches(project_id: int,
                     user=Depends(require_permission("systemAdmin.implementation.relation.manage"))):
    from app.services import business_relation_install_service as relation_service
    return success(relation_service.list_batches(project_id))


@router.post("/projects/{project_id}/relations/{batch_no}/rollback")
def rollback_relations(project_id: int, batch_no: str, body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.implementation.relation.rollback"))):
    from app.services import business_relation_install_service as relation_service
    return success(relation_service.rollback(user, project_id, batch_no, body),
                   message="业务关系批次已安全回滚")


@router.get("/installations")
def installations(user=Depends(require_permission("systemAdmin.implementation.installed.view"))):
    return success(service.installations())


@router.post("/installations/{installation_id}/changes")
def create_change(installation_id: int, body: dict = Body(default={}),
                  user=Depends(require_permission("systemAdmin.implementation.change.manage"))):
    return success(service.create_change_project(user, installation_id, body),
                   message="变更项目已创建，请确认继承配置后再预览")


@router.post("/projects/{project_id}/changes/analyze")
def analyze_change(project_id: int,
                   user=Depends(require_permission("systemAdmin.implementation.change.manage"))):
    return success(service.analyze_change(user, project_id), message="变更影响分析已生成")


@router.get("/projects/{project_id}/runtime-presets")
def runtime_presets(project_id: int,
                    user=Depends(require_permission("systemAdmin.implementation.view"))):
    from app.services import runtime_preset_install_service as runtime_service
    return success(runtime_service.status(project_id))


@router.post("/projects/{project_id}/runtime-presets/workflows/confirm-policy")
def confirm_workflow_policy(project_id: int, body: dict = Body(...),
                            user=Depends(require_permission("systemAdmin.implementation.configure"))):
    from app.services import runtime_preset_install_service as runtime_service
    return success(runtime_service.confirm_policy(user, project_id, body),
                   message="学校流程政策已确认并启用")


@router.put("/projects/{project_id}/runtime-presets/workflows/{workflow_code}")
def update_runtime_workflow(project_id: int, workflow_code: str, body: dict = Body(...),
                            user=Depends(require_permission("systemAdmin.implementation.configure"))):
    from app.services import runtime_preset_install_service as runtime_service
    return success(runtime_service.update_workflow(user, project_id, workflow_code, body),
                   message="流程配置已保存，关键政策变更需重新确认")


@router.put("/projects/{project_id}/runtime-presets/workbenches/{role_code}")
def update_runtime_workbench(project_id: int, role_code: str, body: dict = Body(...),
                             user=Depends(require_permission("systemAdmin.implementation.configure"))):
    from app.services import runtime_preset_install_service as runtime_service
    return success(runtime_service.update_workbench(user, project_id, role_code, body), message="角色工作台已更新")


@router.put("/projects/{project_id}/runtime-presets/notifications/{template_code}/{channel}")
def update_runtime_notification(project_id: int, template_code: str, channel: str,
                                body: dict = Body(...),
                                user=Depends(require_permission("systemAdmin.implementation.configure"))):
    from app.services import runtime_preset_install_service as runtime_service
    return success(runtime_service.update_notification(user, project_id, template_code, channel, body),
                   message="通知模板已更新")


@router.post("/projects/{project_id}/checks/run")
def checks(project_id: int, user=Depends(require_permission("systemAdmin.implementation.check.run"))):
    return success(service.run_checks(user, project_id))


@router.post("/projects/{project_id}/checks/{check_code}/confirm")
def confirm_check(project_id: int, check_code: str, body: dict = Body(...),
                  user=Depends(require_permission("systemAdmin.implementation.check.run"))):
    return success(service.confirm_check(user, project_id, check_code, body), message="责任确认已记录")


@router.post("/projects/{project_id}/accept")
def accept(project_id: int, body: dict = Body(...),
           user=Depends(require_permission("systemAdmin.implementation.accept"))):
    return success(service.accept_project(user, project_id, body), message="学校实施已验收封板")
