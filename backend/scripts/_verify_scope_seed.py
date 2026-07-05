"""一次性校验：dev.db 中 t_teacher_student_scope 存在且范围种子可落地（幂等）。"""
from __future__ import annotations

import _dev_env  # noqa: F401

from sqlalchemy import select, text

from _seed_teacher_scope import seed_teacher_scope
from app.db.session import get_sessionmaker
from app.models import TeacherStudentScope

db = get_sessionmaker()()
tbl = db.execute(text("SELECT name FROM sqlite_master WHERE name='t_teacher_student_scope'")).all()
print("table:", tbl)
print("seed:", seed_teacher_scope(db))
print("rows:", len(db.execute(select(TeacherStudentScope)).all()))
db.close()
