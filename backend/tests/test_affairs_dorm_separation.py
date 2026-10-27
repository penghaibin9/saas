def test_dorm_two_nodes_require_different_people_and_preserve_original_bed(client, db_mode):
    from sqlalchemy import select
    from affairs_contract_test_support import ensure_role_user, post_versioned, role_headers
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, DormBed, DormBuilding, DormTransfer, UnifiedTodo
    from test_affairs_dorm import BASE, TID, _seed, _hdr, _make_building, _first_bed

    ids = _seed(db_mode)
    actor = ensure_role_user("DORM_MANAGER", login_name="counselor01")
    admin = _hdr(client, "school_admin01")
    counselor = role_headers("COUNSELOR", login_name="counselor01")
    building = _make_building(client, admin)
    _, beds = _first_bed(client, admin, building)
    original, target = beds[0]["bedId"], beds[1]["bedId"]
    assert client.post(f"{BASE}/dorm/beds/{original}/checkin", headers=admin,
                       json={"studentId": str(ids["sm"])}).status_code == 200
    created = client.post(f"{BASE}/dorm/transfers", headers=counselor,
        json={"studentId": str(ids["sm"]), "toBedId": target, "reason": "核验不同人员审核调宿"})
    assert created.status_code == 200, created.text
    transfer_id = int(created.json()["data"]["transferId"])
    with get_sessionmaker()() as db:
        db.get(DormBuilding, int(building)).manager_teacher_key = "counselor01"
        db.commit()
    route = f"{BASE}/dorm/transfers/{transfer_id}/review"
    blocked = post_versioned(client, route, headers=counselor, json={"action": "APPROVE"})
    assert blocked.status_code == 409, blocked.text
    with get_sessionmaker()() as db:
        assert db.get(DormTransfer, transfer_id).status == "COUNSELOR_REVIEW"
        assert db.get(DormBed, int(original)).student_id == ids["sm"]
        assert db.get(DormBed, int(target)).student_id is None
        db.get(DormBuilding, int(building)).manager_teacher_key = "dorm01"
        db.commit()
    first = post_versioned(client, route, headers=counselor, json={"action": "APPROVE"})
    assert first.status_code == 200, first.text
    with get_sessionmaker()() as db:
        evidence = db.scalar(select(AffairsAuditTrail).where(AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "DORM_TRANSFER", AffairsAuditTrail.biz_id == transfer_id,
            AffairsAuditTrail.action == "STEP"))
        assert evidence.created_by == actor
        # 初审待办被复用的旧数据也是需要拒绝的表示形式。
        old = db.scalar(select(UnifiedTodo).where(UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_module == "student-affairs", UnifiedTodo.source_biz_id == transfer_id,
            UnifiedTodo.assignee_id == actor, UnifiedTodo.todo_type == "DORM_TRANSFER"))
        assert old is not None
        old.status = "PENDING"
        db.commit()
    # 即使旧待办错误地再次分派给初审本人，也不能用切换职责冒充另一人。
    self_dorm = role_headers("DORM_MANAGER", login_name="counselor01")
    same = post_versioned(client, route, headers=self_dorm, json={"action": "APPROVE"})
    assert same.status_code == 403, same.text
    with get_sessionmaker()() as db:
        old = db.scalar(select(UnifiedTodo).where(UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_module == "student-affairs", UnifiedTodo.source_biz_id == transfer_id,
            UnifiedTodo.assignee_id == actor, UnifiedTodo.todo_type == "DORM_TRANSFER"))
        old.status = "DONE"
        db.commit()
    manager = role_headers("DORM_MANAGER", login_name="dorm01")
    final = post_versioned(client, route, headers=manager, json={"action": "APPROVE"})
    assert final.status_code == 200 and final.json()["data"]["status"] == "EXECUTED", final.text
    with get_sessionmaker()() as db:
        assert db.get(DormBed, int(original)).student_id is None
        assert db.get(DormBed, int(target)).student_id == ids["sm"]
