from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.internship.services.internship_student_makeup_context_service import _check_existing_checkin
from app.modules.internship.services.internship_makeup_service import _evidence_required


@pytest.mark.parametrize('result', ['OUT_OF_RANGE', 'LOW_ACCURACY', 'LOCATION_UNCERTAIN'])
def test_location_correction_requires_evidence_path_and_keeps_original_fact(result):
    row = SimpleNamespace(result=result, is_deleted=False)
    with pytest.raises(AppException):
        _check_existing_checkin(row, 'MISSING')
    _check_existing_checkin(row, 'OUT_OF_RANGE')
    assert _evidence_required('OUT_OF_RANGE')
    assert row.result == result and not row.is_deleted


@pytest.mark.parametrize('result', ['NORMAL', 'RECORDED', 'LEAVE', 'MOCK_LOCATION'])
def test_valid_leave_or_mock_record_cannot_use_location_correction(result):
    with pytest.raises(AppException):
        _check_existing_checkin(SimpleNamespace(result=result, is_deleted=False), 'OUT_OF_RANGE')


def test_missing_location_and_cancelled_leave_keep_existing_correction_path():
    _check_existing_checkin(None, 'MISSING')
    _check_existing_checkin(SimpleNamespace(result='NO_LOCATION', is_deleted=False), 'MISSING')
    _check_existing_checkin(SimpleNamespace(result='LEAVE', is_deleted=True), 'MISSING')
