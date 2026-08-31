"""A1 precise contract: real orientation xlsx import/export with canonical auth and scope reuse."""
from __future__ import annotations

import base64
import io

from openpyxl import load_workbook

TID = 1000000000000000001


def _headers(role: str) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": f"a1-{role}",
        "realName": f"A1-{role}",
        "userType": "TEACHER",
        "tid": "a1",
        "tenantId": str(TID),
        "activeContextId": "a1-context",
        "currentRoleCode": role,
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _xlsx(rows: list[list[str]]) -> bytes:
    from app.services.xlsx_util import build_template_xlsx

    return build_template_xlsx(
        ["姓名", "录取编号", "班级"],
        samples=rows,
        required=["姓名", "录取编号"],
    )


def test_orientation_real_file_import_export_roundtrip(client, db_mode):
    headers = _headers("SCHOOL_ADMIN")

    template_response = client.get(
        "/api/v1/import/domain/orientation/template",
        headers=headers,
    )
    assert template_response.status_code == 200
    template = template_response.json()["data"]
    assert template["filename"].endswith(".xlsx")
    workbook = load_workbook(io.BytesIO(base64.b64decode(template["contentBase64"])), read_only=True)
    assert workbook["导入模板"]["A1"].value == "姓名 *"
    assert workbook["导入模板"]["B1"].value == "录取编号 *"
    workbook.close()

    validate_response = client.post(
        "/api/v1/import/domain/orientation/validate-file",
        headers=headers,
        files={
            "file": (
                "orientation-a1.xlsx",
                _xlsx([["A1测试新生", "A1-LQ-0001", "A1测试班"]]),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validate_response.status_code == 200
    preview = validate_response.json()["data"]
    assert preview["status"] == "DRY_RUN_PASSED"
    assert preview["totalRows"] == preview["okRows"] == 1
    assert preview["errorRows"] == 0

    confirm_response = client.post(
        "/api/v1/import/domain/confirm",
        headers={**headers, "Idempotency-Key": "a1-orientation-import-confirm"},
        json={"domain": "orientation", "batchNo": preview["batchNo"]},
    )
    assert confirm_response.status_code == 200
    receipt = confirm_response.json()["data"]
    assert receipt["status"] == "SUCCESS"
    assert receipt["insertedRows"] == 1

    list_response = client.get("/api/v1/orientation/students", headers=headers)
    assert list_response.status_code == 200
    assert [row["admissionNo"] for row in list_response.json()["data"]["items"]] == ["A1-LQ-0001"]

    export_response = client.post(
        "/api/v1/export/domain/orientation",
        headers={**headers, "Idempotency-Key": "a1-orientation-export"},
        json={"purpose": "A1迎新导出验收"},
    )
    assert export_response.status_code == 200
    task = export_response.json()["data"]
    assert task["status"] == "SUCCESS"
    assert task["rowCount"] == 1

    download_response = client.get(
        f"/api/v1/export/tasks/{task['taskId']}/download",
        headers=headers,
    )
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    exported = load_workbook(io.BytesIO(download_response.content), read_only=True)
    sheet = exported.active
    assert "A1迎新导出验收" in sheet["A1"].value
    assert sheet["A3"].value == "A1测试新生"
    exported.close()


def test_orientation_import_export_rejects_unrelated_dorm_role(client, db_mode):
    headers = _headers("DORM_MANAGER")
    assert client.get(
        "/api/v1/import/domain/orientation/template", headers=headers,
    ).status_code == 403
    assert client.post(
        "/api/v1/export/domain/orientation",
        headers=headers,
        json={"purpose": "无权导出验收"},
    ).status_code == 403
