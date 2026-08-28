"""Graduation grade scoring-policy evidence hardening."""
from __future__ import annotations

import hashlib
import json
from sqlalchemy import func, select
from app.core.exceptions import AppException, not_found
from app.models import GraduationBatch, GraduationGrade, GraduationStudent
from app.services.db_service import _tid, session


def _install_grade_policy_hardening() -> None:
    from app.modules.graduation.services import graduation_grade_service as grade
    from app.modules.graduation.services import graduation_batch_service as batch
    old_sources = grade._source_scores
    old_update_batch = batch.update_batch
    old_set_rules = batch.set_rules
    def source_scores(db, stu):
        result = dict(old_sources(db, stu))
        raw = result.get("sourceSnapshotHash") or ""
        weights = grade._weights(db, stu)
        policy = {"weights": {k: float(weights[k]) for k in sorted(weights)}, "gradeCutoffs": {"A": 90, "B": 80, "C": 70, "D": 60}}
        policy_hash = hashlib.sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        result["rawSourceSnapshotHash"] = raw
        result["scorePolicyHash"] = policy_hash
        result["sourceSnapshotHash"] = hashlib.sha256(json.dumps({"source": raw, "policy": policy_hash}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return result

    def _score_policy_changed(batch_row, proposed_rules):
        old = dict((batch_row.rules_config or {}).get("score") or {})
        new = dict((proposed_rules or {}).get("score") or {})
        return old != new

    def _assert_score_rules_mutable(batch_id, proposed_rules):
        with session() as db:
            b = db.scalars(select(GraduationBatch).where(GraduationBatch.id == int(batch_id), GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).first()
            if not b: raise not_found("毕设批次不存在")
            if not _score_policy_changed(b, proposed_rules): return
            affected = int(db.scalar(select(func.count()).select_from(GraduationGrade).join(GraduationStudent, GraduationStudent.id == GraduationGrade.gd_student_id).where(
                GraduationGrade.tenant_id == _tid(), GraduationGrade.is_deleted.is_(False), GraduationGrade.status.in_(("CALCULATED", "REVIEWED", "PUBLISHED")),
                GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id), GraduationStudent.is_deleted.is_(False)
            )) or 0)
            if affected: raise AppException("DATA_CONFLICT", f"当前批次已有 {affected} 条成绩证据，不能直接修改成绩权重；请先撤回并重新核算")

    def update_batch(batch_id, body):
        data = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else dict(body)
        if "rules" in data and data["rules"] is not None:
            with session() as db:
                b = db.scalars(select(GraduationBatch).where(GraduationBatch.id == int(batch_id), GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).first()
                proposed = batch._validate_and_merge_rules(b.rules_config or {}, data.get("rules"))
            _assert_score_rules_mutable(batch_id, proposed)
        return old_update_batch(batch_id, body)

    def set_rules(batch_id, rules):
        with session() as db:
            b = db.scalars(select(GraduationBatch).where(GraduationBatch.id == int(batch_id), GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).first()
            proposed = batch._validate_and_merge_rules(b.rules_config or {}, rules)
        _assert_score_rules_mutable(batch_id, proposed)
        return old_set_rules(batch_id, rules)

    grade._source_scores = source_scores
    batch.update_batch = update_batch
    batch.set_rules = set_rules
