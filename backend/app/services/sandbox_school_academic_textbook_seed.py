"""sandbox-school · 20K 秋季教材准备数据。

参考日 2026-08-13，2026-2027-1 尚未开学：
- 课程目录已经完成教材匹配；
- 各学院教材选用审核已完成并进入征订；
- 采购订单已下达，按约 80% 到货形成开学准备态；
- 学生正式发放、签收和费用台账必须保持 0，禁止提前制造开学后的事实。

所有教材名、出版社、ISBN 都是确定性虚构售前数据，不复制真实教材/出版数据。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.services.sandbox_school_master_seed import _bulk_insert

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)
EXPECTED_TEXTBOOKS = 196
EXPECTED_SELECTIONS = 768
EXPECTED_REVIEW_BATCHES = 8
EXPECTED_ORDER_BATCHES = 8

PUBLISHERS = ("湘教产融出版社", "职教新程出版社", "现代技能出版社", "产教协同出版社")


def _count(db, model, tenant_id: int, *where) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id,
        model.is_deleted.is_(False),
        *where,
    )) or 0)


def seed_school_academic_textbooks_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaCourse,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        AaTextbook,
        AaTextbookOrderBatch,
        AaTextbookOrderItem,
        AaTextbookReviewBatch,
        AaTextbookReviewBatchItem,
        AaTextbookSelection,
        College,
        SchoolClass,
    )

    term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    )).first()
    if term is None:
        raise RuntimeError("2026-2027-1 学期不存在")

    courses = list(db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.status == "ENABLED",
        AaCourse.is_deleted.is_(False),
    ).order_by(AaCourse.course_code)).all())
    if len(courses) != EXPECTED_TEXTBOOKS:
        raise RuntimeError(f"教材来源课程异常 expected={EXPECTED_TEXTBOOKS} actual={len(courses)}")

    textbook_rows = []
    for index, course in enumerate(courses, 1):
        textbook_rows.append({
            "tenant_id": tenant_id,
            "name": f"{course.course_name}·职业教育项目化教程",
            "isbn": f"978-7-20{(index % 90) + 10:02d}-{index:05d}-{(index * 7) % 10}",
            "publisher": PUBLISHERS[(index - 1) % len(PUBLISHERS)],
            "edition": "2026年修订版",
            "author": f"{course.course_name}课程建设组",
            "subject": course.category,
            "unit_price": Decimal(str(28 + (index % 9) * 3)),
            "is_national_standard": course.course_code in {"PUB001", "PUB002", "PUB003"},
            "status": "ENABLED",
        })
    _bulk_insert(db, AaTextbook, textbook_rows, chunk_size=500)
    db.flush()

    textbook_by_course_name = {
        row.name.removesuffix("·职业教育项目化教程"): row
        for row in db.scalars(select(AaTextbook).where(
            AaTextbook.tenant_id == tenant_id,
            AaTextbook.is_deleted.is_(False),
        )).all()
    }

    next_batches = list(db.execute(select(AaTeachingTaskBatch.id).where(
        AaTeachingTaskBatch.tenant_id == tenant_id,
        AaTeachingTaskBatch.term_id == int(term.id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all())
    batch_ids = [int(row.id) for row in next_batches]
    tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id.in_(batch_ids),
        AaTeachingTask.status != "MERGED",
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).all())
    if len(tasks) != EXPECTED_SELECTIONS:
        raise RuntimeError(f"秋季教材教学任务异常 expected={EXPECTED_SELECTIONS} actual={len(tasks)}")

    class_college = {
        int(cid): int(college_id)
        for cid, college_id in db.execute(select(SchoolClass.id, SchoolClass.college_id).where(
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.is_deleted.is_(False),
        )).all()
    }
    colleges = list(db.scalars(select(College).where(
        College.tenant_id == tenant_id,
        College.is_deleted.is_(False),
    ).order_by(College.code)).all())
    if len(colleges) != EXPECTED_REVIEW_BATCHES:
        raise RuntimeError(f"学院基数异常: {len(colleges)}")

    selection_rows = []
    for task in tasks:
        textbook = textbook_by_course_name.get(str(task.course_name or ""))
        if textbook is None:
            raise RuntimeError(f"教学任务无教材映射 task={task.id} course={task.course_name}")
        college_id = class_college.get(int(task.class_id or 0))
        if college_id is None:
            raise RuntimeError(f"教学任务无学院归属 task={task.id} class={task.class_id}")
        selection_rows.append({
            "tenant_id": tenant_id,
            "task_id": int(task.id),
            "textbook_id": int(textbook.id),
            "textbook_name": textbook.name,
            "course_name": task.course_name,
            "college_id": college_id,
            "officer_teacher_id": int(task.teacher_id) if task.teacher_id else None,
            "officer_key": task.teacher_key,
            "expected_qty": int(task.expected_students or 0),
            "remark": "2026-2027学年第一学期开课任务教材选用",
            "status": "ORDERED",
        })
    _bulk_insert(db, AaTextbookSelection, selection_rows, chunk_size=1000)
    db.flush()

    selections = list(db.scalars(select(AaTextbookSelection).where(
        AaTextbookSelection.tenant_id == tenant_id,
        AaTextbookSelection.is_deleted.is_(False),
    ).order_by(AaTextbookSelection.id)).all())
    selections_by_college: dict[int, list] = defaultdict(list)
    for row in selections:
        selections_by_college[int(row.college_id)].append(row)

    review_rows = []
    for index, college in enumerate(colleges, 1):
        review_rows.append({
            "tenant_id": tenant_id,
            "batch_name": f"{college.college_name}·2026秋季教材选用审核",
            "term_id": int(term.id),
            "college_id": int(college.id),
            "publicity_start_at": datetime(2026, 7, 20, 9, 0),
            "publicity_end_at": datetime(2026, 7, 27, 18, 0),
            "college_reviewer": f"{college.college_name}教学工作组",
            "academic_reviewer": "教务处教材管理办公室",
            "status": "PUBLISHED",
        })
    _bulk_insert(db, AaTextbookReviewBatch, review_rows)
    db.flush()

    review_by_college = {
        int(row.college_id): row
        for row in db.scalars(select(AaTextbookReviewBatch).where(
            AaTextbookReviewBatch.tenant_id == tenant_id,
            AaTextbookReviewBatch.is_deleted.is_(False),
        )).all()
    }
    review_item_rows = [
        {
            "tenant_id": tenant_id,
            "batch_id": int(review_by_college[int(selection.college_id)].id),
            "selection_id": int(selection.id),
        }
        for selection in selections
    ]
    _bulk_insert(db, AaTextbookReviewBatchItem, review_item_rows, chunk_size=1000)

    order_rows = [{
        "tenant_id": tenant_id,
        "batch_name": f"{college.college_name}·2026秋季教材征订",
        "term_id": int(term.id),
        "college_id": int(college.id),
        "submit_at": datetime(2026, 8, 1, 10, 0),
        "status": "PARTIALLY_ARRIVED",
    } for college in colleges]
    _bulk_insert(db, AaTextbookOrderBatch, order_rows)
    db.flush()
    order_by_college = {
        int(row.college_id): row
        for row in db.scalars(select(AaTextbookOrderBatch).where(
            AaTextbookOrderBatch.tenant_id == tenant_id,
            AaTextbookOrderBatch.is_deleted.is_(False),
        )).all()
    }

    order_item_rows = []
    expected_total = 0
    arrived_total = 0
    for college_id, rows in selections_by_college.items():
        grouped: dict[int, dict] = {}
        for selection in rows:
            textbook_id = int(selection.textbook_id)
            item = grouped.setdefault(textbook_id, {
                "name": selection.textbook_name,
                "qty": 0,
            })
            item["qty"] += int(selection.expected_qty or 0)
        for textbook_id, item in grouped.items():
            textbook = next(row for row in textbook_by_course_name.values() if int(row.id) == textbook_id)
            qty = int(item["qty"])
            arrived = int(qty * 0.8)
            expected_total += qty
            arrived_total += arrived
            order_item_rows.append({
                "tenant_id": tenant_id,
                "order_batch_id": int(order_by_college[college_id].id),
                "textbook_id": textbook_id,
                "textbook_name": item["name"],
                "order_qty": qty,
                "arrived_qty": arrived,
                "unit_price_snapshot": textbook.unit_price,
            })
    _bulk_insert(db, AaTextbookOrderItem, order_item_rows, chunk_size=1000)
    db.commit()

    result = validate_school_academic_textbooks_20k(db, tenant_id)
    result["orderedCopies"] = expected_total
    result["arrivedCopies"] = arrived_total
    return result


def validate_school_academic_textbooks_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaTextbook,
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookFeeLedger,
        AaTextbookOrderBatch,
        AaTextbookOrderItem,
        AaTextbookReviewBatch,
        AaTextbookReviewBatchItem,
        AaTextbookSelection,
    )

    selections = _count(db, AaTextbookSelection, tenant_id)
    order_qty = int(db.scalar(select(func.coalesce(func.sum(AaTextbookOrderItem.order_qty), 0)).where(
        AaTextbookOrderItem.tenant_id == tenant_id,
        AaTextbookOrderItem.is_deleted.is_(False),
    )) or 0)
    arrived_qty = int(db.scalar(select(func.coalesce(func.sum(AaTextbookOrderItem.arrived_qty), 0)).where(
        AaTextbookOrderItem.tenant_id == tenant_id,
        AaTextbookOrderItem.is_deleted.is_(False),
    )) or 0)
    report = {
        "textbooks": _count(db, AaTextbook, tenant_id),
        "selections": selections,
        "reviewBatches": _count(db, AaTextbookReviewBatch, tenant_id),
        "reviewItems": _count(db, AaTextbookReviewBatchItem, tenant_id),
        "orderBatches": _count(db, AaTextbookOrderBatch, tenant_id),
        "orderItems": _count(db, AaTextbookOrderItem, tenant_id),
        "orderedCopies": order_qty,
        "arrivedCopies": arrived_qty,
        "arrivalRate": round(arrived_qty / order_qty, 4) if order_qty else 0,
        "distributionBatches": _count(db, AaTextbookDistributionBatch, tenant_id),
        "distributionRecords": _count(db, AaTextbookDistributionRecord, tenant_id),
        "feeLedgers": _count(db, AaTextbookFeeLedger, tenant_id),
    }
    expected_fixed = {
        "textbooks": EXPECTED_TEXTBOOKS,
        "selections": EXPECTED_SELECTIONS,
        "reviewBatches": EXPECTED_REVIEW_BATCHES,
        "reviewItems": EXPECTED_SELECTIONS,
        "orderBatches": EXPECTED_ORDER_BATCHES,
        "distributionBatches": 0,
        "distributionRecords": 0,
        "feeLedgers": 0,
    }
    mismatches = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected_fixed.items()
        if report[key] != value
    }
    if order_qty <= 0 or arrived_qty <= 0 or not (0.79 <= report["arrivalRate"] <= 0.81):
        mismatches["arrival"] = {
            "expected": "ordered>0 and arrivalRate≈80%",
            "actual": {"ordered": order_qty, "arrived": arrived_qty, "rate": report["arrivalRate"]},
        }
    if mismatches:
        raise RuntimeError(f"20K 秋季教材验收失败: {mismatches}")
    report["passed"] = True
    return report
