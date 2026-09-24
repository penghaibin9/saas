"""School data-dictionary routes.  Tenant scope always comes from auth context."""
from fastapi import APIRouter, Body, Depends

from app.core.context import current_tenant_id
from app.core.permissions import require_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.system_admin.services import school_dictionary_service as service


router = APIRouter()


@router.get("/school/dictionaries/effective", summary="当前学校业务有效字典")
def get_effective_school_dictionaries(
    consumer: str,
    user=Depends(get_current_user),
):
    _ = user
    return success(service.get_effective_options(int(current_tenant_id() or 0), consumer))


@router.get("/system/dictionaries", summary="本校数据字典")
def get_school_dictionaries(user=Depends(require_permission("systemAdmin.config.view"))):
    _ = user
    return success(service.get_workspace(int(current_tenant_id() or 0)))


@router.put("/system/dictionaries/{dict_code}", summary="保存本校数据字典覆盖")
def save_school_dictionary(
    dict_code: str,
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.config.manage")),
):
    _ = user
    result = service.save_dictionary(
        int(current_tenant_id() or 0),
        dict_code,
        items=(body or {}).get("items"),
        expected_version=(body or {}).get("expectedVersion"),
    )
    return success(result, message="本校字典已保存")
