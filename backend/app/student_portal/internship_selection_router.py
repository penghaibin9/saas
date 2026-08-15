"""Student PC thin facade for A03 selection Authority."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.core.student_portal_module_gate import enforce_student_portal_module_access
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.modules.internship.services import internship_student_selection_actions_service as action_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc

router = APIRouter(
    prefix="/portal/internship",
    tags=["学生PC门户-实习选岗Authority"],
    dependencies=[Depends(enforce_student_portal_module_access)],
)


def _volunteer_contract(result: dict) -> dict:
    group = dict(result.get("group") or {})
    items = []
    for raw in result.get("applications") or []:
        item = dict(raw or {})
        if str(item.get("status") or "").upper() in {"WITHDRAWN", "CANCELLED"}:
            item["positionId"] = None
            item["companyName"] = ""
            item["positionName"] = ""
            item["applicationStatement"] = ""
        items.append(item)
    return {
        **group,
        "internshipId": group.get("recordId") or "",
        "recordVersion": int(result.get("recordVersion") or 0),
        "items": items,
    }


@router.get("/context/profile", summary="本人实习档案")
def get_my_profile(user=Depends(get_current_user)):
    return success(profile_svc.get_my_profile(user))


@router.put("/context/profile", summary="按版本保存本人实习档案")
def save_my_profile(body: dict = Body(...), user=Depends(get_current_user)):
    return success(profile_svc.save_my_profile(body or {}, user), message="实习档案已保存")


@router.get("/context/volunteers", summary="本人当前招聘季三志愿")
def get_my_volunteers(user=Depends(get_current_user)):
    return success(_volunteer_contract(selection_svc.get_my_volunteers(user=user)))


@router.put("/context/volunteers", summary="原子保存本人三志愿草稿")
def save_my_volunteer_draft(body: dict = Body(...), user=Depends(get_current_user)):
    result = selection_svc.save_my_draft(user=user, body=body or {})
    return success(_volunteer_contract(result), message="志愿草稿已保存")


@router.get("/context/volunteers/material-preview", summary="提交前企业视角材料预览证据")
def get_my_material_preview(user=Depends(get_current_user)):
    return success(selection_svc.get_my_material_preview(user=user))


@router.post("/context/volunteers/submit", summary="按预览与档案版本原子提交三志愿")
def submit_my_volunteers(body: dict = Body(...), user=Depends(get_current_user)):
    result = selection_svc.submit_my_saved_volunteers(user=user, body=body or {})
    return success(_volunteer_contract(result), message="志愿已整组提交")


@router.post("/context/volunteers/withdraw", summary="按版本整组撤回已提交志愿")
def withdraw_my_volunteers(body: dict = Body(...), user=Depends(get_current_user)):
    result = action_svc.withdraw_my_submission(user=user, body=body or {})
    return success(_volunteer_contract(result), message="志愿已整组撤回，可重新修改")


@router.post("/context/volunteers/unlock-request", summary="按版本申请修改企业拟接收锁定志愿")
def request_my_volunteer_unlock(body: dict = Body(...), user=Depends(get_current_user)):
    result = action_svc.request_my_unlock(user=user, body=body or {})
    return success(_volunteer_contract(result), message="改志愿申请已提交")


@router.get("/context/volunteers/submissions", summary="本人不可变投递版本历史")
def list_my_submission_history(user=Depends(get_current_user)):
    return success(action_svc.list_my_submissions(user=user))


@router.get("/context/volunteers/submissions/{submission_version}", summary="本人指定不可变投递版本")
def get_my_submission_version(submission_version: int, user=Depends(get_current_user)):
    return success(action_svc.get_my_submission(user=user, submission_version=submission_version))


@router.post("/context/volunteers/contact-consent/revoke", summary="撤销当前投递联系方式共享授权")
def revoke_my_contact_consent(body: dict = Body(...), user=Depends(get_current_user)):
    result = action_svc.revoke_my_contact_consent(user=user, body=body or {})
    return success(_volunteer_contract(result), message="联系方式共享授权已撤销")
