from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_counselor_eval_appeal_review_accepts_version():
    source = read("backend/app/api/v1/student_affairs.py")
    block = source.split("class EvalAppealReviewBody", 1)[1].split("@router.get", 1)[0]
    assert "version: int" in block
    assert "乐观锁版本" in block


def test_dorm_checkout_is_formally_versioned():
    api = read("backend/app/api/v1/student_affairs.py")
    service = read("backend/app/services/affairs_dorm_service.py")
    assert "class DormCheckoutBody" in api
    assert "dorm_svc.checkout(bedId, user, body.version)" in api
    assert "def checkout(bed_id, user, expected_version=None)" in service
    assert "atomic_claim_version(db, bed, expected_version)" in service


def test_talk_actions_read_record_version():
    helper = read("backend/affairs_contract_test_support.py")
    assert '(re.compile(r"/student-affairs/talks/(\\d+)/(?:record|follow-up)$"), "TalkRecord")' in helper


def test_publicity_tests_use_explicit_time_progression():
    helper = read("backend/affairs_contract_test_support.py")
    funding = read("backend/tests/test_affairs_funding.py")
    assert "def expire_publicity" in helper
    assert 'expire_publicity("AidApply", aid_id)' in funding
    assert 'expire_publicity("FundingApplication", app_id)' in funding
