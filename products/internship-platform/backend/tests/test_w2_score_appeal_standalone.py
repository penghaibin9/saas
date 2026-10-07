def test_score_appeal_is_standalone_domain_model():
    from app.models import InternshipScoreAppeal
    from app.modules.internship.services import internship_score_appeal_service as svc

    assert InternshipScoreAppeal.__tablename__ == "t_internship_score_appeal"
    assert "CsWorkOrder" not in svc.__doc__
