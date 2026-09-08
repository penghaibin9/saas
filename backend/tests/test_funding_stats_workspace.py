"""资助统计工作区：真实 MySQL 聚合、范围、脱敏与到账对账。"""
from __future__ import annotations

from decimal import Decimal

from affairs_contract_test_support import role_headers
from test_affairs_funding import BASE, TID, _seed


def _seed_stats_truth(ids):
    from app.db.session import get_sessionmaker
    from app.models import (
        AidApply, AidBatch, FeeReduction, FundingApplication, FundingBatch,
        FundingDisbursement, FundingProject, StudentLoan, WorkStudyPost, WorkStudyRecord,
    )

    db = get_sessionmaker()()
    try:
        project = FundingProject(
            tenant_id=TID, project_name="统计口径奖学金", project_type="SCHOLARSHIP",
            amount=Decimal("3000.00"), quota=10, status="ENABLED",
        )
        db.add(project); db.flush()
        award_batch = FundingBatch(
            tenant_id=TID, project_id=project.id, project_type="SCHOLARSHIP",
            year_code="2025-2026", quota=10, amount_budget=Decimal("30000.00"), status="OPEN",
        )
        review_batch = FundingBatch(
            tenant_id=TID, project_id=project.id, project_type="SCHOLARSHIP",
            year_code="2026-2027", quota=10, amount_budget=Decimal("30000.00"), status="OPEN",
        )
        db.add_all([award_batch, review_batch]); db.flush()
        granted_a = FundingApplication(
            tenant_id=TID, batch_id=award_batch.id, student_id=ids["sa"], apply_source="SELF",
            project_type="SCHOLARSHIP", amount=Decimal("3000.00"), requested_amount=Decimal("3000.00"),
            approved_amount=Decimal("3000.00"), status="PUBLICITY",
        )
        granted_b = FundingApplication(
            tenant_id=TID, batch_id=award_batch.id, student_id=ids["sb"], apply_source="SELF",
            project_type="SCHOLARSHIP", amount=Decimal("2500.00"), requested_amount=Decimal("2500.00"),
            approved_amount=Decimal("2500.00"), status="PUBLICITY",
        )
        reviewing_a = FundingApplication(
            tenant_id=TID, batch_id=review_batch.id, student_id=ids["sa"], apply_source="SELF",
            project_type="SCHOLARSHIP", amount=Decimal("3000.00"), requested_amount=Decimal("3000.00"),
            status="COUNSELOR_REVIEW",
        )
        db.add_all([granted_a, granted_b, reviewing_a]); db.flush()
        # 让真实数据库迁移中的 PUBLICITY→GRANTED 约束执行，避免绕过额度真值。
        granted_a.status = "GRANTED"
        granted_b.status = "GRANTED"
        db.flush()

        aid_batch = AidBatch(
            tenant_id=TID, batch_name="统计困难认定", year_code="2025-2026", status="CLOSED",
        )
        db.add(aid_batch); db.flush()
        db.add(AidApply(
            tenant_id=TID, batch_id=aid_batch.id, student_id=ids["sa"],
            apply_level="DIFFICULT", final_level="DIFFICULT", status="APPROVED",
        ))

        post = WorkStudyPost(
            tenant_id=TID, dept_name="图书馆", post_name="书库助理", salary=Decimal("600.00"),
            headcount=2, status="ENABLED",
        )
        db.add(post); db.flush()
        db.add(WorkStudyRecord(
            tenant_id=TID, post_id=post.id, student_id=ids["sa"], status="ONBOARD",
            subsidy_total=Decimal("600.00"),
        ))
        db.add(StudentLoan(
            tenant_id=TID, student_id=ids["sa"], loan_type="ORIGIN", year_code="2025-2026",
            amount=Decimal("8000.00"), status="CONFIRMED",
        ))
        db.add(FeeReduction(
            tenant_id=TID, student_id=ids["sb"], item_type="TEMP_AID",
            amount=Decimal("1200.00"), reason="突发困难临时补助", status="ISSUED",
        ))
        db.add(FundingDisbursement(
            tenant_id=TID, application_id=granted_a.id, batch_id=award_batch.id,
            student_id=ids["sa"], project_type="SCHOLARSHIP", amount=Decimal("3000.00"),
            bank_status="ISSUED", disburse_no="STAT-001", bank_last4="1234",
        ))
        db.commit()
    finally:
        db.close()


def test_funding_stats_are_cross_branch_scoped_masked_and_reconciled(client, db_mode):
    ids = _seed(db_mode)
    _seed_stats_truth(ids)
    staff = role_headers(
        "STUDENT_AFFAIRS_ADMIN", login_name="stats_sa_admin", real_name="统计学工管理员",
    )

    response = client.get(f"{BASE}/funding/stats", headers=staff)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    # db_mode 自带一名真实基础学生；本测试另建两名，所以可见学生为 3。
    assert data["visibleStudents"] == 3
    assert data["beneficiaryStudents"] == 2
    assert data["coverageRate"] == 0.6667
    assert data["difficultStudents"] == 1
    assert data["difficultBeneficiaries"] == 1
    assert data["difficultCoverageRate"] == 1.0
    assert data["totalApplications"] == 3
    assert data["applicantStudents"] == 2
    assert data["grantedApplications"] == 2
    assert data["inProgressApplications"] == 1
    assert data["workStudyOnboard"] == 1
    assert data["confirmedLoans"] == 1
    assert data["issuedReductions"] == 1
    assert data["ledger"]["total"] == 1
    assert data["ledger"]["missing"] == 1
    assert data["ledger"]["attention"] == 1
    assert data["amounts"] == {
        "visible": True,
        "approvedAmountTotal": "5500.00",
        "issuedAmountTotal": "3000.00",
        "workStudySubsidyTotal": "600.00",
        "confirmedLoanAmountTotal": "8000.00",
        "issuedReductionAmountTotal": "1200.00",
    }

    counselor = role_headers("COUNSELOR", login_name="counselor01", real_name="测试辅导员")
    scoped = client.get(f"{BASE}/funding/stats", headers=counselor).json()["data"]
    assert scoped["visibleStudents"] == 1
    assert scoped["beneficiaryStudents"] == 1
    assert scoped["totalApplications"] == 2
    assert scoped["ledger"]["missing"] == 0
    assert scoped["amounts"] == {"visible": False}

    drill = client.get(
        f"{BASE}/funding/stats/drill", headers=staff,
        params={"metric": "DISBURSEMENT_ATTENTION", "page": 1, "pageSize": 20},
    )
    assert drill.status_code == 200, drill.text
    result = drill.json()["data"]
    assert result["total"] == 1 and result["masked"] is True
    assert result["items"][0]["studentNo"] != "B001"
    assert result["items"][0]["realName"] != "乙一"
    assert "尚未建发放台账" in result["items"][0]["sources"]
    assert set(result["items"][0]) == {"studentNo", "realName", "grade", "sources"}

    invalid = client.get(
        f"{BASE}/funding/stats/drill", headers=staff, params={"metric": "MONEY_DETAIL"},
    )
    assert invalid.status_code == 400
    student = role_headers("STUDENT", login_name="stats_student", real_name="统计学生")
    assert client.get(f"{BASE}/funding/stats", headers=student).status_code == 403
