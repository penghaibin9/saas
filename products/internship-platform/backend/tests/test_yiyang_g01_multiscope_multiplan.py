"""Yiyang G01: multi-school, multi-college and multi-plan authority contracts.

This suite is standalone-owned: it does not depend on the parent SaaS test fixtures.
"""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InternshipEnterpriseCollegeScope, InternshipPlanAssignment
from app.modules.internship.services import internship_scope as scope_svc


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    InternshipEnterpriseCollegeScope.__table__.create(engine)
    InternshipPlanAssignment.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_g01_multi_school_multi_college_scope_is_tenant_isolated(db):
    db.add_all([
        InternshipEnterpriseCollegeScope(
            tenant_id=1001, company_id=501, college_id=11, scope_source="MANUAL"
        ),
        InternshipEnterpriseCollegeScope(
            tenant_id=1001, company_id=501, college_id=12, scope_source="MANUAL"
        ),
        # Same company/college identifiers are legal in another school because
        # tenant_id is part of the authority key.
        InternshipEnterpriseCollegeScope(
            tenant_id=2002, company_id=501, college_id=11, scope_source="MANUAL"
        ),
    ])
    db.commit()

    tenant_1 = db.scalar(
        select(func.count())
        .select_from(InternshipEnterpriseCollegeScope)
        .where(InternshipEnterpriseCollegeScope.tenant_id == 1001)
    )
    tenant_2 = db.scalar(
        select(func.count())
        .select_from(InternshipEnterpriseCollegeScope)
        .where(InternshipEnterpriseCollegeScope.tenant_id == 2002)
    )
    assert tenant_1 == 2
    assert tenant_2 == 1

    db.add(
        InternshipEnterpriseCollegeScope(
            tenant_id=1001, company_id=501, college_id=11, scope_source="IMPORT"
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_g01_one_internship_can_receive_multiple_formal_plans_without_cross_school_collision(db):
    db.add_all([
        InternshipPlanAssignment(
            tenant_id=1001,
            internship_id=7001,
            student_id=9001,
            plan_id=3001,
            plan_batch_id=8001,
            assignment_source="PRIMARY_AUTO",
            is_primary=True,
            status="ACTIVE",
        ),
        InternshipPlanAssignment(
            tenant_id=1001,
            internship_id=7001,
            student_id=9001,
            plan_id=3002,
            plan_batch_id=8001,
            assignment_source="MANUAL",
            is_primary=False,
            status="ACTIVE",
        ),
        # Another school may reuse local numeric identifiers without colliding.
        InternshipPlanAssignment(
            tenant_id=2002,
            internship_id=7001,
            student_id=9001,
            plan_id=3001,
            plan_batch_id=8001,
            assignment_source="PRIMARY_AUTO",
            is_primary=True,
            status="ACTIVE",
        ),
    ])
    db.commit()

    school_1 = list(db.scalars(
        select(InternshipPlanAssignment)
        .where(
            InternshipPlanAssignment.tenant_id == 1001,
            InternshipPlanAssignment.internship_id == 7001,
            InternshipPlanAssignment.status == "ACTIVE",
        )
        .order_by(InternshipPlanAssignment.plan_id)
    ))
    assert [row.plan_id for row in school_1] == [3001, 3002]
    assert sum(1 for row in school_1 if row.is_primary) == 1

    db.add(
        InternshipPlanAssignment(
            tenant_id=1001,
            internship_id=7001,
            student_id=9001,
            plan_id=3001,
            plan_batch_id=8001,
            assignment_source="MANUAL",
            is_primary=False,
            status="ACTIVE",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_g01_scope_authority_is_fail_closed_and_tenant_scoped():
    lock_source = inspect.getsource(scope_svc.lock_internship_record)
    assert "InternshipRecord.tenant_id == _tid()" in lock_source

    assert_source = inspect.getsource(scope_svc.assert_internship_record_scope)
    assert "rec.tenant_id != _tid()" in assert_source
    assert "_rec_in_scope(_current_scope(user)" in assert_source

    apply_source = inspect.getsource(scope_svc.apply_internship_record_scope)
    assert "StudentProfile.tenant_id == _tid()" in apply_source
    assert "else false()" in apply_source
    assert "advisor_user_id" in apply_source
