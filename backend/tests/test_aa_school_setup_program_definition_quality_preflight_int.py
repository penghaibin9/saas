"""INT contracts for authoritative Program credit-quality preflight."""
from __future__ import annotations

import inspect
from decimal import Decimal

import pytest


def _quality():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_quality_preflight as quality
    return quality


def _row(group, payload, *, program_key="SERIES:SER-A:v1", row_no=2):
    return {
        "rowNo": row_no,
        "logicalGroup": group,
        "programKey": program_key,
        "definitionKey": f"{program_key}|{group}|{row_no}",
        "payload": payload,
    }


def _course(code, credit, *, version=1):
    return {"courseCode": code, "version": version, "credit": Decimal(str(credit))}


def test_exact_course_credit_and_practice_credit_prove_a_balanced_definition():
    rows = [
        _row("MAIN", {"totalCredits": Decimal("6")}),
        _row("COURSE", {"courseKey": "CS101@v1", "module": "专业核心", "creditSnapshot": None}),
        _row("COURSE", {"courseKey": "CS102@v1", "module": "专业核心", "creditSnapshot": Decimal("2")}, row_no=3),
        _row("CREDIT_REQUIREMENT", {"module": "专业核心", "creditTarget": Decimal("5")}),
        _row("PRACTICE", {"credit": Decimal("1")}),
    ]
    result = _quality().program_definition_quality_preflight(
        rows,
        course_snapshots=[_course("CS101", 3), _course("CS102", 2)],
    )
    assert result["definitionQualitySafe"] is True
    assert result["errors"] == []
    assert result["warnings"] == []
    assert result["programMetrics"] == [{
        "programKey": "SERIES:SER-A:v1",
        "courseCreditSum": "5",
        "practiceCreditSum": "1",
        "actualCreditSum": "6",
        "totalCredits": "6",
        "moduleActualCredits": {"专业核心": "5"},
        "moduleTargetCredits": {"专业核心": "5"},
    }]


def test_practice_credit_counts_toward_total_but_never_silently_satisfies_course_module_target():
    rows = [
        _row("MAIN", {"totalCredits": Decimal("6")}),
        _row("COURSE", {"courseKey": "CS101@v1", "module": "专业核心"}),
        _row("CREDIT_REQUIREMENT", {"module": "专业核心", "creditTarget": Decimal("5")}),
        _row("PRACTICE", {"credit": Decimal("3")}),
    ]
    result = _quality().program_definition_quality_preflight(
        rows,
        course_snapshots=[_course("CS101", 3)],
    )
    assert result["definitionQualitySafe"] is False
    assert {item["businessCode"] for item in result["errors"]} == {
        "PROGRAM_MODULE_CREDIT_INSUFFICIENT",
    }
    error = result["errors"][0]
    assert error["evidence"] == {
        "module": "专业核心",
        "actualCredit": "3",
        "creditTarget": "5",
    }
    assert "PRACTICE" in error["howToResolve"]


def test_insufficient_total_is_blocker_and_overage_is_warning_matching_program_governance():
    insufficient = _quality().program_definition_quality_preflight(
        [
            _row("MAIN", {"totalCredits": Decimal("5")}),
            _row("COURSE", {"courseKey": "CS101@v1", "module": "核心"}),
            _row("CREDIT_REQUIREMENT", {"module": "核心", "creditTarget": Decimal("3")}),
        ],
        course_snapshots=[_course("CS101", 3)],
    )
    assert insufficient["definitionQualitySafe"] is False
    assert insufficient["errors"][0]["businessCode"] == "PROGRAM_ACTUAL_CREDIT_INSUFFICIENT"
    assert insufficient["errors"][0]["evidence"]["actualCreditSum"] == "3"
    assert insufficient["errors"][0]["evidence"]["totalCredits"] == "5"

    exceeded = _quality().program_definition_quality_preflight(
        [
            _row("MAIN", {"totalCredits": Decimal("3")}),
            _row("COURSE", {"courseKey": "CS101@v1", "module": "核心"}),
            _row("CREDIT_REQUIREMENT", {"module": "核心", "creditTarget": Decimal("3")}),
            _row("PRACTICE", {"credit": Decimal("1")}),
        ],
        course_snapshots=[_course("CS101", 3)],
    )
    assert exceeded["definitionQualitySafe"] is True
    assert exceeded["errors"] == []
    assert exceeded["warnings"][0]["businessCode"] == "PROGRAM_ACTUAL_CREDIT_EXCEEDED"


def test_real_sandbox_school_140_credit_program_is_rejected_before_write_when_seed_definition_only_has_28_course_credits():
    from app.services import sandbox_school_academic_affairs_seed as seed

    public = [(row[0], row[4]) for row in seed.PUBLIC_COURSES]
    major = [(f"M-{row[0]}", row[4]) for row in seed.MAJOR_COURSE_TEMPLATES]
    assert sum((credit for _code, credit in public), Decimal("0")) == Decimal("8")
    assert sum((credit for _code, credit in major), Decimal("0")) == Decimal("20")

    rows = [_row("MAIN", {"totalCredits": Decimal("140")})]
    snapshots = []
    row_no = 2
    for code, credit in public:
        rows.append(_row("COURSE", {"courseKey": f"{code}@v1", "module": "公共基础"}, row_no=row_no))
        snapshots.append(_course(code, credit))
        row_no += 1
    for index, (code, credit) in enumerate(major, start=1):
        module = "专业课程" if index <= 4 else "实践课程"
        rows.append(_row("COURSE", {"courseKey": f"{code}@v1", "module": module}, row_no=row_no))
        snapshots.append(_course(code, credit))
        row_no += 1
    rows.extend([
        _row("CREDIT_REQUIREMENT", {"module": "公共基础", "creditTarget": Decimal("30")}),
        _row("CREDIT_REQUIREMENT", {"module": "专业课程", "creditTarget": Decimal("70")}, row_no=3),
        _row("CREDIT_REQUIREMENT", {"module": "实践课程", "creditTarget": Decimal("40")}, row_no=4),
    ])

    result = _quality().program_definition_quality_preflight(rows, course_snapshots=snapshots)
    assert result["definitionQualitySafe"] is False
    codes = [item["businessCode"] for item in result["errors"]]
    assert codes.count("PROGRAM_ACTUAL_CREDIT_INSUFFICIENT") == 1
    assert codes.count("PROGRAM_MODULE_CREDIT_INSUFFICIENT") == 3
    metrics = result["programMetrics"][0]
    assert metrics["courseCreditSum"] == "28.0"
    assert metrics["actualCreditSum"] == "28.0"
    assert metrics["totalCredits"] == "140"


def test_quality_requires_exact_course_snapshot_and_is_pure():
    with pytest.raises(ValueError, match="missing exact Course snapshot"):
        _quality().program_definition_quality_preflight(
            [
                _row("MAIN", {"totalCredits": Decimal("3")}),
                _row("COURSE", {"courseKey": "CS404@v1", "module": "核心"}),
                _row("CREDIT_REQUIREMENT", {"module": "核心", "creditTarget": Decimal("3")}),
            ],
            course_snapshots=[],
        )

    source = inspect.getsource(_quality())
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "db.query" not in source
    assert "db.add" not in source
    assert "db.commit" not in source
