"""Prepare retained synthetic accounts/tasks in migrated yueke_optimizer_test_* MySQL only."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.aa_optimizer_mysql_acceptance import scenario
from app.db.session import get_sessionmaker
from app.models import User, Tenant, College, Major, SchoolClass, AaTeachingTask, StudentProfile, RolePermission, Permission
from app.core.security import hash_password
from sqlalchemy import select


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--classless',action='store_true',help='Use formal roster without an administrative class on the task')
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Output already exists; preserve the previous scenario receipt')
    password=os.environ.get('E2E_OPTIMIZER_PASSWORD','')
    if len(password)<12:raise SystemExit('Set E2E_OPTIMIZER_PASSWORD to a synthetic test password of at least 12 characters')
    s=scenario.__wrapped__()  # Checks exact isolated database identity and real Alembic head first.
    with get_sessionmaker()() as db:
        for identity in ['user','teacher','student']:
            db.get(User,int(s[identity]['userId'][3:])).password_hash=hash_password(password)
        college=College(tenant_id=s['tid'],college_name='验收学院',code='OPT',status='ACTIVE');db.add(college);db.flush()
        major=Major(tenant_id=s['tid'],college_id=college.id,major_name='验收专业',code='OPT',status='ACTIVE');db.add(major);db.flush()
        group=SchoolClass(tenant_id=s['tid'],major_id=major.id,class_name='验收教学班',class_code='OPT',grade='2026',status='ACTIVE');db.add(group);db.flush()
        if not args.classless:db.get(AaTeachingTask,int(s['task'])).class_id=group.id
        for student in db.scalars(select(StudentProfile).where(StudentProfile.tenant_id==s['tid'])).all():student.class_id=group.id
        s['classId']='' if args.classless else str(group.id)
        for identity,codes in [('user',['academicAffairs.timeslot.view','academicAffairs.teachingTask.view','academicAffairs.classroom.view','academicAffairs.class.view','academicAffairs.term.view']),('teacher',['academicAffairs.timeslot.view','academicAffairs.term.view'])]:
            role=int(s[identity]['activeContextId'].split(':')[1])
            for code in codes:
                perm=db.scalar(select(Permission).where(Permission.permission_code==code))
                if perm is None:
                    perm=Permission(permission_code=code,permission_name=code,module_code='academicAffairs',action='VIEW');db.add(perm);db.flush()
                db.add(RolePermission(tenant_id=s['tid'],role_id=role,permission_id=perm.id,status='ACTIVE'))
        s['tenantCode']=db.get(Tenant,s['tid']).tenant_code
        db.commit()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as output:json.dump(s,output)
    print('Prepared isolated draft',s['batch'],'and role accounts; no timetable items created')


if __name__=='__main__':main()
