"""材料规则启用（目录迁移）规模回归：500+ 学生批次在限定时间内完成，行为不变。

原实现对每一行学生材料逐行 ORM 更新，6402 人批次约 4.5 分钟；现改为分批集合 UPDATE / 批量插入。
这里只断言“不超时”（pytest-timeout），不断言具体秒数；同时逐项核对迁移结果与原逻辑一致：
- 未归档学生的材料全部指向新规则，名称/必交状态随新规则更新；
- 新规则删掉且没有文件的空材料行被逻辑删除；
- 已归档学生、已冻结材料原样保留；
- 新规则新增的材料项为每位未归档学生补建占位；
- 被删掉的材料项里只要有一份已上传文件，整次启用被拒绝，数据不变。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

MAIN = 1000000000000000001
STUDENTS = 520
USER = {"userId": "1", "tenantId": str(MAIN), "realName": "规则管理员", "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "TEACHER", "activeContextId": "ctx", "dataScope": "ALL"}


def _ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(MAIN)})
    set_current_user(USER)


def _clear():
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def _items(*, drop=(), rename=None, extra=()):
    from app.modules.graduation.materials.definitions import DEFAULT_MATERIAL_DEFINITIONS

    rows = [dict(row) for row in DEFAULT_MATERIAL_DEFINITIONS if row["materialCode"] not in drop]
    for row in rows:
        if rename and row["materialCode"] in rename:
            row["materialName"] = rename[row["materialCode"]]
    rows.extend(extra)
    return rows


def _seed_batch_with_enabled_rule() -> int:
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationStudent
    from app.modules.graduation.materials import rule_service

    db = get_sessionmaker()()
    try:
        suffix = uuid.uuid4().hex[:8].upper()
        batch = GraduationBatch(tenant_id=MAIN, batch_name=f"规模规则{suffix}", batch_no=f"GD-SCALE-{suffix}",
                                grade_year="2026届", status="RUNNING")
        db.add(batch)
        db.flush()
        db.add_all([
            GraduationStudent(tenant_id=MAIN, batch_id=int(batch.id), student_no=f"SC{suffix}{i:04d}",
                              name=f"规模生{i:04d}", stage="TOPIC_SELECTING", record_status="ACTIVE")
            for i in range(STUDENTS)
        ])
        db.commit()
        batch_id = int(batch.id)
    finally:
        db.close()
    created = rule_service.create_rule({"batchId": str(batch_id), "useDefaultTemplate": True}, USER)
    rule_service.activate_rule(int(created["id"]), USER, expected_version=_rule_version(int(created["id"])),
                               confirm_catalog_repair=True)
    return batch_id


def _rule_version(rule_id: int) -> int:
    from app.db.session import get_sessionmaker
    from app.models.graduation_material import GraduationMaterialRule

    db = get_sessionmaker()()
    try:
        return int(db.get(GraduationMaterialRule, int(rule_id)).version or 0)
    finally:
        db.close()


@pytest.mark.timeout(600)
def test_activate_rule_migrates_500_plus_students_with_unchanged_behavior(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    from app.models.graduation_material import GraduationStudentMaterial
    from app.modules.graduation.materials import rule_service

    _ctx()
    try:
        batch_id = _seed_batch_with_enabled_rule()
        db = get_sessionmaker()()
        try:
            students = list(db.scalars(select(GraduationStudent).where(
                GraduationStudent.batch_id == batch_id).order_by(GraduationStudent.id)).all())
            assert len(students) == STUDENTS
            per_student = int(db.scalar(select(func.count()).select_from(GraduationStudentMaterial).where(
                GraduationStudentMaterial.gd_student_id == int(students[0].id),
                GraduationStudentMaterial.is_deleted.is_(False))))
            archived = students[0]
            archived.stage = "ARCHIVED"
            frozen_row = db.scalars(select(GraduationStudentMaterial).where(
                GraduationStudentMaterial.gd_student_id == int(students[1].id),
                GraduationStudentMaterial.material_code == "TASKBOOK")).one()
            frozen_row.archive_status = "FROZEN"
            db.commit()
            archived_id, frozen_id = int(archived.id), int(frozen_row.id)
        finally:
            db.close()

        draft = rule_service.create_rule({
            "batchId": str(batch_id),
            "items": _items(
                drop=("TEMPLATE_REFERENCE",),
                rename={"GUIDANCE_RECORD": "指导记录表（新版）"},
                extra=({"materialCode": "TOPIC_WISH_CONFIRM", "materialName": "选题志愿确认单", "stage": "TOPIC",
                        "ownerRole": "STUDENT", "required": True, "allowedExtensions": ["pdf"],
                        "maxSizeBytes": 10 * 1024 * 1024, "reviewRequired": False, "archiveRequired": True,
                        "sensitivityLevel": "SENSITIVE"},),
            ),
        }, USER)
        rule_id = int(draft["id"])
        result = rule_service.activate_rule(rule_id, USER, expected_version=_rule_version(rule_id),
                                            confirm_catalog_repair=True)

        migration = result["catalogMigration"]
        active = STUDENTS - 1
        assert migration["preservedArchived"] == per_student + 1  # 归档学生全部行 + 1 行冻结材料
        assert migration["removedEmpty"] == active - 0  # 每位未归档学生 1 行 TEMPLATE_REFERENCE
        assert migration["migrated"] == active * per_student - active - 1
        assert migration["created"] == active  # 新增“选题志愿确认单”占位
        assert migration["studentCount"] == active

        db = get_sessionmaker()()
        try:
            def rows(**filters):
                stmt = select(GraduationStudentMaterial).where(GraduationStudentMaterial.batch_id == batch_id)
                for key, value in filters.items():
                    stmt = stmt.where(getattr(GraduationStudentMaterial, key) == value)
                return list(db.scalars(stmt).all())

            live = [r for r in rows(is_deleted=False) if int(r.gd_student_id) != archived_id and int(r.id) != frozen_id]
            assert live and all(int(r.rule_id) == rule_id for r in live)
            guidance = [r for r in live if r.material_code == "GUIDANCE_RECORD"]
            assert len(guidance) == active and all(r.material_name == "指导记录表（新版）" for r in guidance)
            assert all(r.required_status == "REQUIRED" for r in guidance)
            removed = rows(material_code="TEMPLATE_REFERENCE")
            assert all(r.is_deleted for r in removed if int(r.gd_student_id) != archived_id)
            assert len(rows(material_code="TOPIC_WISH_CONFIRM", is_deleted=False)) == active
            # 已归档学生与冻结材料保持旧规则。
            assert all(int(r.rule_id) != rule_id for r in rows(gd_student_id=archived_id))
            assert int(db.get(GraduationStudentMaterial, frozen_id).rule_id) != rule_id
        finally:
            db.close()
    finally:
        _clear()


@pytest.mark.timeout(600)
def test_activate_rule_rejects_removing_material_that_has_a_file_and_changes_nothing(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models.graduation_material import GraduationStudentMaterial
    from app.modules.graduation.materials import rule_service

    _ctx()
    try:
        batch_id = _seed_batch_with_enabled_rule()
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(GraduationStudentMaterial).where(
                GraduationStudentMaterial.batch_id == batch_id,
                GraduationStudentMaterial.material_code == "TEMPLATE_REFERENCE",
            ).order_by(GraduationStudentMaterial.id.desc()).limit(1)).one()
            row.current_version_id = 987654321
            db.commit()
            before = sorted((int(r.id), int(r.rule_id), bool(r.is_deleted), r.material_name) for r in db.scalars(
                select(GraduationStudentMaterial).where(GraduationStudentMaterial.batch_id == batch_id)).all())
        finally:
            db.close()

        draft = rule_service.create_rule({"batchId": str(batch_id), "items": _items(drop=("TEMPLATE_REFERENCE",))}, USER)
        rule_id = int(draft["id"])
        with pytest.raises(AppException) as exc:
            rule_service.activate_rule(rule_id, USER, expected_version=_rule_version(rule_id),
                                       confirm_catalog_repair=True)
        assert exc.value.code == "MATERIAL_RULE_REMOVAL_CONFLICT"

        db = get_sessionmaker()()
        try:
            after = sorted((int(r.id), int(r.rule_id), bool(r.is_deleted), r.material_name) for r in db.scalars(
                select(GraduationStudentMaterial).where(GraduationStudentMaterial.batch_id == batch_id)).all())
            assert after == before
        finally:
            db.close()
    finally:
        _clear()
