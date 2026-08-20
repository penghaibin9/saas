"""V3 §11 / Teacher T9 capacity contracts: routes, identity, seed safety and EXPLAIN."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPACITY_JS = REPO_ROOT / "performance" / "k6" / "capacity.js"
CONFIG_JS = REPO_ROOT / "performance" / "k6" / "lib" / "config.js"
AUTH_JS = REPO_ROOT / "performance" / "k6" / "lib" / "auth.js"
SEED_PY = REPO_ROOT / "backend" / "scripts" / "seed_mobile_capacity_school.py"
LOCAL_SEED_PY = REPO_ROOT / "performance" / "tools" / "seed_local_capacity_env.py"
EVALUATOR_PY = REPO_ROOT / "performance" / "tools" / "evaluate_capacity_result.py"
EXPLAIN_PY = REPO_ROOT / "backend" / "scripts" / "explain_mobile_v3_queries.py"


# ── P0-07：V3 新增链路必须进容量门禁 ──

def test_v3_student_routes_are_exercised_by_the_capacity_scenario():
    capacity = CAPACITY_JS.read_text(encoding="utf-8")
    for route, path in [
        ("student_agenda", "/api/v1/mobile/student/agenda"),
        ("student_cases", "/api/v1/mobile/student/cases"),
        ("student_search", "/api/v1/mobile/student/search"),
    ]:
        assert f"'{route}'" in capacity, f"{route} 未进入容量场景"
        assert path in capacity, f"{route} 没有打真实接口"


def test_v3_teacher_t9_routes_are_exercised_by_the_capacity_scenario():
    capacity = CAPACITY_JS.read_text(encoding="utf-8")
    for route, path in [
        ("teacher_my_students", "/api/v1/teacher-mobile/students?pageSize=20"),
        ("teacher_messages", "/api/v1/mobile/performance/teacher/messages-page"),
        ("teacher_visit", "/api/v1/teacher-mobile/internship/visit-targets"),
        ("teacher_employment", "/api/v1/teacher-mobile/employment/overview"),
    ]:
        assert f"'{route}'" in capacity, f"{route} 未进入 Teacher T9 容量场景"
        assert path in capacity, f"{route} 没有打真实接口"
    assert "teacher_student360" in capacity
    assert "/students/${encodeURIComponent(studentId)}/projection" in capacity
    assert "teacher_employment_verification" in capacity
    assert "/employment/students/${encodeURIComponent(employmentId)}/verification" in capacity


def test_v3_routes_have_latency_thresholds():
    config = CONFIG_JS.read_text(encoding="utf-8")
    for route in ("student_agenda", "student_cases", "student_search"):
        assert f"http_req_duration{{route:{route}}}" in config, f"{route} 缺少 route 级阈值"
    assert "REQUIRED_STUDENT_V3_ROUTES" in config
    for route in (
        "teacher_my_students", "teacher_student360", "teacher_messages",
        "teacher_visit", "teacher_employment_verification",
    ):
        assert f"http_req_duration{{route:{route}}}" in config, f"{route} 缺少 Teacher T9 route 级阈值"
    assert "REQUIRED_TEACHER_V3_ROUTES" in config


def test_artifact_flags_runs_that_missed_the_new_routes():
    capacity = CAPACITY_JS.read_text(encoding="utf-8")
    assert "missingStudentV3Routes" in capacity
    assert "missingTeacherV3Routes" in capacity
    assert "MISSING_V3_ROUTES" in capacity, "没覆盖新链路时必须在摘要里显式喊出来"


# ── P0-08：身份分布必须可区分冷启动与热缓存 ──

def test_identity_modes_are_explicit_and_validated():
    auth = AUTH_JS.read_text(encoding="utf-8")
    assert "IDENTITY_MODE" in auth
    assert "['cold', 'warm'].includes(IDENTITY_MODE)" in auth, "未知档位必须直接报错"
    assert "effectivePoolSize" in auth


def test_artifact_records_unique_tokens_and_role_distribution():
    auth = AUTH_JS.read_text(encoding="utf-8")
    capacity = CAPACITY_JS.read_text(encoding="utf-8")
    for field in (
        "uniqueStudentTokens", "uniqueTeacherTokens", "studentTokensAvailable",
        "teacherTokensAvailable", "identityMode", "uniqueTeacherContexts",
        "teacherRoleCounts", "teacherRoleRatios",
    ):
        assert field in auth, f"身份分布缺少 {field}"
    assert "identityDistribution()" in capacity
    assert '"identity": identity' in capacity or "identity," in capacity


def test_cold_teacher_capacity_requires_distinct_contexts_for_preissued_tokens():
    evaluator = EVALUATOR_PY.read_text(encoding="utf-8")
    assert '"teacherTokensAvailable": int(' in evaluator
    assert '"uniqueTeacherContexts": int(' in evaluator
    assert 'actual["teacherTokensAvailable"] > 0' in evaluator
    assert 'required["uniqueTeacherContexts"] = teacher_contexts_required' in evaluator
    assert 'actual["uniqueTeacherContexts"] >= teacher_contexts_required' in evaluator


def test_artifact_records_profile_scenario_dataset_and_per_route_latency():
    capacity = CAPACITY_JS.read_text(encoding="utf-8")
    assert "yueke-capacity-artifact/1" in capacity
    for field in ("profile:", "scenario:", "dataset:", "routes,"):
        assert field in capacity, f"Artifact 缺少 {field}"
    assert "routeLatencies" in capacity


def test_dataset_scale_is_recorded_separately_from_concurrency():
    config = CONFIG_JS.read_text(encoding="utf-8")
    assert "export const DATASET" in config
    assert "不是 10k VU" in config or "10k 并发是两件事" in config


def test_high_load_profiles_remain_locked():
    config = CONFIG_JS.read_text(encoding="utf-8")
    assert "K6_ALLOW_HIGH_LOAD" in config
    assert "K6_ALLOW_PRODUCTION_HIGH_LOAD" in config


# ── §11.1 容量种子只能进 staging/CI ──

def test_capacity_seed_refuses_to_run_without_confirmation_and_on_unsafe_targets():
    seed = SEED_PY.read_text(encoding="utf-8")
    assert "--confirm" in seed
    assert '_fail("缺少 --confirm' in seed
    assert "ALLOWED_DB_NAME_HINTS" in seed
    for hint in ("capacity", "staging", "test", "ci"):
        assert f'"{hint}"' in seed
    assert "DEFAULT_CAPACITY_TENANT" in seed
    assert 'STUDENT_PREFIX = "CAP-"' in seed


def test_capacity_seed_purge_is_tenant_scoped():
    seed = SEED_PY.read_text(encoding="utf-8")
    purge = seed[seed.index("def _purge("):seed.index("def _seed_students(")]
    assert "model.tenant_id == tenant_id" in purge
    assert re.search(r"delete\(model\)\s*\)", purge) is None


def test_capacity_seed_defaults_match_the_manual_scale():
    seed = SEED_PY.read_text(encoding="utf-8")
    assert '"--students", type=int, default=12000' in seed
    assert '"--classes", type=int, default=300' in seed
    assert '"--todos-per-student", type=int, default=7' in seed
    assert '"--messages-per-student", type=int, default=25' in seed
    assert '"--cases-per-student", type=int, default=5' in seed


def test_local_capacity_seed_provides_teacher_t9_real_objects():
    seed = LOCAL_SEED_PY.read_text(encoding="utf-8")
    for contract in ("EmpStudent", "UnifiedMessage", "receiver_context_key", "TEACHER_MESSAGE_SOURCE"):
        assert contract in seed
    assert "teacher_messages=" in seed
    assert "student_tokens=" in seed and "teacher_tokens=" in seed


def test_local_teacher_capacity_identity_uses_direct_numeric_user_id():
    seed = LOCAL_SEED_PY.read_text(encoding="utf-8")
    assert "TEACHER_USER_ID_BASE" in seed
    assert "return str(TEACHER_USER_ID_BASE + int(index))" in seed
    assert "receiver_uid = int(_teacher_user_id(index))" in seed
    assert '"currentRoleCode": "LEADER"' in seed
    assert '"currentRoleCode": "SCHOOL_ADMIN"' not in seed, (
        "fresh CI 未发布 SCHOOL_ADMIN RoleTemplate 时该角色按生产规则 fail-closed，不能冒充可用容量身份"
    )
    assert "zlib" not in seed, "容量门禁不应为每次教师消息请求制造 CRC fallback 身份开销"


# ── §11.4 / T9 EXPLAIN 门禁不得静默通过 ──

def test_explain_gate_refuses_to_pass_when_it_cannot_read_row_counts():
    explain = EXPLAIN_PY.read_text(encoding="utf-8")
    assert "_ROWS_KEYS" in explain
    assert "rows_examined_per_scan" in explain and '"rows"' in explain, "必须同时兼容 MySQL 8 与 MariaDB"
    assert "拒绝按 0 行判定通过" in explain


def test_explain_gate_covers_every_v3_hot_path():
    explain = EXPLAIN_PY.read_text(encoding="utf-8")
    for name in (
        "home_todos", "home_todos_by_due", "messages_page", "cases_keyset", "search_messages",
        "teacher_messages_page", "teacher_messages_badges",
    ):
        assert f'"name": "{name}"' in explain, f"EXPLAIN 门禁缺少热路径 {name}"
    assert "teacherMessageIdentity" in explain
    assert "budget_rows" in explain
    assert "CREATE INDEX" not in explain.upper()
