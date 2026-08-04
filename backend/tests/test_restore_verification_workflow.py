"""PLAT-12 备份恢复验证与灾备（真库）。

只测证据层 + 自检，不测试真实备份工具（mysqldump 本地未装，见
「上线前必做清单-总闸门.md」PLAT-07/12 条目——两卡都卡在同一处真实
基础设施缺口）。重点：①成功备份必须有位置引用，不能"我说成功就成功"；
②结构自检是真实只读查询，不是摆设——用当前测试库跑一次，验证它能
正确识别声明表和实际表一致；③过期判定按备份类型分别算阈值；④恢复
演练不能挂靠不存在的备份证据。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException


# ── PLAT12-T01：成功备份必须有位置引用，不能空口说成功 ─────────────────────
def test_t01_succeeded_evidence_requires_location_ref(db_mode):
    from app.services import disaster_recovery_service as dr

    with pytest.raises(AppException) as exc:
        dr.record_backup_evidence(None, {
            "backupType": "DATABASE_DUMP", "method": "MANUAL_CONFIRMED", "status": "SUCCEEDED",
        })
    assert exc.value.code == "VALIDATION_ERROR"

    out = dr.record_backup_evidence(None, {
        "backupType": "DATABASE_DUMP", "method": "MANUAL_CONFIRMED", "status": "SUCCEEDED",
        "locationRef": "cdb-backup-20260804-001",
    })
    assert out["status"] == "SUCCEEDED"
    assert out["locationRef"] == "cdb-backup-20260804-001"


def test_t01b_failed_evidence_does_not_require_location_ref(db_mode):
    from app.services import disaster_recovery_service as dr

    out = dr.record_backup_evidence(None, {
        "backupType": "DATABASE_DUMP", "method": "MYSQLDUMP", "status": "FAILED",
        "errorMessage": "mysqldump: command not found",
    })
    assert out["status"] == "FAILED"
    assert "not found" in out["errorMessage"]


# ── PLAT12-T02：结构自检是真实只读查询，当前测试库应该完全一致 ─────────────
def test_t02_schema_integrity_check_passes_against_real_test_db(db_mode):
    from app.services import disaster_recovery_service as dr

    out = dr.run_schema_integrity_check()
    assert out["backupType"] == "SCHEMA_INTEGRITY"
    assert out["status"] == "SUCCEEDED", out["detail"]  # 当前测试库由 Base.metadata 建出，理应完全一致
    assert out["tableCount"] > 100  # 真实表数量级校验，不是空跑
    assert out["checksumSha256"]


def test_t02b_schema_integrity_check_detects_missing_table(db_mode):
    """验证"表缺失能被查出来"，但不对共享测试库真的做 DDL——多个 worktree
    可能同时在跑测试，真 DROP 一张表会波及别的并发会话。改成给declared_metadata
    临时加一张真实数据库里必然不存在的"幽灵表"，验证自检能查出这张表缺失。"""
    import sqlalchemy as sa

    import app.db.base as base_module
    from app.services import disaster_recovery_service as dr

    ghost = sa.Table(
        "t_ghost_table_that_will_never_exist_in_real_db", base_module.metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        extend_existing=True,
    )
    try:
        out = dr.run_schema_integrity_check()
        assert out["status"] == "FAILED"
        assert "t_ghost_table_that_will_never_exist_in_real_db" in out["detail"]["missingTables"]
    finally:
        base_module.metadata.remove(ghost)


# ── PLAT12-T03：过期判定按类型分别算阈值 ────────────────────────────────────
def test_t03_staleness_is_computed_per_backup_type(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.disaster_recovery import BackupEvidence
    from app.services import disaster_recovery_service as dr

    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        # t_backup_evidence 是平台级全局表（不按租户隔离，本身就该是这样——
        # 备份是整个数据库级别的事，不是某个学校的事）。FAST_TEST_SCHEMA 的
        # 清理理论上会在每个用例开始前清空它，但这条断言依赖"哪一条是最新的
        # 成功记录"，为了不让这个用例的正确性依赖清理时机，这里显式清空一次，
        # 不管测试库当前状态如何都能保证本用例自己造的数据是唯一数据源。
        db.query(BackupEvidence).delete()
        db.commit()
        # DATABASE_DUMP 阈值 2 天：3 天前的成功备份应判定过期
        db.add(BackupEvidence(
            backup_type="DATABASE_DUMP", method="MANUAL_CONFIRMED", status="SUCCEEDED",
            location_ref="old-backup", detail_json={},
            started_at=now - timedelta(days=3), finished_at=now - timedelta(days=3)))
        # SCHEMA_INTEGRITY 阈值 7 天：1 天前的成功自检不算过期
        db.add(BackupEvidence(
            backup_type="SCHEMA_INTEGRITY", method="SCHEMA_INSPECT", status="SUCCEEDED",
            detail_json={}, started_at=now - timedelta(days=1), finished_at=now - timedelta(days=1)))
        db.commit()
    finally:
        db.close()

    board = dr.governance_overview()
    assert board["byType"]["DATABASE_DUMP"]["stale"] is True
    assert board["byType"]["SCHEMA_INTEGRITY"]["stale"] is False


def test_t03b_no_evidence_at_all_means_stale_by_default(db_mode):
    from app.services import disaster_recovery_service as dr

    board = dr.governance_overview()
    assert board["byType"]["FILE_STORAGE_SYNC"]["hasEvidence"] is False
    assert board["byType"]["FILE_STORAGE_SYNC"]["stale"] is True  # 没有证据默认按"过期/未知"处理，不是默认健康


# ── PLAT12-T04：恢复演练不能挂靠不存在的备份证据 ───────────────────────────
def test_t04_restore_drill_rejects_nonexistent_backup_evidence(db_mode):
    from app.services import disaster_recovery_service as dr

    with pytest.raises(AppException) as exc:
        dr.record_restore_drill(None, {
            "drillType": "MANUAL_CONFIRMED", "status": "PASSED",
            "backupEvidenceId": "999999999",
        })
    assert exc.value.http_status == 404


def test_t04b_restore_drill_without_backup_link_is_allowed(db_mode):
    from app.services import disaster_recovery_service as dr

    out = dr.record_restore_drill(None, {
        "drillType": "MANUAL_CONFIRMED", "status": "PASSED",
        "targetDescription": "在隔离测试环境用最新备份恢复并核对学生数一致",
    })
    assert out["status"] == "PASSED"
    board = dr.governance_overview()
    assert board["restoreDrill"]["hasPassedDrill"] is True
    assert board["restoreDrill"]["stale"] is False


# ── HTTP：仅平台超管可访问 ──────────────────────────────────────────────
def test_http_disaster_recovery_requires_platform_super_admin(client, db_mode):
    from app.core.security import create_access_token

    school_token = create_access_token({
        "userId": "u-plat12-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/disaster-recovery/overview",
                   headers={"Authorization": f"Bearer {school_token}"})
    assert r.status_code == 403

    admin_token = create_access_token({
        "userId": "u-plat12-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = client.post("/api/v1/platform/disaster-recovery/schema-check", headers=headers)
    body = r.json()
    assert body["code"] == 0, body
    assert body["data"]["status"] in ("SUCCEEDED", "FAILED")

    r = client.get("/api/v1/platform/disaster-recovery/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()
