"""Pure regression locks for internship leave/makeup evidence requirements."""
from app.modules.internship.services import internship_leave_service as leave_service
from app.modules.internship.services import internship_makeup_service as makeup_service


def test_leave_evidence_required_for_sick_and_long_leave():
    assert leave_service._evidence_required("SICK", 1)
    assert leave_service._evidence_required("PERSONAL", 3)
    assert leave_service._evidence_required("OTHER", 5)
    assert not leave_service._evidence_required("PERSONAL", 2)


def test_makeup_evidence_required_only_for_out_of_range():
    assert makeup_service._evidence_required("OUT_OF_RANGE")
    assert not makeup_service._evidence_required("MISSING")


def test_requirement_labels_explain_blocking_rule():
    assert "病假" in leave_service._evidence_requirement_label("SICK", 1)
    assert "3天" in leave_service._evidence_requirement_label("PERSONAL", 3)
    assert "超范围" in makeup_service._evidence_requirement_label("OUT_OF_RANGE")
