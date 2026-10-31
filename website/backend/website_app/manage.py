"""Local administrator bootstrap. Prompts never echo a password."""
import argparse
import getpass
from uuid import uuid4
from sqlalchemy import select, delete
from website_app.auth import WebsiteUser, WebsiteSession, AuthAudit, hash_password
from website_app.db import get_sessionmaker

def main():
    parser = argparse.ArgumentParser(description='官网独立管理账号维护')
    parser.add_argument('action', choices=['create-user', 'disable-user', 'reset-password'])
    parser.add_argument('username')
    parser.add_argument('--name', default='官网编辑')
    parser.add_argument('--role', choices=['editor', 'publisher', 'superadmin'], default='editor')
    args = parser.parse_args()
    import re
    if not re.fullmatch(r'[a-z0-9_.@-]{1,80}', args.username):
        raise SystemExit('账号须为小写字母、数字或 . _ @ -，最长 80 字符')
    with get_sessionmaker()() as db:
        user = db.scalar(select(WebsiteUser).where(WebsiteUser.username == args.username).with_for_update())
        if args.action == 'create-user':
            if user:
                raise SystemExit('账号已存在，未覆盖')
            password = getpass.getpass('官网账号密码（不回显）：')
            if password != getpass.getpass('再次输入密码：'):
                raise SystemExit('两次密码不一致，未创建')
            user = WebsiteUser(id=uuid4().hex, username=args.username, display_name=args.name, role=args.role, active=True, password_hash=hash_password(password))
            db.add(user)
        else:
            if not user:
                raise SystemExit('账号不存在')
            if args.action == 'disable-user':
                user.active = False
            else:
                password = getpass.getpass('新密码（不回显）：')
                if password != getpass.getpass('再次输入密码：'):
                    raise SystemExit('两次密码不一致，未更改')
                user.password_hash = hash_password(password)
            db.execute(delete(WebsiteSession).where(WebsiteSession.user_id == user.id))
        db.add(AuthAudit(id=uuid4().hex, user_id=user.id, action=args.action.upper()))
        db.commit()
    print('官网账号操作已完成')

if __name__ == '__main__':
    main()
