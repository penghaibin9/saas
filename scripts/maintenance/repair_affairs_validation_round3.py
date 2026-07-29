from __future__ import annotations

from pathlib import Path


def repair_work_order_version() -> None:
    path = Path("backend/app/services/campus_service_service.py")
    text = path.read_text(encoding="utf-8")
    old = '''            "status": x.status, "statusLabel": L_WO_S.get(x.status, x.status),
            "detail": x.detail or "", "createTime": _iso(x.created_at),
            "updateTime": _iso(x.updated_at), "closeTime": _iso(x.close_time) or ""}
'''
    new = '''            "status": x.status, "statusLabel": L_WO_S.get(x.status, x.status),
            "version": int(x.version or 0),
            "detail": x.detail or "", "createTime": _iso(x.created_at),
            "updateTime": _iso(x.updated_at), "closeTime": _iso(x.close_time) or ""}
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif '"version": int(x.version or 0)' not in text.split("def _wo_row", 1)[1].split("def list_work_orders", 1)[0]:
        raise RuntimeError("work-order DTO anchor missing")
    path.write_text(text, encoding="utf-8")


def repair_mental_route_parameter_names() -> None:
    path = Path("backend/app/api/v1/mobile.py")
    text = path.read_text(encoding="utf-8")
    replacements = (
        ('@router.get("/teacher/mental/{ref_id}"', '@router.get("/teacher/mental/{referral_id}"'),
        ('def teacher_mental_detail(ref_id: str, reason: str = None, user=Depends(get_current_user)):',
         'def teacher_mental_detail(referral_id: str, reason: str = None, user=Depends(get_current_user)):'),
        ('return success(tea.mental_detail(user, ref_id, reason))',
         'return success(tea.mental_detail(user, referral_id, reason))'),
        ('@router.post("/teacher/mental/{ref_id}/follow"', '@router.post("/teacher/mental/{referral_id}/follow"'),
        ('def teacher_mental_follow(ref_id: str, body: dict = Body(...), user=Depends(get_current_user)):',
         'def teacher_mental_follow(referral_id: str, body: dict = Body(...), user=Depends(get_current_user)):'),
        ('return success(tea.mental_follow(user, ref_id, body), message="回访已记录")',
         'return success(tea.mental_follow(user, referral_id, body), message="回访已记录")'),
        ('@router.post("/teacher/mental/{ref_id}/escalate"', '@router.post("/teacher/mental/{referral_id}/escalate"'),
        ('def teacher_mental_escalate(ref_id: str, body: dict = Body(...), user=Depends(get_current_user)):',
         'def teacher_mental_escalate(referral_id: str, body: dict = Body(...), user=Depends(get_current_user)):'),
        ('return success(tea.mental_escalate(user, ref_id, body), message="已升级为危机风险")',
         'return success(tea.mental_escalate(user, referral_id, body), message="已升级为危机风险")'),
        ('@router.post("/teacher/mental/{ref_id}/close"', '@router.post("/teacher/mental/{referral_id}/close"'),
        ('def teacher_mental_close(ref_id: str, body: dict = Body(...), user=Depends(get_current_user)):',
         'def teacher_mental_close(referral_id: str, body: dict = Body(...), user=Depends(get_current_user)):'),
        ('return success(tea.mental_close(user, ref_id, body), message="已关闭")',
         'return success(tea.mental_close(user, referral_id, body), message="已关闭")'),
    )
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new, 1)
        elif new not in text:
            raise RuntimeError(f"mental route anchor missing: {old}")
    path.write_text(text, encoding="utf-8")


def repair_missing_version_expectation() -> None:
    path = Path("backend/tests/test_affairs_four_end_hardening.py")
    text = path.read_text(encoding="utf-8")
    old = '''    missing = client.post(
        f"{MB}/teacher/affairs/leaves/{leave_id}/approve",
        headers=counselor, json={"comment": "同意"},
    )
    assert missing.status_code == 409
'''
    new = '''    missing = client.post(
        f"{MB}/teacher/affairs/leaves/{leave_id}/approve",
        headers=counselor, json={"comment": "同意"},
    )
    assert missing.status_code == 400
    assert missing.json()["bizCode"] == "VALIDATION_ERROR"
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif 'missing.json()["bizCode"] == "VALIDATION_ERROR"' not in text:
        raise RuntimeError("missing-version expectation anchor missing")
    path.write_text(text, encoding="utf-8")


def audit() -> None:
    work_order = Path("backend/app/services/campus_service_service.py").read_text(encoding="utf-8")
    mobile = Path("backend/app/api/v1/mobile.py").read_text(encoding="utf-8")
    hardening = Path("backend/tests/test_affairs_four_end_hardening.py").read_text(encoding="utf-8")
    wo_block = work_order.split("def _wo_row", 1)[1].split("def list_work_orders", 1)[0]
    if '"version": int(x.version or 0)' not in wo_block:
        raise RuntimeError("work-order version still missing")
    for route in (
        '/teacher/mental/{referral_id}',
        '/teacher/mental/{referral_id}/follow',
        '/teacher/mental/{referral_id}/escalate',
        '/teacher/mental/{referral_id}/close',
    ):
        if route not in mobile:
            raise RuntimeError(f"mental contract route missing: {route}")
    if '{ref_id}' in "\n".join(
        line for line in mobile.splitlines() if '/teacher/mental/' in line
    ):
        raise RuntimeError("legacy mental path parameter remains")
    if 'missing.json()["bizCode"] == "VALIDATION_ERROR"' not in hardening:
        raise RuntimeError("missing-version status contract not updated")


def main() -> None:
    repair_work_order_version()
    repair_mental_route_parameter_names()
    repair_missing_version_expectation()
    audit()
    print("student affairs validation round3 repaired")


if __name__ == "__main__":
    main()
