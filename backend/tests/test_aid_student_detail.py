"""本人详情须与评审真相一致，且不向列表或其他学生扩散家庭信息。"""
import pytest
from sqlalchemy import select

from app.core.exceptions import AppException
from app.api.v1.affairs_student_returned import aid_detail, aid_editable
from app.services import mobile_affairs_service
from test_affairs_aid import TID, _seed, _hdr, _open_batch, _apply
from test_affairs_four_end_hardening import _set_ctx, _clear_ctx


def test_personal_detail_preserves_scope_and_sensitive_projection(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, AffairsAuditTrail
    ids = _seed(db_mode)
    header = _hdr(client, 'school_admin01')
    batch = _open_batch(client, header)
    response = _apply(client, header, batch, ids['sa'])
    assert response.status_code == 200, response.text
    apply_id = int(response.json()['data']['applyId'])
    user = {'userId': 'u-A001', 'studentNo': 'A001', 'realName': '甲一',
            'userType': 'STUDENT', 'currentRoleCode': 'STUDENT', 'tenantId': str(TID)}
    _set_ctx(user)
    try:
        detail = aid_detail(apply_id, user)['data']
        assert detail['status'] == 'CLASS_REVIEW'
        assert detail['batchName']
        assert detail['createdAt']
        assert detail['allowedActions'] == []
        assert 'annualIncome' in detail and 'statement' in detail
        assert detail['publicityEnd'] is None
        listing = mobile_affairs_service.aid_my(user)['items']
        assert len(listing) == 1
        assert not ({'annualIncome', 'statement', 'debt', 'familyMembers'} & listing[0].keys())
        # 已退回与已认定都可查看，编辑权限仅在退回时开放。
        with get_sessionmaker()() as db:
            row = db.get(AidApply, apply_id)
            row.status = 'DRAFT'; row.return_reason = '请补充收入说明'
            db.commit()
        returned = aid_detail(apply_id, user)['data']
        assert returned['returnReason'] == '请补充收入说明'
        assert returned['allowedActions'] == ['EDIT_RETURNED', 'RESUBMIT']
        editable = aid_editable(apply_id, user)['data']
        assert editable['statement'] == detail['statement']
        assert editable['statement']
        with get_sessionmaker()() as db:
            db.get(AidApply, apply_id).status = 'APPROVED'
            db.commit()
        assert aid_detail(apply_id, user)['data']['allowedActions'] == []
        other = {**user, 'studentNo': 'B001', 'userId': 'u-B001'}
        with pytest.raises(AppException):
            aid_detail(apply_id, other)
        with get_sessionmaker()() as db:
            audits = db.scalars(select(AffairsAuditTrail).where(
                AffairsAuditTrail.biz_id == apply_id,
                AffairsAuditTrail.action == 'STUDENT_VIEW_DETAIL')).all()
            assert len(audits) == 3
            db.get(AidApply, apply_id).is_deleted = True
            db.commit()
        with pytest.raises(AppException):
            aid_detail(apply_id, user)
    finally:
        _clear_ctx()
