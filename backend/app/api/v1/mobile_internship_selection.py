"""Student mobile thin facade for A03 selection Authority."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc

router = APIRouter(
    prefix="/mobile/internship",
    tags=["学生移动端-实习选岗Authority"],
    dependencies=[Depends(require_module("internship"))],
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
