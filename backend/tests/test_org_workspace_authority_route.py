"""The public organization URLs must reach the signed authority on all router versions."""
from starlette.routing import Match
from app.main import app
from app.api.v1 import system_p1_closure


def test_public_org_routes_reach_signed_authority():
    for method, path, expected in [
        ('GET', '/api/v1/system/org-nodes/COLLEGE/129/impact', system_p1_closure.org_node_impact),
        ('PUT', '/api/v1/system/org-nodes/129/status', system_p1_closure.set_org_node_status),
    ]:
        scope = {'type': 'http', 'path': path, 'root_path': '', 'method': method}
        candidates = [effective for route in app.routes for effective in (route.effective_route_contexts() if hasattr(route, 'effective_route_contexts') else [route])]
        matches = [route for route in candidates if route.matches(scope)[0] is Match.FULL]
        assert len(matches) == 1
        assert getattr(matches[0], 'original_route', matches[0]).endpoint is expected
