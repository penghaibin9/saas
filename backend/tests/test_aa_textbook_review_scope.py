"""教材学院初审与学校备案：真实范围、原单来源与终态保护。"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_textbook_final_facade as svc
from app.modules.academic_affairs.services import academic_affairs_textbook_read_service as reads
from test_aa_textbook import TID, _seed


def test_review_actions_follow_scope_stage_and_source():
    source = SimpleNamespace(item_count=1, owner_count=1, college_count=1, college_id=7, min_term_id=5, max_term_id=5, reviewing_count=1, writable_count=1)
    batch = SimpleNamespace(college_id=7, term_id=5, status="DRAFT")
    college = SimpleNamespace(scope_type="COLLEGE", college_ids={7}, permission_codes={"academicAffairs.textbook.review.manage"})
    school = SimpleNamespace(scope_type="TENANT_ALL", college_ids=set(), permission_codes=college.permission_codes)
    for status in svc._legacy._RB_CHAIN:
        batch.status = status
        assert svc._review_actions(college, batch, source)["advance"] == (status in {"DRAFT", "COLLEGE_REVIEWING"})
        assert svc._review_actions(school, batch, source)["return"] == (status in {"COLLEGE_APPROVED", "ACADEMIC_APPROVED"})
    batch.status = "PUBLISHED"
    assert not any(svc._review_actions(school, batch, source).values())
    batch.status = "DRAFT"
    for change in [{"college_count": 2}, {"owner_count": 0}, {"reviewing_count": 0}, {"max_term_id": 6}, {"writable_count": 0}]:
        invalid = SimpleNamespace(**{**vars(source), **change})
        assert not any(svc._review_actions(college, batch, invalid).values())
    college.permission_codes = set()
    assert not any(svc._review_actions(college, batch, source).values())


def _review_scene(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaTeachingTask, AaTeachingTaskBatch, AaTextbook, AaTextbookSelection, College,
                            Permission, Role, RoleAssignmentScope, RolePermission, Tenant, User, UserRole)
    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code="demo", school_name="教材责任回归学校", status="ACTIVE"))
        second = College(tenant_id=TID, college_name="教材另一学院", status="ACTIVE")
        book = AaTextbook(tenant_id=TID, name="责任审核教材", unit_price=10)
        db.add_all([second, book]); db.flush()
        other_batch = AaTeachingTaskBatch(tenant_id=TID, term_id=ids["term"], college_id=second.id, batch_name="另一学院任务")
        db.add(other_batch); db.flush()
        other_task = AaTeachingTask(tenant_id=TID, batch_id=other_batch.id, course_id=2, course_name="另一学院课程")
        db.add(other_task); db.flush()
        selections = [AaTextbookSelection(tenant_id=TID, task_id=task_id, textbook_id=book.id, textbook_name=book.name,
                         college_id=college_id, expected_qty=30, remark="正式教学选用", status="SUBMITTED")
                      for task_id, college_id in [(ids["task"], ids["college"]), (other_task.id, second.id)]]
        db.add_all(selections)
        users = {}
        from tests.support_grade_review_identity import _ensure_permission
        permissions = [_ensure_permission(db, f"academicAffairs.textbook.{action}") for action in ["review.manage", "selection.manage", "view"]]
        for name, role_code, college_id in [("tb_college_a", "TB_COLLEGE_A", ids["college"]), ("tb_college_b", "TB_COLLEGE_B", second.id), ("tb_school", "TB_SCHOOL", None)]:
            user = User(tenant_id=TID, login_name=name, real_name=name, user_type="TEACHER", password_hash="x", status="ACTIVE")
            role = Role(tenant_id=TID, role_code=role_code, role_name=name, role_type="CUSTOM", status="ACTIVE")
            db.add_all([user, role]); db.flush()
            link = UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE")
            db.add(link); db.flush()
            db.add_all([RolePermission(tenant_id=TID, role_id=role.id, permission_id=p.id, status="ACTIVE") for p in permissions])
            db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id, role_code=role_code,
                scope_type="COLLEGE" if college_id else "SCHOOL", scope_id=college_id or 0, effective_at=datetime(2020, 1, 1), status="ACTIVE"))
            users[name] = {"userId": f"db-{user.id}", "loginName": name, "currentRoleCode": role_code,
                           "activeContextId": f"role:{role.id}", "tenantId": str(TID), "userType": "TEACHER"}
        db.flush()
        ids.update(own_selection=selections[0].id, other_selection=selections[1].id, other_college=second.id, other_task=other_task.id, book=book.id)
        db.commit()
    return ids, users


def _call(user, function, *args, **kwargs):
    from app.core.context import set_current_user, set_tenant
    set_tenant(user["tenantId"])
    set_current_user(user)
    return function(user, *args, **kwargs)


def test_review_relay_scopes_and_terminal_return_guard(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTextbookReviewBatch, AaTextbookSelection, AffairsAuditTrail
    ids, users = _review_scene(db_mode)
    college, outsider, school = [users[name] for name in ["tb_college_a", "tb_college_b", "tb_school"]]
    batch = _call(school, svc.create_review_batch, SimpleNamespace(termId=ids["term"], selectionIds=[ids["own_selection"]]))
    bid = int(batch["reviewBatchId"])
    assert batch["collegeId"] == str(ids["college"])
    assert not batch["actions"]["advance"]
    assert _call(outsider, reads.list_review_batches)[1] == 0
    assert _call(college, reads.list_review_batches, page=2, page_size=1) == ([], 1)
    visible, total = _call(college, reads.list_review_batches, page=1, page_size=1)
    assert total == 1 and visible[0]["actions"] == {"advance": True, "return": True}
    for denied in [outsider, school]:
        with pytest.raises(AppException) as error:
            _call(denied, svc.review_batch_advance, bid, "APPROVE")
        assert error.value.code == "NO_DATA_SCOPE"
    with pytest.raises(AppException) as error:
        _call({**school, "tenantId": str(TID + 1)}, svc.review_batch_advance, bid, "APPROVE")
    assert error.value.code == "DATA_NOT_FOUND"
    for _ in range(2):
        _call(college, svc.review_batch_advance, bid, "APPROVE")
    with pytest.raises(AppException):
        _call(college, svc.review_batch_advance, bid, "RETURN", "不能跨级学校审核")
    for _ in range(2):
        result = _call(school, svc.review_batch_advance, bid, "APPROVE")
    assert result["status"] == "PUBLISHED" and not any(result["actions"].values())
    for action in ["RETURN", "APPROVE"]:
        with pytest.raises(AppException):
            _call(school, svc.review_batch_advance, bid, action, "已备案不能再退回")
    with get_sessionmaker()() as db:
        saved = db.get(AaTextbookReviewBatch, bid)
        assert saved.status == "PUBLISHED"
        assert saved.college_reviewer == college["userId"]
        assert saved.academic_reviewer == school["userId"]
        audits = db.query(AffairsAuditTrail).filter_by(biz_type="AA_TEXTBOOK_REVIEW", biz_id=bid, action="TEXTBOOK_REVIEW_ADVANCE").order_by(AffairsAuditTrail.id).all()
        assert [row.operator for row in audits] == [college["userId"]] * 2 + [school["userId"]] * 2
        assert db.get(AaTextbookSelection, ids["own_selection"]).status == "APPROVED"
        db.get(AaTextbookSelection, ids["own_selection"]).status = "ORDERED"
        db.commit()
    with pytest.raises(AppException):
        _call(school, svc.review_batch_advance, bid, "RETURN", "已征订不能再退回")
    with get_sessionmaker()() as db:
        assert db.get(AaTextbookSelection, ids["own_selection"]).status == "ORDERED"


def test_review_sources_and_selection_writes_fail_closed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskBatch, AaTeachingTask, AaTextbookReviewBatch, AaTextbookReviewBatchItem, AaTextbookSelection
    ids, users = _review_scene(db_mode)
    college, school = users["tb_college_a"], users["tb_school"]
    with pytest.raises(AppException):
        _call(school, svc.create_review_batch, SimpleNamespace(termId=ids["term"], selectionIds=[ids["own_selection"], ids["other_selection"]]))
    with get_sessionmaker()() as db:
        assert db.query(AaTextbookReviewBatch).count() == 0
        own = db.get(AaTextbookSelection, ids["own_selection"])
        own.college_id = ids["other_college"]  # 陈旧投影不能改变真实教学任务范围。
        other = db.get(AaTextbookSelection, ids["other_selection"])
        other.status = "DRAFT"
        db.commit()
    own_rows, total = _call(college, svc.list_selections)
    assert total == 1 and own_rows[0]["selectionId"] == str(ids["own_selection"])
    for fn, args in [(svc.update_selection, (ids["other_selection"], SimpleNamespace(textbookId=ids["book"], expectedQty=30, remark="越范围不能修改"))),
                     (svc.submit_selection, (ids["other_selection"],)), (svc.withdraw_selection, (ids["other_selection"],))]:
        with pytest.raises(AppException):
            _call(college, fn, *args)
    with pytest.raises(AppException):
        _call(college, svc.create_selection, SimpleNamespace(taskId=ids["other_task"], textbookId=ids["book"], expectedQty=30))
    batch = _call(school, svc.create_review_batch, SimpleNamespace(termId=ids["term"], selectionIds=[ids["own_selection"]]))
    bid = int(batch["reviewBatchId"])
    with get_sessionmaker()() as db:
        db.get(AaTextbookReviewBatch, bid).college_id = None  # 旧批次只读解析来源，不批量回填。
        db.commit()
    assert _call(college, reads.list_review_batches)[0][0]["actions"]["advance"]
    result = _call(college, svc.review_batch_advance, bid, "RETURN", "教材版次过旧需更新")
    assert result["status"] == "RETURNED"
    with get_sessionmaker()() as db:
        task = db.get(AaTeachingTask, ids["task"])
        db.get(AaTeachingTaskBatch, task.batch_id).college_id = None
        db.get(AaTextbookSelection, ids["own_selection"]).status = "SUBMITTED"
        db.commit()
    with pytest.raises(AppException):
        _call(school, svc.create_review_batch, SimpleNamespace(termId=ids["term"], selectionIds=[ids["own_selection"]]))
    assert _call(college, reads.list_review_batches)[1] == 0
    with get_sessionmaker()() as db:
        empty = AaTextbookReviewBatch(tenant_id=TID, term_id=ids["term"], batch_name="旧无来源批次", status="DRAFT")
        mixed = AaTextbookReviewBatch(tenant_id=TID, term_id=ids["term"], batch_name="旧混学院批次", status="DRAFT")
        db.add_all([empty, mixed]); db.flush()
        db.add_all([AaTextbookReviewBatchItem(tenant_id=TID, batch_id=mixed.id, selection_id=sid)
                    for sid in [ids["own_selection"], ids["other_selection"]]])
        old_ids = [empty.id, mixed.id]
        db.commit()
    assert _call(college, reads.list_review_batches)[1] == 0
    for old_id in old_ids:
        with pytest.raises(AppException):
            _call(college, svc.review_batch_advance, old_id, "APPROVE")
    with get_sessionmaker()() as db:
        assert all(db.get(AaTextbookReviewBatch, old_id).status == "DRAFT" for old_id in old_ids)
