"""益阳 SM02：正式实习计划字段与报告数量快照契约。"""
from __future__ import annotations

from types import SimpleNamespace

from app.models import InternshipBatchPlan
from app.modules.internship.services.internship_plan_service import (
    _rules_snapshot,
    _validate_plan_fields,
)


def _payload():
    return {
        "internshipType": "POST",
        "planNo": "YYZY-2026-GWSX-001",
        "majorName": "软件技术",
        "educationLevel": "高职（专科）",
        "subsidyStandard": "按学校实习补贴管理办法执行",
        "targetAudience": "2024级软件技术专业学生",
        "objectives": "完成岗位实习培养目标",
        "requirements": "遵守安全、考勤和报告要求",
        "assessmentContent": "按过程表现与校企评价综合考核",
        "responsibleName": "实习负责人",
        "attachmentFileIds": [],
    }


def test_sm02_plan_procurement_fields_are_canonical_columns():
    columns = InternshipBatchPlan.__table__.columns
    for name in ("plan_no", "major_name", "education_level", "subsidy_standard"):
        assert name in columns


def test_sm02_plan_fields_are_normalized_for_persistence():
    data = _validate_plan_fields(_payload())
    assert data["planNo"] == "YYZY-2026-GWSX-001"
    assert data["majorName"] == "软件技术"
    assert data["educationLevel"] == "高职（专科）"
    assert data["subsidyStandard"] == "按学校实习补贴管理办法执行"


def test_sm02_report_requirements_snapshot_preserves_zero_and_counts():
    batch = SimpleNamespace(
        rules_version=7,
        rules_config={
            "checkin": {"requiredDays": 88},
            "weeklyReport": {"requiredCount": 12, "minWordCount": 300},
            "processReport": {
                "dailyRequiredCount": 0,
                "dailyMinWords": 30,
                "monthlyRequiredCount": 4,
                "monthlyMinWords": 500,
                "summaryRequiredCount": 1,
                "summaryMinWords": 1000,
            },
        },
    )
    snap = _rules_snapshot(batch)
    assert snap["requiredCheckinDays"] == 88
    assert snap["dailyRequiredCount"] == 0
    assert snap["weeklyRequiredCount"] == 12
    assert snap["monthlyRequiredCount"] == 4
    assert snap["summaryRequiredCount"] == 1
    assert snap["monthlyMinWordCount"] == 500
    assert snap["summaryMinWordCount"] == 1000
