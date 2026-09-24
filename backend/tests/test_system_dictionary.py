from sqlalchemy import select

from app.models import PlatformConfig


BASE = "/api/v1/system/dictionaries"
TENANT_ID = 1000000000000000001


def test_school_dictionary_menu_api_reads_and_saves_own_tenant(client, db_mode, auth_headers):
    initial = client.get(BASE, headers=auth_headers)
    assert initial.status_code == 200
    payload = initial.json()["data"]
    assert payload["version"] == 0
    dictionaries = {item["code"]: item for item in payload["dictionaries"]}
    assert len(dictionaries) == 12
    assert dictionaries["studentStatus"]["editable"] is True
    assert dictionaries["tenantStatus"]["editable"] is False

    saved = client.put(
        f"{BASE}/riskLevel",
        headers=auth_headers,
        json={
            "expectedVersion": payload["version"],
            "tenantId": 999999,
            "items": [
                {"code": "HIGH", "label": "重点关注", "enabled": True},
                {"code": "LOW", "label": "一般关注", "enabled": True},
            ],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["version"] == 1

    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        own = db.scalar(select(PlatformConfig).where(
            PlatformConfig.tenant_id == TENANT_ID,
            PlatformConfig.config_type == "DICT",
            PlatformConfig.config_key == "-",
        ))
        foreign = db.scalar(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 999999,
            PlatformConfig.config_type == "DICT",
            PlatformConfig.config_key == "-",
        ))
        assert own.config_json["riskLevel"][0]["label"] == "重点关注"
        assert foreign is None
    finally:
        db.close()

    refreshed = client.get(BASE, headers=auth_headers).json()["data"]
    risk = next(item for item in refreshed["dictionaries"] if item["code"] == "riskLevel")
    assert risk["source"] == "SCHOOL"
    assert risk["items"][0]["label"] == "重点关注"


def test_school_dictionary_rejects_unknown_code_and_stale_version(client, db_mode, auth_headers):
    unknown = client.put(
        f"{BASE}/tenantStatus",
        headers=auth_headers,
        json={"expectedVersion": 0, "items": [{"code": "ACTIVE", "label": "启用"}]},
    )
    assert unknown.status_code == 400

    first = client.put(
        f"{BASE}/studentStatus",
        headers=auth_headers,
        json={"expectedVersion": 0, "items": [{"code": "NORMAL", "label": "正常在籍"}]},
    )
    assert first.status_code == 200
    stale = client.put(
        f"{BASE}/studentStatus",
        headers=auth_headers,
        json={"expectedVersion": 0, "items": [{"code": "NORMAL", "label": "正常"}]},
    )
    assert stale.status_code == 409
