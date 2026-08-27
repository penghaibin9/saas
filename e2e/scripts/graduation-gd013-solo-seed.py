#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import GraduationBatch, GraduationFinal, GraduationMentor, GraduationStudent, StudentProfile

TENANT_ID = 1000000000000000007
RUN_ID = str(os.getenv('GITHUB_RUN_ID') or 'local').strip()
BATCH_NO = f'GD013-SOLO-{RUN_ID}'
BATCH_NAME = f'E2E GD013 SOLO {RUN_ID}'


def mentor(db, teacher_no: str, teacher_name: str, title: str):
    row = db.scalars(select(GraduationMentor).where(
        GraduationMentor.tenant_id == TENANT_ID,
        GraduationMentor.teacher_no == teacher_no,
        GraduationMentor.is_deleted.is_(False),
    )).first()
    if row is None:
        row = GraduationMentor(
            tenant_id=TENANT_ID,
            teacher_no=teacher_no,
            teacher_name=teacher_name,
            mentor_type='INTERNAL',
            title=title,
            research_direction='GD013 solo diagnostic',
            max_capacity=20,
            current_count=0,
            qualification_status='QUALIFIED',
        )
        db.add(row)
        db.flush()
    else:
        row.teacher_name = teacher_name
        row.title = title
        row.qualification_status = 'QUALIFIED'
        row.is_deleted = False
    return row


def main() -> int:
    if os.getenv('E2E_ALLOW_DESTRUCTIVE_TESTS') != 'true':
        raise SystemExit('E2E_ALLOW_DESTRUCTIVE_TESTS=true is required')
    if not any(x in str(os.getenv('DATABASE_URL') or '').lower() for x in ('e2e', 'test')):
        raise SystemExit('refusing non-E2E database')

    db = get_sessionmaker()()
    try:
        profile = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == TENANT_ID,
            StudentProfile.student_no == 'E2E20260002',
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not profile:
            raise SystemExit('missing canonical E2E20260002 profile')

        mentor_a = mentor(db, 'e2e_advisor_a', 'E2E指导教师A', '副教授')
        reviewer = mentor(db, 'e2e_reviewer', 'E2E评阅教师', '讲师')

        batch = GraduationBatch(
            tenant_id=TENANT_ID,
            batch_name=BATCH_NAME,
            batch_no=BATCH_NO,
            academic_year='2025-2026',
            grade_year='2026届',
            planned_count=1,
            status='RUNNING',
            archive_status='NOT_ARCHIVED',
            stage_config=[],
            rules_config={},
        )
        db.add(batch)
        db.flush()

        student = GraduationStudent(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            student_id=profile.id,
            student_no=profile.student_no,
            name='E2E学生B',
            class_id=str(profile.class_id or ''),
            college_id=str(profile.college_id or ''),
            major_id=str(profile.major_id or ''),
            eligibility_status='QUALIFIED',
            mentor_id=mentor_a.id,
            advisor_name=mentor_a.teacher_name,
            stage='FINAL_CHECK',
            record_status='ACTIVE',
        )
        db.add(student)
        db.flush()

        final = GraduationFinal(
            tenant_id=TENANT_ID,
            gd_student_id=student.id,
            final_type='定稿',
            version=f'g13-{RUN_ID[-12:]}',
            submit_at=datetime.now(timezone.utc),
            plagiarism_rate='8.0%',
            plagiarism_status='已检测',
            status='APPROVED',
            active_key=None,
            reviewer='GD013 SOLO',
            review_comment='solo prerequisite',
            review_time=datetime.now(timezone.utc),
            attachments_json=[],
        )
        db.add(final)
        db.commit()

        fixture = {
            'runId': RUN_ID,
            'batchId': str(batch.id),
            'batchName': batch.batch_name,
            'mentorId': str(mentor_a.id),
            'reviewerMentorId': str(reviewer.id),
            'student': {
                'gdStudentId': str(student.id),
                'studentNo': 'E2E20260002',
                'name': 'E2E学生B',
            },
        }
        out = Path('../e2e/runtime-logs/gd013-solo-fixture.json')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(fixture, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
