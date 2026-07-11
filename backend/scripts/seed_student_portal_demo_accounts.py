"""初始化学生 PC 门户演示学生账号（真实入库，密码 hash，跨租户隔离）。

创建（幂等）：
  demo-school 租户：账号 student  / 密码 123456 → 绑定本租户学生档案「门户演示学生」
  trial-school 租户：账号 student2 / 密码 123456 → 绑定本租户学生档案「门户试用学生」

要点：
- 密码只存 pbkdf2_sha256 哈希（app.core.security.hash_password），绝不落明文。
- 登录走 /api/v1/auth/login；auth_service_db 按 (tenant_id, real_name) 绑定学生档案并把 student_no 写进令牌。
- userType=STUDENT，令牌 tenantId 为各自租户 → student 只见 demo-school、student2 只见 trial-school。
- 不打开 mock-login；不创建平台超级管理员。

用法（在 backend 目录）：
  python scripts/seed_student_portal_demo_accounts.py --dry-run
  python scripts/seed_student_portal_demo_accounts.py --confirm
DB 连接：遵循 backend/.env（DATABASE_URL 或 DB_DRIVER=mysql + DB_*）；未配置则默认 SQLite ./data/dev.db。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 需要真实 DB；DATABASE_URL / DB_* 仍尊重 backend/.env（此处仅强制启用 DB）
os.environ["DB_ENABLED"] = "true"
try:
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
except Exception:
    pass

# demo-school 复用 _seed_core 的租户 ID；trial-school 为新租户 ID
TID_DEMO = 1000000000000000003
TID_TRIAL = 1000000000000000005

# (tenant_id, tenant_code, school_name, short_name, login_name, real_name, student_no)
ACCOUNTS = [
    (TID_DEMO, "demo-school", "演示职业技术学院", "演示职院", "student", "门户演示学生", "2026PORTAL01"),
    (TID_TRIAL, "trial-school", "试用职业技术学院", "试用职院", "student2", "门户试用学生", "2026TRIAL01"),
]


def main(confirm: bool) -> int:
    from sqlalchemy import select

    from app.core.config import settings
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker, reset_state
    from app.models import StudentProfile, Tenant, TenantBrandConfig, User

    print(f"[seed-portal] DB = {settings.effective_database_url.split('@')[-1] or settings.effective_database_url}")
    reset_state()
    db = get_sessionmaker()()
    planned, created = [], []
    try:
        for default_tid, tcode, sname, short, login, rname, sno in ACCOUNTS:
            # login_name 全局唯一（登录按 login_name 全局解析）：先全局查，已存在则就地确保可用，
            # 不再往别的租户新建同名账号造成重复/歧义。仅当全局不存在时才在默认租户新建。
            u = db.scalars(select(User).where(
                User.login_name == login, User.is_deleted.is_(False))).first()
            tid = u.tenant_id if u else default_tid

            # 1) 租户（仅在需要新建账号且租户缺失时创建）
            if not db.get(Tenant, tid):
                planned.append(f"租户 {tcode}（{sname}）")
                if confirm:
                    db.add(Tenant(id=tid, tenant_code=tcode, school_name=sname, short_name=short, status="ACTIVE"))
                    db.add(TenantBrandConfig(tenant_id=tid, platform_name="学生服务门户",
                                             browser_title="学生服务门户", primary_color="#1677ff",
                                             watermark_text=short))
                    db.flush()

            # 2) 登录账号（演示账号：保证密码=123456、user_type=STUDENT、状态可用）
            if not u:
                planned.append(f"新建账号 {login} / 123456（STUDENT）@ {tcode}")
                if confirm:
                    u = User(tenant_id=tid, login_name=login, real_name=rname,
                             password_hash=hash_password("123456"), user_type="STUDENT", status="ACTIVE")
                    db.add(u); db.flush()
                    created.append(login)
                bound_name = rname
            else:
                planned.append(f"更新账号 {login}（重置密码=123456 + 确认 STUDENT/可用）@ {tcode}")
                if confirm:
                    u.password_hash = hash_password("123456")
                    u.user_type = "STUDENT"
                    u.status = "ACTIVE"
                    db.flush()
                bound_name = u.real_name or rname

            # 3) 学生档案：按「账号真实姓名」绑定（登录 auth 据 real_name 取 student_no）
            sp = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tid, StudentProfile.real_name == bound_name,
                StudentProfile.is_deleted.is_(False))).first()
            if not sp:
                # 避免 student_no 撞唯一约束：占用则换一个
                use_no = sno
                if db.scalars(select(StudentProfile).where(
                        StudentProfile.tenant_id == tid, StudentProfile.student_no == use_no)).first():
                    use_no = sno + "X"
                planned.append(f"学生档案 {bound_name}（{use_no}）@ {tcode}")
                if confirm:
                    db.add(StudentProfile(tenant_id=tid, student_no=use_no, real_name=bound_name, gender="男",
                                          grade="2026", current_stage="ON_CAMPUS",
                                          student_status="NORMAL", status="ACTIVE"))
                    db.flush()
        if confirm:
            db.commit()
    finally:
        db.close()

    if not confirm:
        print("[dry-run] 将创建以下对象（未写库）：")
        for p in planned:
            print("   -", p)
        print(f"[dry-run] 合计 {len(planned)} 项。确认无误后加 --confirm 执行。")
    else:
        print(f"[confirm] 完成。新建账号：{created or '（均已存在）'}")
        print("[confirm] 验证：student/123456→demo-school，student2/123456→trial-school，均 /auth/login 登录。")
    return 0


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--confirm" in args:
        raise SystemExit(main(confirm=True))
    if "--dry-run" in args or not args:
        raise SystemExit(main(confirm=False))
    print("用法：--dry-run | --confirm")
    raise SystemExit(2)
