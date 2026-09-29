"""老师毕设工作台（PC 与教师小程序共用的只读聚合）。

一个老师可以同时是指导教师、评阅教师、答辩评委、答辩秘书。工作台把这些身份下
“现在轮到我做的事”按业务先后排成一张清单，老师不用切换角色、也不用记菜单位置。

- 只读；每条待办都指向既有的正式处理页面/接口，处理逻辑、状态机、权限校验不在这里复制。
- 只认稳定 ID：导师台账（工号 = 登录名）→ mentor_id / reviewer_mentor_id / 答辩席位 / 秘书 ID。
- 每类待办最多返回 ITEM_LIMIT 条明细，另给真实总数；不在内存里收齐整批再分页。
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from app.models import (
    GraduationBatch,
    GraduationDefenseGroup,
    GraduationDefenseScore,
    GraduationFinal,
    GraduationGrade,
    GraduationMidterm,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTaskBook,
    GraduationTopic,
    GraduationTopicChangeRequest,
    GraduationTopicChoice,
)
from app.modules.graduation.services import graduation_auto_identity as auto
from app.services.db_service import _iso, _tid, session

ITEM_LIMIT = 50

# 任务在工作台上的先后顺序＝毕业设计业务顺序。
TASK_META: dict[str, dict] = {
    "topicChoice": {"identity": "GD_MENTOR", "title": "确认学生选题", "action": "topic.choice",
                    "hint": "学生选了你出的题目，确认后才算定题。"},
    "topicChange": {"identity": "GD_MENTOR", "title": "审核换题申请", "action": "topic.change",
                    "hint": "学生申请更换题目，需要你同意或退回。"},
    "taskbook": {"identity": "GD_MENTOR", "title": "下达任务书", "action": "taskbook.issue",
                 "hint": "已定题的学生还没有任务书，下达后学生确认即可开始。"},
    "proposal": {"identity": "GD_MENTOR", "title": "批阅开题报告", "action": "proposal.review",
                 "hint": "学生已提交开题报告，等你通过或退回修改。"},
    "midterm": {"identity": "GD_MENTOR", "title": "中期检查", "action": "midterm.check",
                "hint": "开题已通过的学生可以做中期检查；学生交了整改也在这里复核。"},
    "final": {"identity": "GD_MENTOR", "title": "批阅论文", "action": "final.review",
              "hint": "学生已提交论文（初稿/定稿），等你通过或退回修改。"},
    "advisorScore": {"identity": "GD_MENTOR", "title": "打导师分", "action": "advisor.score",
                     "hint": "论文定稿已通过的学生，给出你的导师分（综合成绩的一部分）。"},
    "review": {"identity": "GD_REVIEWER", "title": "评阅论文", "action": "review.submit",
               "hint": "学校分给你评阅的论文，打分并写评阅意见。"},
    "defenseScore": {"identity": "GD_DEFENSE_EXPERT", "title": "答辩评分", "action": "defense.score",
                     "hint": "你所在答辩组的学生，答辩后给出评分。"},
    "defenseConfirm": {"identity": "GD_DEFENSE_SECRETARY", "title": "确认答辩成绩", "action": "defense.confirm",
                       "hint": "本组评委都已评完分的学生，核对后确认成绩。"},
}
TASK_ORDER = tuple(TASK_META)


def _stage_label(stage: str | None) -> str:
    try:
        from app.modules.graduation.services.graduation_student_service import STAGE_LABEL
        return STAGE_LABEL.get(str(stage or ""), str(stage or ""))
    except Exception:  # noqa: BLE001
        return str(stage or "")


def _student_brief(student: GraduationStudent) -> dict:
    return {
        "gdStudentId": str(student.id), "studentName": student.name, "studentNo": student.student_no or "",
        "className": student.class_name or "", "topicTitle": student.topic_title or "",
        "stage": student.stage, "stageLabel": _stage_label(student.stage),
        "batchId": str(student.batch_id) if student.batch_id else None,
    }


def _task(key: str, items: list[dict], total: int) -> dict:
    meta = TASK_META[key]
    return {
        "key": key, "identity": meta["identity"], "identityLabel": auto.IDENTITY_LABELS[meta["identity"]],
        "title": meta["title"], "hint": meta["hint"], "action": meta["action"],
        "count": int(total), "items": items[:ITEM_LIMIT], "truncated": int(total) > len(items[:ITEM_LIMIT]),
    }


def _batch_ids(db, tenant_id: int, batch_id) -> list[int]:
    if batch_id not in (None, ""):
        row = db.get(GraduationBatch, int(batch_id))
        if row is None or row.is_deleted or int(row.tenant_id) != int(tenant_id):
            return []
        return [int(row.id)]
    return [int(x) for x in db.scalars(select(GraduationBatch.id).where(
        GraduationBatch.tenant_id == tenant_id,
        GraduationBatch.is_deleted.is_(False),
        GraduationBatch.status.in_(auto.ACTIVE_BATCH_STATUSES),
    )).all()]


def _student_filters(tenant_id: int, batch_ids: list[int]) -> list:
    return [
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.batch_id.in_(batch_ids or [-1]),
    ]


def _count_and_rows(db, count_stmt, rows_stmt) -> tuple[int, list]:
    total = int(db.scalar(count_stmt) or 0)
    rows = db.execute(rows_stmt.limit(ITEM_LIMIT)).all() if total else []
    return total, rows


def _mentor_tasks(db, tenant_id: int, mentor_id: int, batch_ids: list[int]) -> list[dict]:
    from app.modules.graduation.services import graduation_process_consistency as process

    mine = [*_student_filters(tenant_id, batch_ids), GraduationStudent.mentor_id == int(mentor_id)]
    tasks: list[dict] = []

    # 1. 确认学生选题：我出的题目下待确认的志愿（学生不一定已经分给我）
    my_topics = select(GraduationTopic.id).where(
        GraduationTopic.tenant_id == tenant_id, GraduationTopic.is_deleted.is_(False),
        GraduationTopic.advisor_mentor_id == int(mentor_id),
    )
    choice_where = [
        GraduationTopicChoice.tenant_id == tenant_id, GraduationTopicChoice.is_deleted.is_(False),
        GraduationTopicChoice.status == "PENDING", GraduationTopicChoice.topic_id.in_(my_topics),
        *_student_filters(tenant_id, batch_ids),
    ]
    join_choice = GraduationStudent.id == GraduationTopicChoice.gd_student_id
    total, rows = _count_and_rows(
        db,
        select(func.count(GraduationTopicChoice.id)).select_from(GraduationTopicChoice)
        .join(GraduationStudent, join_choice).where(*choice_where),
        select(GraduationTopicChoice, GraduationStudent, GraduationTopic.title)
        .join(GraduationStudent, join_choice)
        .join(GraduationTopic, GraduationTopic.id == GraduationTopicChoice.topic_id)
        .where(*choice_where).order_by(GraduationTopicChoice.choice_order, GraduationTopicChoice.id),
    )
    tasks.append(_task("topicChoice", [{
        **_student_brief(stu), "id": str(choice.id), "topicTitle": title or "",
        "status": choice.status, "statusLabel": f"第{choice.choice_order}志愿", "submittedAt": _iso(choice.created_at),
    } for choice, stu, title in rows], total))

    # 2. 审核换题申请：原题目或新题目是我出的
    change_where = [
        GraduationTopicChangeRequest.tenant_id == tenant_id, GraduationTopicChangeRequest.is_deleted.is_(False),
        GraduationTopicChangeRequest.status == "PENDING",
        or_(GraduationTopicChangeRequest.old_topic_id.in_(my_topics),
            GraduationTopicChangeRequest.new_topic_id.in_(my_topics)),
        *_student_filters(tenant_id, batch_ids),
    ]
    join_change = GraduationStudent.id == GraduationTopicChangeRequest.gd_student_id
    total, rows = _count_and_rows(
        db,
        select(func.count(GraduationTopicChangeRequest.id)).select_from(GraduationTopicChangeRequest)
        .join(GraduationStudent, join_change).where(*change_where),
        select(GraduationTopicChangeRequest, GraduationStudent)
        .join(GraduationStudent, join_change).where(*change_where)
        .order_by(GraduationTopicChangeRequest.id),
    )
    tasks.append(_task("topicChange", [{
        **_student_brief(stu), "id": str(req.id), "status": req.status, "statusLabel": "待审核",
        "note": req.reason or "", "submittedAt": _iso(req.requested_at or req.created_at),
    } for req, stu in rows], total))

    # 3. 下达任务书：已定题、还没有任务书的我的学生
    no_taskbook = ~select(GraduationTaskBook.id).where(
        GraduationTaskBook.tenant_id == GraduationStudent.tenant_id,
        GraduationTaskBook.gd_student_id == GraduationStudent.id,
        GraduationTaskBook.is_deleted.is_(False),
    ).exists()
    taskbook_where = [*mine, GraduationStudent.topic_id.is_not(None),
                      GraduationStudent.stage.in_(("TOPIC_SELECTING", "TASKBOOK_CONFIRM")), no_taskbook]
    total, rows = _count_and_rows(
        db,
        select(func.count(GraduationStudent.id)).where(*taskbook_where),
        select(GraduationStudent).where(*taskbook_where).order_by(GraduationStudent.id),
    )
    tasks.append(_task("taskbook", [{
        **_student_brief(stu), "id": str(stu.id), "status": "NOT_ISSUED", "statusLabel": "未下达",
        "submittedAt": None,
    } for (stu,) in rows], total))

    # 4. 批阅开题报告 / 6. 批阅论文：待审材料
    def _material(key, model, label):
        where = [model.tenant_id == tenant_id, model.is_deleted.is_(False),
                 model.status == "PENDING_REVIEW", *mine]
        join_on = GraduationStudent.id == model.gd_student_id
        total, rows = _count_and_rows(
            db,
            select(func.count(model.id)).select_from(model).join(GraduationStudent, join_on).where(*where),
            select(model, GraduationStudent).join(GraduationStudent, join_on).where(*where)
            .order_by(model.submit_at.is_(None), model.submit_at, model.id),
        )
        return _task(key, [{
            **_student_brief(stu), "id": str(row.id), "status": row.status,
            "statusLabel": label(row), "submittedAt": _iso(row.submit_at),
            "version": row.version or "",
        } for row, stu in rows], total)

    proposal_task = _material(
        "proposal", GraduationProposal, lambda row: "重新提交" if row.is_resubmit else "待批阅")

    # 5. 中期检查：待检查（含尚未建记录的学生）+ 整改待复核
    virtual_where = [*mine, process._midterm_eligible_clause(), process._no_midterm_row()]
    mid_where = [GraduationMidterm.tenant_id == tenant_id, GraduationMidterm.is_deleted.is_(False),
                 GraduationMidterm.status.in_(("PENDING", "RECTIFY_SUBMITTED")), *mine]
    join_mid = GraduationStudent.id == GraduationMidterm.gd_student_id
    virtual_total = int(db.scalar(select(func.count(GraduationStudent.id)).where(*virtual_where)) or 0)
    real_total = int(db.scalar(select(func.count(GraduationMidterm.id)).select_from(GraduationMidterm)
                               .join(GraduationStudent, join_mid).where(*mid_where)) or 0)
    mid_items: list[dict] = []
    if real_total:
        for row, stu in db.execute(select(GraduationMidterm, GraduationStudent).join(GraduationStudent, join_mid)
                                   .where(*mid_where).order_by(GraduationMidterm.id).limit(ITEM_LIMIT)).all():
            rectify = row.status == "RECTIFY_SUBMITTED"
            mid_items.append({**_student_brief(stu), "id": str(row.id), "status": row.status,
                              "statusLabel": "整改待复核" if rectify else "待检查",
                              "submittedAt": _iso(row.rectify_submitted_at if rectify else row.created_at)})
    if virtual_total and len(mid_items) < ITEM_LIMIT:
        for stu in db.scalars(select(GraduationStudent).where(*virtual_where)
                              .order_by(GraduationStudent.id).limit(ITEM_LIMIT - len(mid_items))).all():
            mid_items.append({**_student_brief(stu), "id": None, "status": "PENDING",
                              "statusLabel": "待检查", "submittedAt": None})
    midterm_task = _task("midterm", mid_items, virtual_total + real_total)

    final_task = _material("final", GraduationFinal, lambda row: f"{row.final_type or '论文'}待批阅")
    # 7. 打导师分：定稿已通过、导师分还没打、成绩未发布的我的学生
    latest_final_id = select(func.max(GraduationFinal.id)).where(
        GraduationFinal.tenant_id == GraduationStudent.tenant_id,
        GraduationFinal.gd_student_id == GraduationStudent.id,
        GraduationFinal.is_deleted.is_(False),
    ).correlate(GraduationStudent).scalar_subquery()
    final_approved = select(GraduationFinal.id).where(
        GraduationFinal.id == latest_final_id, GraduationFinal.status == "APPROVED").exists()
    no_advisor_score = ~select(GraduationGrade.id).where(
        GraduationGrade.tenant_id == GraduationStudent.tenant_id,
        GraduationGrade.gd_student_id == GraduationStudent.id,
        GraduationGrade.is_deleted.is_(False),
        or_(GraduationGrade.advisor_score.is_not(None), GraduationGrade.status == "PUBLISHED"),
    ).exists()
    score_where = [*mine, final_approved, no_advisor_score]
    total, rows = _count_and_rows(
        db,
        select(func.count(GraduationStudent.id)).where(*score_where),
        select(GraduationStudent).where(*score_where).order_by(GraduationStudent.id),
    )
    score_task = _task("advisorScore", [{
        **_student_brief(stu), "id": str(stu.id), "status": "NOT_SCORED", "statusLabel": "待打导师分",
        "submittedAt": None,
    } for (stu,) in rows], total)
    tasks.extend([proposal_task, midterm_task, final_task, score_task])
    return tasks


def _review_task(db, tenant_id: int, mentor_id: int, batch_ids: list[int]) -> dict:
    where = [GraduationReview.tenant_id == tenant_id, GraduationReview.is_deleted.is_(False),
             GraduationReview.reviewer_mentor_id == int(mentor_id),
             GraduationReview.status.in_(("ASSIGNED", "REVIEWING", "RETURNED")),
             *_student_filters(tenant_id, batch_ids)]
    join_on = GraduationStudent.id == GraduationReview.gd_student_id
    total, rows = _count_and_rows(
        db,
        select(func.count(GraduationReview.id)).select_from(GraduationReview).join(GraduationStudent, join_on).where(*where),
        select(GraduationReview, GraduationStudent).join(GraduationStudent, join_on).where(*where)
        .order_by(GraduationReview.id),
    )
    labels = {"ASSIGNED": "待评阅", "REVIEWING": "评阅中", "RETURNED": "被退回重评"}
    return _task("review", [{
        **_student_brief(stu), "id": str(row.id), "status": row.status,
        "statusLabel": labels.get(row.status, row.status), "submittedAt": _iso(row.assigned_at),
    } for row, stu in rows], total)


def _my_groups(db, tenant_id: int, mentor, batch_ids: list[int]) -> list[tuple]:
    """我所在的答辩组：[(group, 我的席位角色集合)]。"""
    from app.modules.graduation.services import graduation_identity as gid

    out = []
    for group in db.scalars(select(GraduationDefenseGroup).where(
        GraduationDefenseGroup.tenant_id == tenant_id,
        GraduationDefenseGroup.is_deleted.is_(False),
        GraduationDefenseGroup.batch_id.in_(batch_ids or [-1]),
    ).order_by(GraduationDefenseGroup.id)).all():
        roles = []
        if group.chair_mentor_id is not None and int(group.chair_mentor_id) == int(mentor.id):
            roles.append("组长")
        elif any(gid.user_matches_judge_seat(seat, mentor=mentor) for seat in gid.judge_panel_seats(group)):
            roles.append("评委")
        if group.secretary_mentor_id is not None and int(group.secretary_mentor_id) == int(mentor.id):
            roles.append("秘书")
        if roles:
            out.append((group, roles))
    return out


def _group_students(db, tenant_id: int, group_id: int) -> list[GraduationStudent]:
    return db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id, GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.defense_group_id == int(group_id),
    ).order_by(GraduationStudent.id)).all()


def _round_scores(db, tenant_id: int, student_id: int) -> tuple[int, list]:
    from app.modules.graduation.services import graduation_defense_score_service as score_svc
    round_no = score_svc._active_round_no(db, int(student_id))
    rows = db.scalars(select(GraduationDefenseScore).where(
        GraduationDefenseScore.tenant_id == tenant_id,
        GraduationDefenseScore.gd_student_id == int(student_id),
        GraduationDefenseScore.round_no == round_no,
        GraduationDefenseScore.is_deleted.is_(False),
    )).all()
    return round_no, rows


def _defense_tasks(db, tenant_id: int, mentor, groups: list[tuple], held: frozenset) -> tuple[dict | None, dict | None, list[dict]]:
    from app.modules.graduation.services import graduation_identity as gid

    score_items: list[dict] = []
    confirm_items: list[dict] = []
    group_rows: list[dict] = []
    for group, roles in groups:
        students = _group_students(db, tenant_id, group.id)
        seats = gid.judge_panel_seats(group)
        my_seat = next((seat for seat in seats if gid.user_matches_judge_seat(seat, mentor=mentor)), None)
        scored_by_me = 0
        confirmable = 0
        for stu in students:
            if not group.published:
                continue
            round_no, rows = _round_scores(db, tenant_id, stu.id)
            base = {**_student_brief(stu), "groupId": str(group.id), "groupName": group.group_name,
                    "defenseDate": group.defense_date or "", "location": group.location or "", "roundNo": round_no}
            if my_seat is not None and ("组长" in roles or "评委" in roles):
                mine = next((row for row in rows if gid.score_row_covers_seat(row, my_seat)), None)
                if mine is None or mine.status == "PENDING":
                    score_items.append({**base, "id": str(mine.id) if mine else None, "status": "PENDING",
                                        "statusLabel": "二次答辩待评分" if round_no > 1 else "待评分",
                                        "submittedAt": None})
                else:
                    scored_by_me += 1
            if "秘书" in roles and seats and rows:
                all_scored = all(any(gid.score_row_covers_seat(row, seat) and row.status != "PENDING" for row in rows)
                                 for seat in seats)
                if all_scored and any(row.status != "CONFIRMED" for row in rows):
                    confirmable += 1
                    confirm_items.append({**base, "id": str(stu.id), "status": "SCORED",
                                          "statusLabel": f"{len(seats)} 位评委已评完", "submittedAt": None})
        group_rows.append({
            "id": str(group.id), "groupName": group.group_name, "defenseDate": group.defense_date or "",
            "location": group.location or "", "published": bool(group.published), "myRoles": roles,
            "studentCount": len(students), "judgeCount": len(seats),
            "scoredByMe": scored_by_me, "confirmable": confirmable,
        })
    score_task = _task("defenseScore", score_items, len(score_items)) if "GD_DEFENSE_EXPERT" in held else None
    confirm_task = _task("defenseConfirm", confirm_items, len(confirm_items)) if "GD_DEFENSE_SECRETARY" in held else None
    return score_task, confirm_task, group_rows


def _my_students(db, tenant_id: int, mentor_id: int, batch_ids: list[int], limit: int = 300) -> tuple[int, list[dict]]:
    from app.models import GraduationGuidance

    where = [*_student_filters(tenant_id, batch_ids), GraduationStudent.mentor_id == int(mentor_id)]
    total = int(db.scalar(select(func.count(GraduationStudent.id)).where(*where)) or 0)
    students = db.scalars(select(GraduationStudent).where(*where)
                          .order_by(GraduationStudent.class_name, GraduationStudent.student_no, GraduationStudent.id)
                          .limit(limit)).all()
    ids = [stu.id for stu in students]
    last_guidance = dict(db.execute(select(GraduationGuidance.gd_student_id, func.max(GraduationGuidance.guidance_date))
                                    .where(GraduationGuidance.tenant_id == tenant_id,
                                           GraduationGuidance.is_deleted.is_(False),
                                           GraduationGuidance.gd_student_id.in_(ids or [-1]))
                                    .group_by(GraduationGuidance.gd_student_id)).all()) if ids else {}
    return total, [{
        **_student_brief(stu), "riskLevel": stu.risk_level or "NONE",
        "lastGuidanceAt": _iso(last_guidance.get(stu.id)), "defenseGroup": stu.defense_group or "",
    } for stu in students]


def build(user: dict, batch_id=None) -> dict:
    """老师工作台：我的身份、按业务顺序的待办、我指导的学生、我所在的答辩组。"""
    from app.db.session import db_enabled
    from app.models import GraduationMentor

    empty = {
        "identities": [], "identityLabels": [], "mentorId": None, "batchIds": [],
        "tasks": [], "todoTotal": 0, "students": [], "studentTotal": 0, "groups": [],
        "message": "你的账号还没有对应的毕业设计导师台账，学校把你加入导师名单（工号与登录账号一致）后，这里会自动出现你的毕设工作。",
    }
    if not db_enabled() or not user:
        return empty
    tenant_id = _tid()
    login = str(user.get("loginName") or "").strip()
    with session() as db:
        held, mentor_id = auto.compute_identities(db, tenant_id, login) if login else (frozenset(), None)
        base = auto._base_role(user)
        if base in auto.IDENTITY_ORDER and mentor_id is not None:
            held = held | {base}  # 学校手工授予的毕设老师角色仍然有效
        if mentor_id is None:
            return empty
        mentor = db.get(GraduationMentor, int(mentor_id))
        batch_ids = _batch_ids(db, tenant_id, batch_id)
        tasks: list[dict] = []
        students: list[dict] = []
        student_total = 0
        if "GD_MENTOR" in held:
            tasks.extend(_mentor_tasks(db, tenant_id, int(mentor_id), batch_ids))
            student_total, students = _my_students(db, tenant_id, int(mentor_id), batch_ids)
        if "GD_REVIEWER" in held:
            tasks.append(_review_task(db, tenant_id, int(mentor_id), batch_ids))
        groups = _my_groups(db, tenant_id, mentor, batch_ids) if mentor is not None else []
        score_task, confirm_task, group_rows = _defense_tasks(db, tenant_id, mentor, groups, held)
        tasks.extend(task for task in (score_task, confirm_task) if task is not None)

    order = {key: index for index, key in enumerate(TASK_ORDER)}
    tasks.sort(key=lambda task: order.get(task["key"], 99))
    identities = [i for i in auto.IDENTITY_ORDER if i in held]
    return {
        "identities": identities,
        "identityLabels": [auto.IDENTITY_LABELS[i] for i in identities],
        "mentorId": str(mentor_id),
        "batchIds": [str(x) for x in batch_ids],
        "tasks": tasks,
        "todoTotal": sum(task["count"] for task in tasks),
        "students": students,
        "studentTotal": student_total,
        "groups": group_rows,
        "message": "" if identities else "你目前没有进行中的毕设工作。",
    }
