"""Stage D integration guard: explanation stays downstream of existing business truth."""
from __future__ import annotations

import inspect


def test_selection_trace_is_attached_after_canonical_rule_decision():
    from app.modules.academic_affairs.services import academic_affairs_selection_service as final
    from app.modules.academic_affairs.services import academic_affairs_selection_decision_trace as trace

    source = inspect.getsource(final.student_enroll)
    # Existing canonical validation remains authoritative and trace attachment is in its
    # exception path; no DecisionTrace function is allowed to replace _validate_enroll.
    assert "_base._validate_enroll(" in source
    assert "except AppException as exc" in source
    assert "selection_trace.attach_selection_trace(" in source
    trace_source = inspect.getsource(trace)
    assert "_validate_enroll(" not in trace_source
    assert "change_student_status(" not in trace_source
    assert "selected_count =" not in trace_source


def test_graduation_trace_consumes_existing_evaluator_result_only():
    from app.modules.academic_affairs.services import academic_affairs_graduation_decision_trace as trace
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable
    from app.modules.academic_affairs.services import mobile_academic_affairs_service as mobile

    trace_source = inspect.getsource(trace)
    for forbidden in (
        "_run_items(", "_check_credit(", "_program_resolution(", "change_student_status(",
        "GraduationEvaluationRun(", "GraduationDecisionFact(",
    ):
        assert forbidden not in trace_source

    preview = inspect.getsource(immutable.evaluate_preview)
    assert "evaluated = evaluate_student(db, student)" in preview
    assert "build_graduation_student_explanation(student, evaluated)" in preview
    assert '"formalRunCreated": False' in preview
    assert "GraduationEvaluationRun(" not in preview

    progress = inspect.getsource(mobile.graduation_progress_my)
    assert "evaluated = graduation.evaluate_student(db, student)" in progress
    assert "build_graduation_student_explanation(student, evaluated)" in progress
    assert '"formalRunCreated": False' in progress
    assert "item_results_json" not in progress


def test_stage_d_has_no_llm_authority_or_technical_student_leakage():
    from app.modules.academic_affairs.services import academic_affairs_decision_trace as base
    from app.modules.academic_affairs.services import academic_affairs_graduation_decision_trace as graduation
    from app.modules.academic_affairs.services import academic_affairs_selection_decision_trace as selection

    source = "\n".join((inspect.getsource(base), inspect.getsource(selection), inspect.getsource(graduation))).lower()
    for forbidden in ("openai", "anthropic", "langchain", "completion.create", "chat.completions"):
        assert forbidden not in source
    # Renderer student branch must not add target/trace metadata; those are teacher/admin only.
    render = inspect.getsource(base.render_zh_cn)
    assert 'if audience in {"teacher", "admin"}' in render
    assert 'out.update({' in render
