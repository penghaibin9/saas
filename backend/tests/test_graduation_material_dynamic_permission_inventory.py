from __future__ import annotations

from app.core.graduation_permissions import graduation_permission_for_endpoint
from app.modules.graduation.routers.graduation_material_center import review_material_item


def test_dynamic_material_review_endpoint_is_registered_for_permission_inventory():
    assert graduation_permission_for_endpoint(review_material_item) == "graduationDesign.review.submit"
