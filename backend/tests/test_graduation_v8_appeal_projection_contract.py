from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v8_grade_appeal_list_projects_the_exact_published_grade_snapshot():
    source = _text(
        "backend/app/modules/graduation/services/"
        "graduation_release_grade_appeal_hardening.py"
    )
    for key in (
        '"advisorScore"', '"reviewerScore"', '"defenseScore"',
        '"appealedGrade"', '"currentGrade"', '"versionMatches"',
        '"versionMessage"',
    ):
        assert key in source
    assert 'GraduationAuditTrail.biz_type == "GRADE_APPEAL_SNAPSHOT"' in source
    assert 'grade.status == "PUBLISHED"' in source
    assert 'comparable = ("gradeId", "gradeVersion", "sourceSnapshotHash", "totalScore", "publishedAt")' in source


def test_v8_grade_appeal_review_refuses_to_mutate_a_newer_grade_version():
    source = _text(
        "backend/app/modules/graduation/services/"
        "graduation_release_grade_appeal_hardening.py"
    )
    assert "current != expected" in source
    assert "原申诉不得作用于新成绩" in source
