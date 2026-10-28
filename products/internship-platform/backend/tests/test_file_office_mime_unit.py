"""Office type projection and rejection checks; no database access."""
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.core.exceptions import AppException
from app.services.file_content_security import validate_content, validate_content_path
from app.services.internship_file_transfer_service import validate_upload


def test_office_mime_bytes_and_path_keep_container_validation(tmp_path):
    cases = {
        'docx': ('word/document.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        'xlsx': ('xl/workbook.xml', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        'pptx': ('ppt/presentation.xml', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'),
    }
    for ext, (member, expected) in cases.items():
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr(member, '<document/>')
        data = buffer.getvalue()
        args = dict(filename='sample.' + ext, ext=ext, declared_content_type=expected, source='SYSTEM')
        assert validate_content(data=data, **args)[0] == expected
        path = tmp_path / args['filename']
        path.write_bytes(data)
        assert validate_content_path(path=path, **args)[0] == expected
        wrong = 'xlsx' if ext != 'xlsx' else 'docx'
        with pytest.raises(AppException):
            validate_content(data=data, **{**args, 'ext': wrong})
    for ext, expected in [('doc', 'application/msword'), ('xls', 'application/vnd.ms-excel')]:
        assert validate_upload(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + bytes(512), 'sample.' + ext, expected)[2] == expected
        with pytest.raises(AppException):
            validate_upload(b'plain text is not Office', 'sample.' + ext, expected)
