#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import GraduationDefenseGroup, GraduationStudent

TENANT_ID = 1000000000000000007
RUN_ID = str(os.getenv('GITHUB_RUN_ID') or 'local').strip()
GROUP_NAME = f'GD013-DIAG-{RUN_ID}'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    db = get_sessionmaker()()
    try:
        group = db.scalars(select(GraduationDefenseGroup).where(
            GraduationDefenseGroup.tenant_id == TENANT_ID,
            GraduationDefenseGroup.group_name == GROUP_NAME,
            GraduationDefenseGroup.is_deleted.is_(False),
        )).first()
        require(group is not None, 'GD013 solo: group missing')
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == TENANT_ID,
            GraduationStudent.batch_id == group.batch_id,
            GraduationStudent.student_no == 'E2E20260002',
            GraduationStudent.is_deleted.is_(False),
        )).first()
        require(student is not None, 'GD013 solo: student B missing')
        evidence = {
            'groupId': str(group.id),
            'groupName': group.group_name,
            'chairMentorId': str(group.chair_mentor_id or ''),
            'groupStudentCount': int(group.student_count or 0),
            'groupConflict': group.conflict or '',
            'studentMentorId': str(student.mentor_id or ''),
            'studentDefenseGroupId': str(student.defense_group_id or ''),
        }
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        require(group.chair_mentor_id is not None, 'GD013 solo: chair_mentor_id missing')
        require(int(group.chair_mentor_id) == int(student.mentor_id or 0), 'GD013 solo: chair mentor != student advisor')
        require(int(student.defense_group_id or 0) == int(group.id), 'GD013 solo: student assignment not persisted')
        require(int(group.student_count or 0) == 1, f'GD013 solo: expected student_count=1, got {group.student_count}')
        require(bool(group.conflict), 'GD013 solo: conflict not persisted despite chair == advisor')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
