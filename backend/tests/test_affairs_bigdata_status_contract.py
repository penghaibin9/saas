from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_bigdata_seeds_only_current_aid_states():
    for name in ("test_affairs_phase2_bigdata.py", "test_affairs_round2_bigdata.py"):
        text = (ROOT / "backend/tests" / name).read_text(encoding="utf-8")
        assert 'status="REVIEW"' not in text
        assert '"status": "REVIEW"' not in text
        assert "COUNSELOR_REVIEW" in text
        assert "is_deleted=False, version=0" in text
