"""退宿兼容入口：D4 起只发起正式退宿单，不再直接释放床位。"""
from __future__ import annotations

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import affairs_dorm_service as dorm

    def checkout(bed_id, user, expected_version=None):
        from app.services.affairs_dorm_stay_service import create_checkout_request
        return create_checkout_request(
            bed_id=int(bed_id), expected_bed_version=expected_version,
            request_type="SPECIAL", reason="人工办理退宿，待宿管确认",
            client_request_id=f"legacy-checkout:{int(bed_id)}:v{int(expected_version)}",
            user=user,
        )

    dorm.checkout = checkout
    _INSTALLED = True
