"""建 t_student_parent_link 表(dev 库缺失，迁移 portal_r1_parent_link 未应用)并给张同学
种 1 个已授权家长，使学生 PC 门户「我的档案 · 家长授权」出真实数据、修复 guardians 500。
仅建这一张表(checkfirst，附加式，无破坏)；纯 INSERT；仅 demo-school。
用法：cd backend && .venv/Scripts/python.exe scripts/_seed_demo_student_guardian.py
"""
from __future__ import annotations
import hashlib
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import get_engine
from app.services.db_service import session
import app.models as M

DEMO = 1000000000000000003
PROFILE_ID = 23
NO = "2026D0006"
PHONE = "13900006666"
SCOPES = ["ACADEMIC_GRADE", "FEE_AID_STATUS", "CAMPUS_ALERT", "CAREER_PROGRESS"]


def main():
    # 1) 建表（仅这两张，checkfirst）：家长授权 + 门户登录验证码
    M.StudentParentLink.__table__.create(bind=get_engine(), checkfirst=True)
    M.PortalLoginOtp.__table__.create(bind=get_engine(), checkfirst=True)
    print("[TABLE] t_student_parent_link / t_portal_login_otp 就绪（checkfirst）")
    # 2) 种家长
    with session() as db:
        ph = hashlib.sha256(PHONE.encode("utf-8")).hexdigest()
        dup = db.scalars(select(M.StudentParentLink).where(
            M.StudentParentLink.tenant_id == DEMO, M.StudentParentLink.student_id == PROFILE_ID,
            M.StudentParentLink.guardian_phone_hash == ph)).first()
        if dup:
            print("[SKIP] 家长授权已存在 id=", dup.id)
            return
        row = M.StudentParentLink(tenant_id=DEMO, student_id=PROFILE_ID, student_no=NO,
                                  guardian_name="张建国", relation="FATHER",
                                  guardian_phone_encrypted=PHONE, guardian_phone_hash=ph,
                                  visible_scopes=SCOPES, link_status="ACTIVE")
        db.add(row)
        db.commit()
        print("[OK] 已为张同学种家长授权 id=", row.id, "(张建国·父亲)")


if __name__ == "__main__":
    main()
