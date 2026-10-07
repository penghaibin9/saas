#!/usr/bin/env python3
"""Read-only pre-release inventory: never grant roles based on login names.

Run before deploying SEC-01. Affected accounts need independently authorized
real UserRole links or intentional suspension, including the school's first admin.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tenant-id',type=int)
    p.add_argument('--sample-limit',type=int,default=100)
    args=p.parse_args(argv)
    if args.tenant_id is not None and args.tenant_id<=0:p.error('tenant ID must be positive')
    if not 1<=args.sample_limit<=500:p.error('sample-limit must be between 1 and 500')
    from sqlalchemy import and_,exists,func,select
    from app.core.config import settings
    from app.db.session import db_enabled,get_sessionmaker
    from app.models import Role,User,UserRole
    from app.services.auth_service_db import LEGACY_DEMO_ROLE_BY_LOGIN
    if not db_enabled() or settings.db_dialect!='mysql':raise RuntimeError('Explicit MySQL required')
    active_role=exists(select(UserRole.id).join(Role,and_(Role.id==UserRole.role_id,
        Role.tenant_id==UserRole.tenant_id)).where(
        UserRole.user_id==User.id,UserRole.tenant_id==User.tenant_id,
        UserRole.status=='ACTIVE',UserRole.is_deleted.is_(False),
        Role.status.in_(('ACTIVE','ENABLED')),Role.is_deleted.is_(False),
        Role.role_code!='PLATFORM_SUPER_ADMIN'))
    filters=[User.login_name.in_(tuple(LEGACY_DEMO_ROLE_BY_LOGIN)),User.status=='ACTIVE',
        User.is_deleted.is_(False),User.user_type!='PLATFORM_SUPER_ADMIN',~active_role]
    if args.tenant_id is not None:filters.append(User.tenant_id==args.tenant_id)
    db=get_sessionmaker()()
    try:
        count=int(db.scalar(select(func.count()).select_from(User).where(*filters)) or 0)
        rows=db.execute(select(User.id,User.tenant_id).where(*filters).order_by(User.tenant_id,User.id)
                        .limit(args.sample_limit)).all()
        print(json.dumps({'readOnly':True,'affectedAccountCount':count,
            'sample':[{'userId':str(uid),'tenantId':str(tid)} for uid,tid in rows],
            'sampleTruncated':count>len(rows),'releaseBlocked':count>0,
            'automaticRoleGrants':False},ensure_ascii=False,indent=2))
        return 2 if count else 0
    finally:db.close()

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'readOnly':True,'releaseBlocked':True,'errorType':type(exc).__name__,
            'message':'Inventory failed; do not assume there are no affected accounts.'}),file=sys.stderr)
        raise SystemExit(1)
