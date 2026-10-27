"""Audit export must match filters and columns beyond the first page."""
from datetime import datetime

import pytest

from app.modules.system_admin.routers import system_bundle as logs


def test_export_keeps_filters_columns_and_all_pages(db_mode, monkeypatch):
    from app.core.context import set_tenant
    from app.core.exceptions import AppException
    from app.models import SecurityAuditLog
    from app.services.db_service import session
    tid = 1000000000000000001
    set_tenant({'tenantId': tid})
    with session() as db:
        db.add_all([SecurityAuditLog(tenant_id=tid, action='USER_UPDATE', result='SUCCESS',
            resource='D603-export', operator_name='虚构经办人',
            request_path='/api/v1/system/users', created_at=datetime(2026, 10, 25, 1)) for _ in range(201)])
        for changes in ({'tenant_id': tid + 1}, {'result': 'FAILED'},
                        {'created_at': datetime(2026, 10, 23)}, {'action': 'ROLE_UPDATE'},
                        {'detail_json': {'moduleCode': 'graduationDesign'}}):
            values = dict(tenant_id=tid, action='USER_UPDATE', result='SUCCESS', resource='D603-export',
                          request_path='/api/v1/system/users', created_at=datetime(2026, 10, 25, 1))
            db.add(SecurityAuditLog(**(values | changes)))
        db.commit()
    monkeypatch.setattr(logs, '_xlsx_response', lambda title, headers, rows, *args: (headers, rows))
    headers, rows = logs.export_system_logs(keyword='D603-export', result='SUCCESS', action='USER_UPDATE',
        module='systemAdmin', dateFrom='2026-10-25', dateTo='2026-10-25', fields='who,time,result', user={})
    assert headers == ['操作人', '时间', '结果']
    assert len(rows) == 201
    assert all(r == ['虚构经办人', '2026-10-25 09:00:00', '成功'] for r in rows)
    for fields in ('who,unknown', 'who,who'):
        with pytest.raises(AppException):
            logs.export_system_logs(fields=fields, user={})
