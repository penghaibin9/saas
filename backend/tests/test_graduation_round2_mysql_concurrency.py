"""毕业设计第2轮：MySQL 唯一约束 10 并发兜底验收。

只验证数据库最终防线；服务层行锁/状态机由同文件静态契约测试覆盖。
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import get_sessionmaker
from app.models import (
    GraduationDefenseScore, GraduationFinal, GraduationGrade, GraduationGradeAppeal,
    GraduationPlagiarismCheck, GraduationProposal, GraduationReview, GraduationPeerReview,
    GraduationTopicChoice,
)


TENANT = 910000000000000001


def _race(factory, workers=10):
    barrier = Barrier(workers)

    def insert(index):
        db = get_sessionmaker()()
        try:
            barrier.wait()
            db.add(factory(index))
            db.commit()
            return "ok"
        except IntegrityError:
            db.rollback()
            return "conflict"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(insert, range(workers)))
    assert results.count("ok") == 1
    assert results.count("conflict") == workers - 1


@pytest.mark.usefixtures("db_mode")
def test_mysql_unique_constraints_reject_ten_concurrent_duplicates():
    factories = [
        lambda i: GraduationTopicChoice(
            id=910010000000000000 + i, tenant_id=TENANT, round_id=1, gd_student_id=1,
            topic_id=100 + i, choice_order=1, status="PENDING",
        ),
        lambda i: GraduationProposal(
            id=910020000000000000 + i, tenant_id=TENANT, gd_student_id=2,
            version=f"v{i + 1}", status="PENDING_REVIEW", active_key="pending:2",
        ),
        lambda i: GraduationProposal(
            id=910030000000000000 + i, tenant_id=TENANT, gd_student_id=3,
            version="v1", status="REJECTED", active_key=None,
        ),
        lambda i: GraduationFinal(
            id=910040000000000000 + i, tenant_id=TENANT, gd_student_id=4,
            final_type="定稿", version=f"v{i + 1}", status="PENDING_REVIEW", active_key="pending:4",
        ),
        lambda i: GraduationReview(
            id=910050000000000000 + i, tenant_id=TENANT, gd_student_id=5,
            gd_final_id=500, reviewer_name="评阅教师", reviewer_mentor_id=50, status="ASSIGNED",
        ),
        lambda i: GraduationPlagiarismCheck(
            id=910060000000000000 + i, tenant_id=TENANT, gd_student_id=6,
            gd_final_id=600, status="CHECKING", active_key="checking:600",
        ),
        lambda i: GraduationDefenseScore(
            id=910070000000000000 + i, tenant_id=TENANT, gd_student_id=7,
            defense_group_id=70, round_no=1, judge_name="评委",
            judge_mentor_id=700, judge_identity="MENTOR:700", status="SCORED",
        ),
        lambda i: GraduationDefenseScore(
            id=910080000000000000 + i, tenant_id=TENANT, gd_student_id=8,
            defense_group_id=80, round_no=2, judge_name="评委",
            judge_mentor_id=800, judge_identity="MENTOR:800", status="PENDING",
        ),
        lambda i: GraduationGrade(
            id=910090000000000000 + i, tenant_id=TENANT, gd_student_id=9, status="DRAFT",
        ),
        lambda i: GraduationGradeAppeal(
            id=910100000000000000 + i, tenant_id=TENANT, gd_student_id=10,
            reason="并发申诉测试", status="PENDING", active_key="pending:10",
        ),
        lambda i: GraduationPeerReview(
            id=910110000000000000 + i, tenant_id=TENANT, gd_student_id=11,
            reviewer_gd_student_id=12, task_version=1, status="ASSIGNED",
        ),
    ]
    for factory in factories:
        _race(factory)


def test_services_keep_required_row_locks_and_closed_match_contract():
    from pathlib import Path

    root = Path(__file__).parents[1] / "app" / "modules" / "graduation" / "services"
    required = {
        "graduation_topic_round_service.py": ("with_for_update", 'r.status != "CLOSED"'),
        "graduation_service.py": ("with_for_update", "active_key"),
        "graduation_review_service.py": ("with_for_update", "reviewer_mentor_id"),
        "graduation_defense_score_service.py": ("with_for_update", "judge_identity"),
        "graduation_grade_service.py": ("_stu_for_update", "source_snapshot_hash"),
        "graduation_more_service.py": ("with_for_update", "active_key"),
    }
    for filename, tokens in required.items():
        source = (root / filename).read_text(encoding="utf-8")
        for token in tokens:
            assert token in source, f"{filename} 缺少并发契约 {token}"
