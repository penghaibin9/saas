"""20K academic-quality evaluation score truth must reuse production policy."""
from __future__ import annotations

import pytest

TID = 1000000000000000001


def test_quality_seed_projection_delegates_to_production_policy():
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as policy
    from app.services import sandbox_school_academic_quality_seed as quality_seed

    values = (84.0, 100.0, 100.0, 100.0)
    composite, level = quality_seed._canonical_projection(*values)
    expected = policy._composite(*values)
    assert composite == expected
    assert level == policy._level(expected)
    assert composite == 90.4
    assert level == "EXCELLENT"


@pytest.mark.usefixtures("db_mode")
def test_quality_score_truth_detects_old_weight_and_level_drift():
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationRecord, AaEvaluationResult, AaEvaluationTask
    from app.services import sandbox_school_academic_quality_seed as quality_seed

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        batch = AaEvaluationBatch(
            tenant_id=TID,
            batch_name="20K评教算法真值合同",
            anonymous=True,
            status="ARCHIVED",
        )
        db.add(batch)
        db.flush()
        teaching_task_id = 99887766
        task_ids = {}
        for evaluator_type in ("STUDENT", "SELF", "PEER", "SUPERVISOR"):
            task = AaEvaluationTask(
                tenant_id=TID,
                batch_id=batch.id,
                teaching_task_id=teaching_task_id,
                teacher_key="quality_truth_teacher",
                teacher_name="算法真值教师",
                evaluator_type=evaluator_type,
                evaluator_key=None if evaluator_type == "STUDENT" else f"actor_{evaluator_type.lower()}",
                submitted_count=2 if evaluator_type == "STUDENT" else 1,
                status="SUBMITTED",
            )
            db.add(task)
            db.flush()
            task_ids[evaluator_type] = int(task.id)

        for score in (83, 85):
            db.add(AaEvaluationRecord(
                tenant_id=TID,
                batch_id=batch.id,
                task_id=task_ids["STUDENT"],
                teacher_key="quality_truth_teacher",
                evaluator_type="STUDENT",
                answers_json="{}",
                objective_score=score,
            ))
        for evaluator_type in ("SELF", "PEER", "SUPERVISOR"):
            db.add(AaEvaluationRecord(
                tenant_id=TID,
                batch_id=batch.id,
                task_id=task_ids[evaluator_type],
                teacher_key="quality_truth_teacher",
                evaluator_type=evaluator_type,
                answers_json="{}",
                objective_score=100,
            ))

        result = AaEvaluationResult(
            tenant_id=TID,
            batch_id=batch.id,
            teaching_task_id=teaching_task_id,
            teacher_key="quality_truth_teacher",
            teacher_name="算法真值教师",
            course_name="算法真值课程",
            student_avg=84,
            student_count=2,
            self_score=100,
            peer_avg=100,
            peer_count=1,
            supervisor_avg=100,
            supervisor_count=1,
            # Historical sandbox drift: 70/10/10/10 plus student-average-only level.
            composite_score=88.8,
            level="PASS",
            published=True,
        )
        db.add(result)
        db.commit()

        drift = quality_seed._evaluation_score_truth(db, TID)
        assert drift["checked"] == 1
        assert drift["mismatchCount"] == 1
        fields = " ".join(drift["samples"][0]["fields"])
        assert "compositeScore" in fields
        assert "level" in fields

        composite, level = quality_seed._canonical_projection(84.0, 100.0, 100.0, 100.0)
        result.composite_score = composite
        result.level = level
        db.commit()
        aligned = quality_seed._evaluation_score_truth(db, TID)
        assert aligned == {"checked": 1, "mismatchCount": 0, "samples": []}
    finally:
        db.close()
        set_tenant(None)
