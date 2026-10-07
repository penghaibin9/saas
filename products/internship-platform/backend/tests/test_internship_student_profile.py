"""E-A01 / A01-7 StudentInternshipProfile targeted contracts."""
from __future__ import annotations

import inspect

from sqlalchemy import Index, UniqueConstraint

from app.models.internship_student_profile import (
    StudentInternshipProfile,
    StudentInternshipProfileItem,
)
from app.modules.internship.services import internship_student_profile_item_service as item_svc
from app.modules.internship.services import internship_student_profile_service as profile_svc


def test_profile_never_copies_school_canonical_student_fields():
    columns = set(StudentInternshipProfile.__table__.columns.keys())
    assert StudentInternshipProfile.__tablename__ == "t_internship_student_profile"
    assert {
        "tenant_id", "student_id", "profile_version", "headline", "self_intro", "strengths",
        "available_from", "available_until", "expected_locations_json", "skill_tags_json",
        "resume_template_code", "created_at", "updated_at", "is_deleted",
    } <= columns
    assert not {
        "real_name", "student_no", "college_id", "college_name", "major_id", "major_name",
        "grade", "class_id", "class_name", "student_status", "current_stage",
    } & columns
    uniques = {
        tuple(column.name for column in c.columns)
        for c in StudentInternshipProfile.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("tenant_id", "student_id") in uniques


def test_profile_items_cover_v3_student_entered_material_without_file_blob_columns():
    columns = set(StudentInternshipProfileItem.__table__.columns.keys())
    assert StudentInternshipProfileItem.__tablename__ == "t_internship_student_profile_item"
    assert {
        "profile_id", "item_type", "title", "organization", "description", "start_date",
        "end_date", "level", "source_type", "source_ref_type", "source_ref_id",
        "verification_status", "sort_order",
    } <= columns
    assert "file_id" not in columns
    assert "file_url" not in columns
    indexes = {
        tuple(column.name for column in index.columns)
        for index in StudentInternshipProfileItem.__table__.indexes
        if isinstance(index, Index)
    }
    assert ("tenant_id", "profile_id", "item_type", "is_deleted") in indexes


def test_my_student_identity_resolves_via_stable_account_link_not_login_name_guessing():
    source = inspect.getsource(profile_svc.resolve_my_student_id)
    assert "StudentAccountLink" in source
    assert 'StudentAccountLink.link_status == "ACTIVE"' in source
    assert "StudentAccountLink.user_id == _user_db_id(actor)" in source
    assert "login_name" not in source
    assert "student_no" not in source


def test_school_fact_projection_reads_canonical_student_and_org_tables_each_time():
    source = inspect.getsource(profile_svc._student_facts_in_tx)
    assert "select(StudentProfile)" in source
    assert "select(College)" in source
    assert "select(Major)" in source
    assert "select(SchoolClass)" in source
    assert '"realName": student.real_name' in source
    assert '"studentNo": student.student_no' in source
    assert '"studentStatus": student.student_status' in source


def test_student_profile_write_rejects_school_authority_fields_and_is_versioned():
    source = inspect.getsource(profile_svc.save_my_profile)
    assert "_FORBIDDEN_SCHOOL_FIELDS.intersection(body)" in source
    assert "学校主档字段不可在实习档案修改" in source
    assert "with_for_update()" in source
    assert "expectedProfileVersion" in source
    assert "profile.profile_version = int(profile.profile_version or 0) + 1" in source


def test_profile_attachments_reuse_file_center_binding_in_same_transaction():
    add_source = inspect.getsource(profile_svc.add_my_item)
    update_source = inspect.getsource(item_svc.update_my_item)
    assert "file_business_binding_service.bind_file_to_business(" in add_source
    assert 'biz_type="INTERNSHIP_STUDENT_PROFILE_ITEM"' in add_source
    assert 'relation_type="PROFILE_EVIDENCE"' in add_source
    assert "file_business_binding_service.bind_file_to_business(" in update_source
    assert 'verification_status="UNVERIFIED"' in add_source


def test_students_cannot_turn_self_entered_items_into_verified_school_facts():
    source = inspect.getsource(item_svc.update_my_item)
    assert 'item.source_type = "STUDENT_ENTERED"' in source
    assert "item.source_ref_type = None" in source
    assert "item.source_ref_id = None" in source
    assert 'item.verification_status = "UNVERIFIED"' in source
    assert "学校事实投影条目不可由学生修改" in inspect.getsource(item_svc._owned_item_in_tx)
