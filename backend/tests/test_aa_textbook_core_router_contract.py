"""D9-S4 教材 Router Move Only 结构合同。"""
from __future__ import annotations

import re


def _key(route):
    path = re.sub(r"\{[^/{}]+\}", "{}", getattr(route, "path", ""))
    methods = tuple(sorted(getattr(route, "methods", set()) or set()))
    return path, methods


def _owners():
    from app.modules.academic_affairs.routers import academic_affairs_bundle

    return {
        _key(route): route.endpoint.__module__
        for route in academic_affairs_bundle.build_router().routes
        if getattr(route, "endpoint", None)
    }


def test_d9_s4_textbook_legacy_routes_are_owned_by_textbook_core_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/textbooks", ("POST",)),
        ("/academic-affairs/textbooks", ("GET",)),
        ("/academic-affairs/textbooks/{}", ("PUT",)),
        ("/academic-affairs/textbooks/selections", ("POST",)),
        ("/academic-affairs/textbooks/selections", ("GET",)),
        ("/academic-affairs/textbooks/selections/{}/submit", ("POST",)),
        ("/academic-affairs/textbooks/selections/{}/withdraw", ("POST",)),
        ("/academic-affairs/textbooks/review-batches", ("POST",)),
        ("/academic-affairs/textbooks/review-batches", ("GET",)),
        ("/academic-affairs/textbooks/review-batches/{}/advance", ("POST",)),
        ("/academic-affairs/textbooks/order-batches", ("POST",)),
        ("/academic-affairs/textbooks/order-batches", ("GET",)),
        ("/academic-affairs/textbooks/order-batches/{}/items", ("GET",)),
        ("/academic-affairs/textbooks/order-batches/{}/submit", ("POST",)),
        ("/academic-affairs/textbooks/order-items/{}/arrival", ("POST",)),
        ("/academic-affairs/textbooks/order-batches/{}/archive", ("POST",)),
        ("/academic-affairs/textbooks/distribution-batches", ("POST",)),
        ("/academic-affairs/textbooks/distribution-batches/{}/records", ("GET",)),
        ("/academic-affairs/textbooks/distribution-records/{}/sign", ("POST",)),
        ("/academic-affairs/textbooks/fee-ledger", ("GET",)),
        ("/academic-affairs/textbooks/fee-ledger/{}/mark", ("POST",)),
        ("/academic-affairs/textbooks/stock", ("GET",)),
        ("/academic-affairs/textbooks/stats", ("GET",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D9-S4 routes missing from public bundle: {sorted(missing)}"
    expected_owner = "app.modules.academic_affairs.routers.textbook_core_router"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"D9-S4 public owner drift: {wrong}"


def test_d9_s4_preserves_textbook_closure_extension_owners():
    owners = _owners()
    expected = {
        ("/academic-affairs/textbooks/review-candidates", ("GET",)),
        ("/academic-affairs/textbooks/distribution-batches", ("GET",)),
        ("/academic-affairs/textbooks/distribution-workbench/{}/records", ("GET",)),
        ("/academic-affairs/textbooks/order-batches/{}/cancel", ("POST",)),
        ("/academic-affairs/textbooks/distribution-records/{}/return", ("POST",)),
    }
    expected_owner = "app.modules.academic_affairs.routers.textbook_closure_router"
    missing = expected - set(owners)
    assert not missing, f"textbook closure routes missing: {sorted(missing)}"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"textbook closure owner drift: {wrong}"
