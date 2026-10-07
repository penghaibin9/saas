from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
def main():
 p=argparse.ArgumentParser();p.add_argument('--confirm',action='store_true');a=p.parse_args()
 if not a.confirm: print('refuse: pass --confirm');return 2
 from app.db.session import get_sessionmaker
 from app.models import Tenant
 from app.services.sandbox_service import SANDBOX_TID,SANDBOX_CODE
 from app.services.sandbox_school_internship_operational_seed import seed_internship_operational_coverage
 db=get_sessionmaker()()
 try:
  t=db.get(Tenant,SANDBOX_TID)
  if not t or t.tenant_code!=SANDBOX_CODE: raise RuntimeError('target tenant identity check failed')
  print(json.dumps(seed_internship_operational_coverage(db,SANDBOX_TID),ensure_ascii=False,indent=2));return 0
 finally: db.close()
if __name__=='__main__': raise SystemExit(main())
