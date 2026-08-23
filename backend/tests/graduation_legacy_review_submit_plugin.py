"""Legacy HTTP adapter for pre-W7 formal-review submit fixtures only.

Production W7 requires optimistic review version + exact frozen FileVersion on every
formal-review submit. Older graduation_client tests intentionally exercise the same
business flow but predate those request fields. This adapter fills only those missing
request fields from the already-created authoritative GraduationReview snapshot; it
never creates evidence, changes production authorization, or overwrites explicit test
values.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import pytest
from sqlalchemy import text

MAIN_TENANT_ID = 1000000000000000001
_FORMAL_REVIEW_SUBMIT = re.compile(r"^/api/v1/graduation/gd-reviews/(\d+)/submit$")


def _inject_formal_review_submit(path: str, kwargs: dict) -> None:
    match = _FORMAL_REVIEW_SUBMIT.match(path)
    if not match:
        return
    body = kwargs.get("json")
    if not isinstance(body, dict):
        return
    if body.get("expectedVersion") is not None and body.get("fileVersionId") is not None:
        return

    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        row = db.execute(text(
            "SELECT version,file_version_id FROM t_gd_review "
            "WHERE tenant_id=:tenant_id AND id=:review_id AND is_deleted=0"
        ), {
            "tenant_id": MAIN_TENANT_ID,
            "review_id": int(match.group(1)),
        }).mappings().first()
        if not row:
            return
        patched = dict(body)
        patched.setdefault("expectedVersion", int(row.get("version") or 0))
        if row.get("file_version_id") is not None:
            patched.setdefault("fileVersionId", int(row["file_version_id"]))
        kwargs["json"] = patched
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _legacy_formal_review_submit_contract(request):
    if "graduation_client" not in request.fixturenames:
        yield
        return

    client = request.getfixturevalue("graduation_client")
    original_request = client.request

    def request_with_w7_submit_contract(method, url, **kwargs):
        path = urlsplit(str(url)).path or str(url)
        if str(method).upper() == "POST":
            _inject_formal_review_submit(path, kwargs)
        return original_request(method, url, **kwargs)

    client.request = request_with_w7_submit_contract
    yield
