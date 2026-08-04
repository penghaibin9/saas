from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_second_review_migrations_are_committed() -> None:
    versions = ROOT / "backend" / "alembic" / "versions"
    assert (versions / "20260804_merge_affairs_second_review_heads.py").is_file()
    assert (versions / "20260804_affairs_archive_async.py").is_file()


def test_second_review_transport_artifacts_are_removed() -> None:
    assert not (ROOT / ".audit").exists()
    workflows = ROOT / ".github" / "workflows"
    assert not (workflows / "student-affairs-second-review-export.yml").exists()
    assert not (workflows / "student-affairs-second-review-apply.yml").exists()
