"""Agreement template scope contracts for preview/options/generate."""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.internship.routers import internship_agreement_template as template_router
from app.modules.internship.services import internship_agreement_service as agreement_service
from app.modules.internship.services import internship_agreement_template_service as template_service


def _tpl(*, status="ENABLED", colleges=None, majors=None, grades=None, batches=None):
    return SimpleNamespace(
        status=status,
        scope_college_ids=colleges or [],
        scope_major_ids=majors or [],
        scope_grades=grades or [],
        scope_batch_ids=batches or [],
    )


def _rec(batch_id=40):
    return SimpleNamespace(batch_id=batch_id)


def _stu(college_id=10, major_id=20, grade="2024"):
    return SimpleNamespace(college_id=college_id, major_id=major_id, grade=grade)


def test_empty_scope_is_global_and_matches_real_student():
    assert agreement_service.template_scope_matches(_tpl(), _rec(), _stu()) is True


@pytest.mark.parametrize(
    ("template", "student", "record"),
    [
        (_tpl(colleges=[11]), _stu(college_id=10), _rec()),
        (_tpl(majors=[21]), _stu(major_id=20), _rec()),
        (_tpl(grades=["2025"]), _stu(grade="2024"), _rec()),
        (_tpl(batches=[41]), _stu(), _rec(batch_id=40)),
    ],
)
def test_any_scoped_dimension_mismatch_fails_closed(template, student, record):
    assert agreement_service.template_scope_matches(template, record, student) is False
    with pytest.raises(AppException):
        agreement_service.ensure_template_applicable(template, record, student)


def test_all_four_scoped_dimensions_must_match_together():
    template = _tpl(colleges=[10], majors=[20], grades=["2024"], batches=[40])
    assert agreement_service.template_scope_matches(template, _rec(), _stu()) is True
    agreement_service.ensure_template_applicable(template, _rec(), _stu())


def test_disabled_template_is_rejected_even_when_scope_matches():
    with pytest.raises(AppException):
        agreement_service.ensure_template_applicable(_tpl(status="DISABLED"), _rec(), _stu())


def test_generate_keeps_service_layer_scope_guard():
    source = inspect.getsource(agreement_service.generate)
    assert "ensure_template_applicable(tpl, rec, stu)" in source


def test_options_route_accepts_student_context_and_service_uses_four_dimensional_match():
    router_source = inspect.getsource(template_router.template_options)
    options_source = inspect.getsource(template_service.enabled_options)
    assert "internshipId" in inspect.signature(template_router.template_options).parameters
    assert "internship_id=internshipId" in router_source
    assert "template_scope_matches(t, rec, stu)" in options_source
    assert "not in your data scope" not in options_source  # Chinese message remains user-facing, no hidden bypass branch.


def test_admin_scope_filter_keeps_global_templates_visible():
    items = [
        {"scopeBatchIds": []},
        {"scopeBatchIds": [40]},
        {"scopeBatchIds": [41]},
    ]
    filtered = template_service._row_scope_matches(items, "scopeBatchIds", 40)
    assert filtered == items[:2]


def test_agreement_view_loads_templates_after_real_internship_selection():
    view = (Path(__file__).parents[2] / "frontend/src/modules/internship/views/AgreementView.vue").read_text(
        encoding="utf-8"
    )
    assert "'genForm.internshipId'() { this.refreshTemplateOptions() }" in view
    assert "internshipId: this.genForm.internshipId" in view
    assert "getEnabledOptions({ batchId: this.batchStore.selectedBatchId })" not in view
