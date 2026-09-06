from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
def main():
 p=argparse.ArgumentParser();p.add_argument('--confirm',action='store_true');a=p.parse_args()
 if not a.confirm:print('refuse: pass --confirm');return 2
 from app.db.session import get_sessionmaker
 from app.models import Tenant
 from app.services.sandbox_service import SANDBOX_CODE,SANDBOX_TID
 from app.services.sandbox_school_academic_operational_seed import seed_academic_operational_coverage
 db=get_sessionmaker()
 with db() as s:
  t=s.get(Tenant,SANDBOX_TID)
  if not t or t.tenant_code!=SANDBOX_CODE:raise RuntimeError('target tenant identity check failed')
  print(json.dumps(seed_academic_operational_coverage(s,SANDBOX_TID),ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
