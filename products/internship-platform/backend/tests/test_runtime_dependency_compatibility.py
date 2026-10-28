from io import BytesIO
from time import time

import jwt
import pytest
from PIL import Image

from app.config import settings
from app.core.exceptions import AppException
from app.core.security import create_access_token, decode_token
from app.services.internship_file_transfer_service import validate_upload


@pytest.mark.parametrize('format,extension,mime', [('PNG','png','image/png'), ('JPEG','jpg','image/jpeg'), ('GIF','gif','image/gif')])
def test_supported_image_uploads_still_validate(format, extension, mime):
    output = BytesIO()
    Image.new('RGB', (48, 32), (180, 210, 230)).save(output, format=format)
    result = validate_upload(output.getvalue(), 'fixture.' + extension, mime)
    assert result[1:3] == (extension, mime)


@pytest.mark.parametrize('data', [b'not an image', b'GIF89a\x01\x00\x01\x00'])
def test_invalid_image_content_is_rejected(data):
    with pytest.raises(AppException):
        validate_upload(data, 'invalid.gif', 'image/gif')


def test_token_compatibility_preserves_signature_algorithm_expiry_and_safe_errors(monkeypatch):
    key = 'local-dependency-compatibility-fixture-' * 2
    monkeypatch.setattr(settings, 'JWT_SECRET', key)
    monkeypatch.setattr(settings, 'JWT_ALG', 'HS256')
    token = create_access_token({'tenantId':'11','userId':'db-22'})
    assert decode_token(token)['userId'] == 'db-22'
    cases = [
        jwt.encode({'exp': int(time()) + 60}, 'different-fixture-key-' * 3, algorithm='HS256'),
        jwt.encode({'exp': int(time()) - 60}, key, algorithm='HS256'),
        jwt.encode({'exp': int(time()) + 60}, key, algorithm='HS384'),
        jwt.encode({'exp': {'unexpected':'object'}}, key, algorithm='HS256'),
        'broken.token',
    ]
    for invalid in cases:
        with pytest.raises(AppException) as caught:
            decode_token(invalid)
        assert caught.value.http_status == 401
