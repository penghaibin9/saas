"""毕业设计中心 · 移动端答辩评委打分（新聚合 judge_pending + 评分录入 judgeName 服务端强制）。
全部经 HTTP client 走真库(db_mode)。覆盖：面板收敛(评委甲/评委乙可见，组外专家不可见)、
未发布分组过滤、评分后状态刷新、judgeName 防伪造(评委甲用自己身份提交时无论请求体是否夹带
其他评委姓名，落库都归属评委甲本人)、非面板成员写入 403。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
GD_SCORE = "/api/v1/graduation/gd-defense-scores"
TID = 1000000000000000001


_TEACHER_NO_BY_NAME = {"评委甲": "MOB-JA", "评委乙": "MOB-JB", "组外专家": "MOB-OUT"}


def _defense_expert(name, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "GD_DEFENSE_EXPERT", "clientType": "MP",
        "loginName": _TEACHER_NO_BY_NAME.get(name, f"MOB-{name}"),
    })}


def _seed(db_mode, published=True):
    """1个答辩组(chair=评委甲, members=[评委乙])，1个学生挂在组下。返回 gd_student_id(str)。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationDefenseGroup, GraduationMentor, GraduationStudent
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(
            tenant_id=TID, batch_name="移动端答辩批次",
            batch_no=f"MOB-DEF-{published}", grade_year="2026届",
            planned_count=10, status="ACTIVE",
        )
        db.add(batch)
        db.flush()
        judge_a = GraduationMentor(
            tenant_id=TID, teacher_no="MOB-JA", teacher_name="评委甲",
            qualification_status="QUALIFIED",
        )
        judge_b = GraduationMentor(
            tenant_id=TID, teacher_no="MOB-JB", teacher_name="评委乙",
            qualification_status="QUALIFIED",
        )
        db.add_all([judge_a, judge_b])
        db.flush()
        g = GraduationDefenseGroup(tenant_id=TID, batch_id=batch.id, group_name="答辩一组", chair="评委甲",
                                   chair_mentor_id=judge_a.id,
                                   members_json=[{"mentorId": judge_b.id, "name": "评委乙", "teacherNo": "MOB-JB"}],
                                   secretary="", published=published)
        db.add(g)
        db.flush()
        stu = GraduationStudent(tenant_id=TID, batch_id=batch.id, name="答辩测试生", student_no="DEF001",
                                advisor_name="另一位导师", record_status="ACTIVE",
                                stage="DEFENSE", defense_group_id=g.id)
        db.add(stu)
        db.flush()
        gid = stu.id
        db.commit()
        return str(gid)
    finally:
        db.close()


def _items(data):
    return data.get("items", []) if isinstance(data, dict) else data


def test_panel_members_see_pending_outsider_does_not(db_mode, client):
    gid = _seed(db_mode)

    r1 = client.get(f"{MOB}/teacher/graduation/defense/pending", headers=_defense_expert("评委甲"))
    assert r1.status_code == 200
    items1 = _items(r1.json()["data"])
    assert any(x["gdStudentId"] == gid for x in items1)
    row1 = next(x for x in items1 if x["gdStudentId"] == gid)
    assert row1["myStatus"] == "PENDING" and row1["myScore"] is None

    r2 = client.get(f"{MOB}/teacher/graduation/defense/pending", headers=_defense_expert("评委乙"))
    items2 = _items(r2.json()["data"])
    assert any(x["gdStudentId"] == gid for x in items2)

    r3 = client.get(f"{MOB}/teacher/graduation/defense/pending", headers=_defense_expert("组外专家"))
    if r3.status_code == 403:
        assert r3.json()["code"] != 0
    else:
        items3 = _items(r3.json()["data"])
        assert not any(x["gdStudentId"] == gid for x in items3)


def test_unpublished_group_excluded_from_pending(db_mode, client):
    gid = _seed(db_mode, published=False)
    r = client.get(f"{MOB}/teacher/graduation/defense/pending", headers=_defense_expert("评委甲"))
    items = _items(r.json()["data"])
    assert not any(x["gdStudentId"] == gid for x in items)


def test_score_entry_updates_pending_status_and_judge_name_is_server_forced(db_mode, client):
    gid = _seed(db_mode)
    h_a = _defense_expert("评委甲")

    # 请求体夹带伪造的 judgeName="评委乙"，服务端必须忽略，仍记为评委甲本人的评分
    entry = client.post(f"{MOB}/teacher/graduation/defense/{gid}/score", headers=h_a,
                        json={"score": 88, "comment": "表现优秀", "judgeName": "评委乙"})
    assert entry.status_code == 200 and entry.json()["code"] == 0

    pending_a = _items(client.get(f"{MOB}/teacher/graduation/defense/pending", headers=h_a).json()["data"])
    row_a = next(x for x in pending_a if x["gdStudentId"] == gid)
    assert row_a["myStatus"] == "SCORED" and row_a["myScore"] == 88

    # 评委乙自己的视角仍是 PENDING——证明评委甲的伪造 judgeName 没有落到评委乙名下
    pending_b = _items(client.get(f"{MOB}/teacher/graduation/defense/pending",
                                  headers=_defense_expert("评委乙")).json()["data"])
    row_b = next(x for x in pending_b if x["gdStudentId"] == gid)
    assert row_b["myStatus"] == "PENDING" and row_b["myScore"] is None

    # PC 侧台账核对：确实只有一条 judgeName=评委甲 的评分，没有产生 judgeName=评委乙 的记录
    admin_h = _defense_expert("评委甲")  # GD_DEFENSE_EXPERT 在自己面板范围内也能查列表(owner 收敛)
    lst = client.get(GD_SCORE, headers=admin_h, params={"gdStudentId": gid}).json()["data"]["items"]
    assert len(lst) == 1
    assert lst[0]["judgeName"] == "评委甲" and lst[0]["score"] == 88


def test_outsider_cannot_write_score(db_mode, client):
    gid = _seed(db_mode)
    r = client.post(f"{MOB}/teacher/graduation/defense/{gid}/score",
                    headers=_defense_expert("组外专家"), json={"score": 60})
    assert r.status_code == 403
    assert r.json()["code"] != 0 and r.json()["bizCode"] == "NO_PERMISSION"
