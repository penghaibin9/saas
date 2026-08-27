from app.services import file_service


def test_attachment_view_projects_authorized_preview_and_download(monkeypatch):
    monkeypatch.setattr(
        file_service,
        "_authorized_attachment_metadata",
        lambda file_id: {
            "fileId": str(file_id),
            "fileName": "proposal.pdf",
            "ext": "pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 128,
            "allowedActions": ["viewMetadata", "preview", "download"],
        },
    )

    result = file_service.attachment_view("42")

    assert result == {
        "fileId": "42",
        "fileName": "proposal.pdf",
        "ext": "pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 128,
        "allowedActions": ["viewMetadata", "preview", "download"],
        "canPreview": True,
        "canDownload": True,
    }


def test_attachment_view_does_not_invent_capabilities(monkeypatch):
    monkeypatch.setattr(
        file_service,
        "_authorized_attachment_metadata",
        lambda file_id: {
            "fileId": str(file_id),
            "fileName": "proposal.pdf",
            "ext": "pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 128,
            "allowedActions": ["viewMetadata"],
        },
    )

    result = file_service.attachment_view("42")

    assert result["canPreview"] is False
    assert result["canDownload"] is False
    assert result["allowedActions"] == ["viewMetadata"]
