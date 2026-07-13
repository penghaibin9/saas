"""Fast production invariants for graduation persistence and evidence integrity."""
from app.models import (GraduationArchiveRecord, GraduationAuditTrail, GraduationFinal,
                        GraduationGrade, GraduationPlagiarismCheck, GraduationReview,
                        GraduationStudent, GraduationTopicChoice)


def _index_names(model) -> set[str]:
    return {index.name for index in model.__table__.indexes}


def test_graduation_integrity_columns_are_mapped():
    assert GraduationGrade.__table__.c.source_snapshot_hash.type.length == 64
    assert GraduationArchiveRecord.__table__.c.manifest_hash.type.length == 64
    assert GraduationAuditTrail.__table__.c.request_id.type.length == 64
    assert GraduationAuditTrail.__table__.c.request_path.type.length >= 255
    assert GraduationAuditTrail.__table__.c.client_ip.type.length >= 45


def test_graduation_hot_path_indexes_are_declared():
    expected = {
        GraduationStudent: "ix_gd_student_tenant_stage_active",
        GraduationTopicChoice: "ix_gd_choice_round_status",
        GraduationFinal: "ix_gd_final_tenant_student_status",
        GraduationPlagiarismCheck: "ix_gd_plag_tenant_final_status",
        GraduationReview: "ix_gd_review_tenant_student_status",
        GraduationArchiveRecord: "ix_gd_archive_tenant_status",
        GraduationAuditTrail: "ix_gd_audit_request_id",
    }
    for model, index_name in expected.items():
        assert index_name in _index_names(model)
