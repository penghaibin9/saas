from app.modules.system_admin.services import school_dictionary_service as service


class _Row:
    def __init__(self, payload):
        self.config_json = payload


class _Db:
    def close(self):
        pass


def test_effective_dictionary_only_overrides_consumer_labels(monkeypatch):
    monkeypatch.setattr(service, "get_sessionmaker", lambda: lambda: _Db())
    monkeypatch.setattr(
        service,
        "_row",
        lambda _db, tenant_id, **_kwargs: _Row({
            "studentStatus": [
                {"code": "ACTIVE", "label": "在校学习", "enabled": False},
                {"code": "CUSTOM", "label": "自定义状态", "enabled": True},
            ],
            "riskLevel": [{"code": "HIGH", "label": "重点关注", "enabled": True}],
        }) if tenant_id else None,
    )

    result = service.get_effective_options(1001, "studentCenter")

    statuses = {item["value"]: item["label"] for item in result["statusOptions"]["studentStatus"]}
    risks = {item["value"]: item["label"] for item in result["statusOptions"]["riskLevel"]}
    assert statuses["ACTIVE"] == "在校学习"
    assert "CUSTOM" not in statuses
    assert statuses["GRADUATED"] == "已毕业"
    assert risks["HIGH"] == "重点关注"


def test_effective_dictionary_rejects_unknown_consumer():
    try:
        service.get_effective_options(1001, "unknown")
    except Exception as exc:
        assert getattr(exc, "code", "") == "VALIDATION_ERROR"
    else:
        raise AssertionError("unknown consumer should be rejected")
