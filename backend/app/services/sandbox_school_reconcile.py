"""20K 演示学校跨表数量对账。

数据生成后再从“事实表”反算冗余计数，确保看板、岗位容量、企业累计人数与学生实习台账一致。
任何计数都不靠 seed 手填常数冒充事实。
"""
from __future__ import annotations

from sqlalchemy import func, select


def reconcile_internship_capacity(db, tenant_id: int) -> dict:
    from app.models import EmpCompany, InternshipPosition, InternshipRecord

    position_counts = {
        int(position_id): int(count)
        for position_id, count in db.execute(
            select(InternshipRecord.position_id, func.count())
            .where(
                InternshipRecord.tenant_id == tenant_id,
                InternshipRecord.position_id.is_not(None),
                InternshipRecord.destination_type == "ASSIGNED",
                InternshipRecord.is_deleted.is_(False),
            )
            .group_by(InternshipRecord.position_id)
        ).all()
    }
    company_counts = {
        int(company_id): int(count)
        for company_id, count in db.execute(
            select(InternshipRecord.enterprise_id, func.count())
            .where(
                InternshipRecord.tenant_id == tenant_id,
                InternshipRecord.enterprise_id.is_not(None),
                InternshipRecord.destination_type == "ASSIGNED",
                InternshipRecord.is_deleted.is_(False),
            )
            .group_by(InternshipRecord.enterprise_id)
        ).all()
    }

    positions = db.scalars(select(InternshipPosition).where(
        InternshipPosition.tenant_id == tenant_id,
        InternshipPosition.is_deleted.is_(False),
    )).all()
    companies = db.scalars(select(EmpCompany).where(
        EmpCompany.tenant_id == tenant_id,
        EmpCompany.is_deleted.is_(False),
    )).all()

    for row in positions:
        row.allocated_count = position_counts.get(int(row.id), 0)
        if row.allocated_count > int(row.headcount or 0):
            raise RuntimeError(
                f"实习岗位容量不自洽 position={row.id}: allocated={row.allocated_count} > headcount={row.headcount}")
    for row in companies:
        row.intern_count = company_counts.get(int(row.id), 0)

    db.commit()

    assigned_records = int(db.scalar(
        select(func.count()).select_from(InternshipRecord).where(
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.destination_type == "ASSIGNED",
            InternshipRecord.position_id.is_not(None),
            InternshipRecord.enterprise_id.is_not(None),
            InternshipRecord.is_deleted.is_(False),
        )
    ) or 0)
    allocated_sum = sum(int(x.allocated_count or 0) for x in positions)
    company_sum = sum(int(x.intern_count or 0) for x in companies)
    if assigned_records != allocated_sum or assigned_records != company_sum:
        raise RuntimeError(
            "实习人数对账失败: "
            f"records={assigned_records}, positionAllocated={allocated_sum}, companyInternCount={company_sum}")

    return {
        "assignedRecords": assigned_records,
        "positionAllocated": allocated_sum,
        "companyInternCount": company_sum,
        "positions": len(positions),
        "companies": len(companies),
        "passed": True,
    }
