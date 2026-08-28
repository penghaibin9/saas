from __future__ import annotations

import os
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    EmpCompany,
    InternshipApplication,
    InternshipAuditTrail,
    InternshipBatchParticipant,
    InternshipMatch,
    InternshipPosition,
    InternshipRecord,
)
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot
from app.models.internship_volunteer_group import InternshipVolunteerGroup


def required_int(name: str) -> int:
    raw = str(os.getenv(name) or '').strip()
    if not raw.isdigit():
        raise SystemExit(f'{name} must be a numeric id')
    return int(raw)


def required_text(name: str) -> str:
    value = str(os.getenv(name) or '').strip()
    if not value:
        raise SystemExit(f'{name} is required')
    return value


def assert_safe_target() -> None:
    db_url = str(os.getenv('DATABASE_URL') or '')
    lowered = db_url.lower()
    if not db_url or not any(x in lowered for x in ('e2e', 'test')):
        raise SystemExit('DATABASE_URL must target e2e/test')
    if any(x in lowered for x in ('prod', 'production', 'staging')):
        raise SystemExit('refusing production/staging database')
    if urlparse(db_url).hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise SystemExit('IX-009 verifier only accepts a local database')


def main() -> int:
    assert_safe_target()
    company_id = required_int('E2E_IX009_COMPANY_ID')
    position_id = required_int('E2E_IX009_POSITION_ID')
    match_id = required_int('E2E_IX009_MATCH_ID')
    application_id = required_int('E2E_IX009_APPLICATION_ID')
    record_id = required_int('E2E_IX009_INTERNSHIP_ID')
    batch_id = required_int('E2E_IX009_BATCH_ID')
    campaign_id = required_int('E2E_IX009_CAMPAIGN_ID')
    advisor_name = required_text('E2E_IX009_ADVISOR_NAME')
    position_title = required_text('E2E_IX009_POSITION_TITLE')
    company_name = required_text('E2E_IX009_COMPANY_NAME')

    db = get_sessionmaker()()
    try:
        record = db.get(InternshipRecord, record_id)
        company = db.get(EmpCompany, company_id)
        position = db.get(InternshipPosition, position_id)
        match = db.get(InternshipMatch, match_id)
        application = db.get(InternshipApplication, application_id)
        if not all((record, company, position, match, application)):
            raise AssertionError('IX-009 canonical rows are incomplete')

        tenant_id = int(record.tenant_id)
        assert int(record.batch_id or 0) == batch_id
        assert int(record.enterprise_id or 0) == company_id
        assert int(record.position_id or 0) == position_id
        assert record.enterprise_name == company_name
        assert record.position_name == position_title
        assert record.destination_type == 'ASSIGNED'
        assert record.advisor_name == advisor_name
        assert record.advisor_user_id is not None

        assert company.blacklist is True or company.coop_status == 'BLACKLIST'
        assert position.title == position_title
        assert int(position.allocated_count or 0) == 1
        assert int(position.headcount or 0) == 2

        assert int(match.record_id) == record_id
        assert int(match.position_id) == position_id
        assert match.status == 'CONFIRMED'

        assert int(application.record_id) == record_id
        assert int(application.position_id or 0) == position_id
        assert int(application.campaign_id or 0) == campaign_id
        assert application.application_type == 'POSITION'
        assert application.status == 'APPROVED'
        assert application.material_snapshot_id is not None

        group = db.scalars(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.record_id == record_id,
            InternshipVolunteerGroup.campaign_id == campaign_id,
            InternshipVolunteerGroup.is_deleted.is_(False),
        )).first()
        assert group is not None
        assert group.status == 'APPROVED'
        assert int(group.current_material_snapshot_id or 0) == int(application.material_snapshot_id)

        participant = db.scalars(select(InternshipBatchParticipant).where(
            InternshipBatchParticipant.tenant_id == tenant_id,
            InternshipBatchParticipant.batch_id == batch_id,
            InternshipBatchParticipant.internship_id == record_id,
            InternshipBatchParticipant.is_deleted.is_(False),
        )).first()
        assert participant is not None
        assert participant.status == 'ACTIVE'

        snapshots = list(db.scalars(select(InternshipPlacementSnapshot).where(
            InternshipPlacementSnapshot.tenant_id == tenant_id,
            InternshipPlacementSnapshot.record_id == record_id,
        ).order_by(InternshipPlacementSnapshot.placement_seq)).all())
        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert int(snapshot.position_id) == position_id
        assert int(snapshot.company_id) == company_id
        assert int(snapshot.application_id or 0) == application_id
        assert snapshot.company_name == company_name
        assert snapshot.position_title == position_title
        assert snapshot.snapshot_sha256 and len(snapshot.snapshot_sha256) == 64
        assert int(record.current_placement_snapshot_id or 0) == int(snapshot.id)

        record_actions = {
            row.action for row in db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == tenant_id,
                InternshipAuditTrail.target_type == 'INTERN_STUDENT',
                InternshipAuditTrail.target_id == record_id,
            )).all()
        }
        for action in ('ASSIGN_POSITION', 'PLACEMENT_SNAPSHOT', 'ASSIGN_ADVISOR'):
            assert action in record_actions, (action, sorted(record_actions))

        match_actions = {
            row.action for row in db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == tenant_id,
                InternshipAuditTrail.target_type == 'MATCH',
                InternshipAuditTrail.target_id == match_id,
            )).all()
        }
        assert 'MANUAL_MATCH' in match_actions
        assert 'MATCH_CONFIRM' in match_actions

        print('[e2e-ix-009-db] PASS', {
            'recordId': record_id,
            'positionId': position_id,
            'companyId': company_id,
            'applicationId': application_id,
            'matchId': match_id,
            'placementSnapshotId': snapshot.id,
            'advisorName': advisor_name,
            'companyBlacklistedAfterPlacement': True,
        })
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
