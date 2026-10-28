"""Initialize an empty, migrated independent-school database. Never resets an existing school.

Run using the backend virtual environment and its configured environment variables.
The receipt is created exclusively with private permissions; no password is printed.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys



def initialize(code,name,login,receipt):
    from sqlalchemy import select,text
    from app.config import settings
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker,get_engine
    from app.models import Tenant,User
    from app.services.system_authorization import bootstrap_school,audit
    if not code or len(code)>50 or not name or len(name)>100 or not login or len(login)>50:
        raise ValueError('学校代码、学校名称和管理员账号必填，且不能超出长度限制')
    path=Path(receipt).resolve()
    if not path.parent.is_dir(): raise ValueError('请先创建受控交付目录')
    password='Aa9!'+secrets.token_urlsafe(20)
    wrote=False;commit_started=False
    # MySQL named locks belong to the connection; keep it pinned across commit/rollback.
    with get_engine().connect() as connection, get_sessionmaker()(bind=connection) as db:
        lock=db.scalar(text("SELECT GET_LOCK(CONCAT(DATABASE(), :suffix), 10)"),{'suffix':':school-init'})
        if lock!=1: raise ValueError('另一个初始化正在执行，请稍后核对')
        try:
            revision=db.scalar(text('SELECT version_num FROM alembic_version'))
            if not settings.EXPECTED_ALEMBIC_REVISION or revision!=settings.EXPECTED_ALEMBIC_REVISION:
                raise ValueError('数据库结构尚未就绪，请先按交付流程完成增量迁移')
            if db.scalar(select(Tenant.id).limit(1)) or db.scalar(select(User.id).limit(1)):
                raise ValueError('数据库已有学校或账号，禁止重复初始化；请从系统管理继续维护')
            school=Tenant(tenant_code=code,school_name=name,status='ACTIVE',deploy_mode='PRIVATE')
            db.add(school);db.flush()
            owner=User(tenant_id=school.id,login_name=login,real_name='学校初始化负责人',user_type='SCHOOL_ADMIN',
                password_hash=hash_password(password),status='ACTIVE',must_change_password=True)
            db.add(owner);db.flush();bootstrap_school(db,school.id)
            audit(db,{'tenantId':school.id,'userId':owner.id,'realName':owner.real_name,'currentRoleCode':'SYSTEM_ADMIN'},
                  'SCHOOL_INITIALIZE','school',school.id,{'reason':'独立学校首次安装'})
            descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(descriptor,'w',encoding='utf-8') as handle:
                json.dump({'schoolCode':code,'loginName':login,'temporaryPassword':password,
                    'notice':'首次登录必须修改；仅受控交付给学校负责人，正常登录后销毁本回执'},handle,ensure_ascii=False,indent=2)
            wrote=True;commit_started=True;db.commit()
        except Exception:
            db.rollback()
            if wrote and not commit_started:path.unlink(missing_ok=True)
            raise
        finally:
            db.execute(text("SELECT RELEASE_LOCK(CONCAT(DATABASE(), :suffix))"),{'suffix':':school-init'})
    return path


def main():
    parser=argparse.ArgumentParser(description='仅初始化已迁移且完全为空的独立学校数据库')
    parser.add_argument('--school-code',required=True);parser.add_argument('--school-name',required=True)
    parser.add_argument('--admin-login',required=True);parser.add_argument('--receipt-file',required=True)
    args=parser.parse_args()
    output=initialize(args.school_code,args.school_name,args.admin_login,args.receipt_file)
    print(f'学校初始化完成。请受控交付回执：{output}')


if __name__ == '__main__':
    main()
