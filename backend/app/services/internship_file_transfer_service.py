"""实习证据读取适配：授权、扫描与存储仍由公共文件中心负责。"""
from app.core.exceptions import not_found
from app.services import file_access_service as access
from app.services.db_service import _tid, session

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset({
    'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx',
    'txt', 'csv', 'zip', 'rar', 'mp4', 'webm',
})


def authorized_file(file_id, user, action='meta'):
    value = str(file_id or '')
    if not value.isascii() or not value.isdigit() or not 0 < int(value) < 2**63:
        raise not_found('文件不存在')
    with session() as db:
        row, bindings = access._load_file_and_bindings(db, _tid(), int(value))
        if not row or not access.authorize_file_object(row, bindings, user or {}, action, db=db):
            raise not_found('文件不存在或不在可访问范围内')
        return row, access.file_view(row, user=user or {}, bindings=bindings, db=db)
