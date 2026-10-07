"""分阶段建设标准沙箱学校：阶段 5，2027 届毕业设计早期全过程。"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from sqlalchemy import func, select
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]

def _count(db, model, tid):
    return int(db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == tid, model.is_deleted.is_(False))) or 0)

def main():
    p=argparse.ArgumentParser(); m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--dry-run',action='store_true'); m.add_argument('--confirm',action='store_true'); a=p.parse_args()
    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import GraduationStudent, Tenant
    from app.services.sandbox_school_domain_seed import _roster, _seed_graduation
    from app.services.sandbox_school_graduation_mentor_reconcile import reconcile_graduation_mentor_workload
    from app.services.sandbox_school_graduation_process_seed import seed_school_graduation_process_20k, validate_school_graduation_process_20k
    from app.services.sandbox_school_mentor_pool import ensure_role_and_advisor_scope, mentor_user_pools
    from app.services.sandbox_school_professional_reconcile import _professionalize_graduation
    if not db_enabled(): return 2
    tid=SANDBOX_SCHOOL.tenant_id; db=get_sessionmaker()()
    try:
        old,new=db.get(Tenant,TRIAL_SCHOOL.tenant_id),db.get(Tenant,tid)
        if old is None or old.tenant_code!=TRIAL_SCHOOL.tenant_code: return 3
        if new is None or new.tenant_code!=SANDBOX_SCHOOL.tenant_code: return 4
        current=_count(db,GraduationStudent,tid)
        print(json.dumps({'tenantId':str(tid),'currentStudents':current,'targetStudents':6400},ensure_ascii=False))
        if a.dry_run: return 0 if current==0 else 5
        if current: return 5
        roster=_roster(db,tid,grades=('2024',))
        if len(roster)!=6400: raise RuntimeError(f'2024级学生范围异常: {len(roster)}')
        base=_seed_graduation(db,tid,roster)
        professional=_professionalize_graduation(db,tid)
        _,users=mentor_user_pools(db,tid)
        role=ensure_role_and_advisor_scope(db,tid,'GD_MENTOR',users)
        mentors=reconcile_graduation_mentor_workload(db,tid,users)
        process=seed_school_graduation_process_20k(db,tid)
        acceptance=validate_school_graduation_process_20k(db,tid)
        print(json.dumps({'base':base,'professional':professional,'role':role,'mentors':mentors,
                          'process':process,'acceptance':acceptance},ensure_ascii=False,indent=2,default=str))
        return 0
    except Exception: db.rollback(); raise
    finally: db.close()
if __name__=='__main__': raise SystemExit(main())
