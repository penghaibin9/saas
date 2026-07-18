"""13B-培养方案二级模块第三轮续工 · 端到端：实践环节 / 方案变更 / 方案归档。

TR1 实践环节：编制态增删改 + 非编制态 409 + 周数<=0 校验失败。
TR2 方案变更：冻结→恢复（无绑定回 PUBLISHED / 有绑定回 ENABLED 两分支）→停用（终态）+
    原因<5字 400 + 终态再变更 409 + 变更记录可查。
TR3 方案归档：DISABLED 与版本链 SUPERSEDED 两类均出现在只读列表，普通 DRAFT 不出现。
TR4 越权：学生令牌对三组新端点一律 403。

用本文件专属 db_mode_programs 夹具（非全量 db_mode/db_mode_additive）：高并发 worktree 场景下
本机与多个子智能体共用同一张 TEST_DATABASE_URL 物理库，db_mode 的全量 drop_all 会与并行会话
持续撞车；即使不 drop 只 create_all(checkfirst=True)，只要还是遍历全量 ~250 张表，CREATE INDEX
阶段仍可能撞见另一会话此刻正在 drop 某张不相关表（1146/1050/1051/1684 均实测出现过）。本文件
用例均按自建方案 id 精确断言，天然不依赖"全库清空后精确计数"，故只需保证「培养方案相关表 +
审计流水表」这一小撮表存在，不需要也不 drop 全量 metadata，最大限度降低碰撞面。
"""
from __future__ import annotations

import os
import time

import pytest

BASE = "/api/v1/academic-affairs"

# 本文件用例只触达这几张表（+ 审计流水表），无需全量 metadata create_all。
_PROGRAM_TABLES = [
    "t_aa_program", "t_aa_program_course", "t_aa_program_binding",
    "t_aa_program_graduation_requirement", "t_aa_program_practice_segment",
    "t_affairs_audit_trail",
]


@pytest.fixture()
def db_mode_programs():
    """最小化真库夹具：只 create_all(checkfirst=True) 培养方案相关表 + 审计流水表（真实 MySQL，
    TEST_DATABASE_URL），不做全量 drop_all/create_all，规避与并行 worktree/子智能体共享同一物理
    测试库时的全量 DDL 竞态（1146/1050/1051/1684，root cause 见文件头注释）。MySQL 不可达/建表
    失败直接抛错，不静默回落 sqlite。"""
    from app.core.config import settings
    from app.db.session import reset_state
    test_url = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL
    if test_url.startswith("sqlite"):
        raise RuntimeError("db_mode_programs 仅供 MySQL 使用（拒绝 SQLite 冒充通过）")
    old_enabled, old_url = settings.DB_ENABLED, settings.DATABASE_URL
    settings.DB_ENABLED, settings.DATABASE_URL = True, test_url
    reset_state()
    from app.db.base import metadata
    from app.db.session import get_engine
    engine = get_engine()
    tables = [metadata.tables[t] for t in _PROGRAM_TABLES if t in metadata.tables]

    def _create():
        metadata.create_all(bind=engine, tables=tables, checkfirst=True)

    from sqlalchemy.exc import OperationalError, ProgrammingError
    attempts, base_delay = 15, 2.0
    for i in range(attempts):
        try:
            _create()
            break
        except (OperationalError, ProgrammingError) as e:
            transient = any(code in str(e) for code in ("1050", "1051", "1146", "1684"))
            if not transient or i == attempts - 1:
                raise
            time.sleep(base_delay)

    yield
    settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
    reset_state()


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _new_program(client, hdr, name):
    r = client.post(f"{BASE}/programs", headers=hdr, json={"programName": name})
    assert r.status_code == 200, r.text
    return r.json()["data"]["programId"]


def _publish(client, hdr, pid):
    """DRAFT -> COLLEGE_REVIEW -> ACADEMIC_REVIEW -> PUBLISHED。
    先设总学分 + 补一门等额学分课程使课程学分合计达标（submit_program 校验总学分已设置且课程学分达标，
    历史版本靠"不设 totalCredits 短路跳过校验"的 bug 通过本用例，该 bug 已修复，见 CC-真实交互业务巡检）。"""
    r = client.put(f"{BASE}/programs/{pid}", headers=hdr, json={"totalCredits": 1})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={"courseName": "占位课程", "credit": 1})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "PUBLISHED"


def test_tr1_practice_segment_crud(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "实践环节CRUD方案")
    r = client.post(f"{BASE}/programs/{pid}/practice-segments", headers=hdr, json={
        "segmentName": "顶岗实习", "segmentType": "POST_INTERNSHIP", "openTermNo": 6,
        "weeks": 16, "credit": 8, "orgMode": "DISTRIBUTED", "location": "合作企业", "assessmentMode": "CHECK"})
    assert r.status_code == 200, r.text
    seg = r.json()["data"]
    sid = seg["segmentId"]
    assert seg["weeks"] == 16 and seg["segmentType"] == "POST_INTERNSHIP" and seg["orgMode"] == "DISTRIBUTED"

    items = client.get(f"{BASE}/programs/{pid}/practice-segments", headers=hdr).json()["data"]["items"]
    assert len(items) == 1 and items[0]["segmentName"] == "顶岗实习"

    r = client.put(f"{BASE}/programs/practice-segments/{sid}", headers=hdr, json={"weeks": 18})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["weeks"] == 18

    r = client.delete(f"{BASE}/programs/practice-segments/{sid}", headers=hdr)
    assert r.status_code == 200, r.text
    items = client.get(f"{BASE}/programs/{pid}/practice-segments", headers=hdr).json()["data"]["items"]
    assert items == []


def test_tr1_practice_segment_rejects_bad_weeks_and_non_draft(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "实践环节校验方案")
    # 周数必须 > 0（pydantic gt=0，本仓库全局处理器把 RequestValidationError 统一转 400）
    r = client.post(f"{BASE}/programs/{pid}/practice-segments", headers=hdr, json={"segmentName": "军训", "weeks": 0})
    assert r.status_code == 400, r.text

    # 非编制态方案不可增删改实践环节
    _publish(client, hdr, pid)
    r = client.post(f"{BASE}/programs/{pid}/practice-segments", headers=hdr, json={"segmentName": "军训", "weeks": 2})
    assert r.status_code == 409, r.text


def test_tr2_change_status_freeze_resume_disable(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "方案变更生命周期")
    _publish(client, hdr, pid)

    # 原因<5字拒绝
    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "短"})
    assert r.status_code == 400, r.text

    # 冻结 PUBLISHED -> FROZEN
    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "专业停招临时冻结"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "FROZEN"

    # 恢复（无生效绑定 -> PUBLISHED）
    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "RESUME", "reason": "专业恢复招生启用"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "PUBLISHED"

    # 停用（终态）
    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "DISABLE", "reason": "方案编制有误停用"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "DISABLED"

    # 终态再变更应 409
    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "再次尝试冻结应失败"})
    assert r.status_code == 409, r.text

    # 变更记录可查（含冻结/恢复/停用三条生命周期动作）
    log = client.get(f"{BASE}/programs/{pid}/change-log", headers=hdr).json()["data"]["items"]
    actions = [x["action"] for x in log]
    assert "LIFECYCLE_FREEZE" in actions
    assert "LIFECYCLE_RESUME" in actions
    assert "LIFECYCLE_DISABLE" in actions


def test_tr2_resume_to_enabled_when_active_binding(client, db_mode_programs):
    """已绑定年级的方案冻结后恢复，应回到 ENABLED（而非 PUBLISHED）——按是否存在生效绑定判定。"""
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "方案变更绑定恢复")
    _publish(client, hdr, pid)
    r = client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2027"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "ENABLED"

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "FREEZE", "reason": "临时冻结待复核"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "FROZEN"

    r = client.post(f"{BASE}/programs/{pid}/change-status", headers=hdr, json={"action": "RESUME", "reason": "复核通过恢复启用"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "ENABLED"


def test_tr3_archive_lists_disabled_and_superseded_not_plain_draft(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    # 分支一：DISABLED
    pid1 = _new_program(client, hdr, "归档-已停用方案")
    _publish(client, hdr, pid1)
    r = client.post(f"{BASE}/programs/{pid1}/change-status", headers=hdr, json={"action": "DISABLE", "reason": "停用测试用例数据"})
    assert r.status_code == 200, r.text

    # 分支二：SUPERSEDED（已被新版本取代的历史版本）
    pid2 = _new_program(client, hdr, "归档-历史版本方案")
    _publish(client, hdr, pid2)
    r = client.post(f"{BASE}/programs/{pid2}/new-version", headers=hdr)
    assert r.status_code == 200, r.text
    new_pid = r.json()["data"]["programId"]

    # 对照组：普通 DRAFT，两条归档原因都不成立，不应出现
    pid3 = _new_program(client, hdr, "归档-普通草稿不应出现")

    items = client.get(f"{BASE}/program-archive", headers=hdr, params={"pageSize": 200}).json()["data"]["items"]
    by_id = {x["programId"]: x for x in items}
    assert pid1 in by_id and "DISABLED" in by_id[pid1]["archiveReasons"]
    assert pid2 in by_id and "SUPERSEDED" in by_id[pid2]["archiveReasons"]
    assert by_id[pid2]["supersededByProgramId"] == new_pid
    assert pid3 not in by_id


def test_submit_rejects_when_total_credits_unset_or_course_sum_short(client, db_mode_programs):
    """回归：CC-真实交互业务巡检发现 submit_program 曾用 `if p.total_credits and ...` 短路校验，
    毕业总学分未设置时空方案(0 门课程)也能一路提交到学院审→发布，成为约束学生毕业的生效方案。"""
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "总学分未设置不可提交")
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 400, r.text
    assert "毕业总学分尚未设置" in r.text

    # 设置总学分但课程学分合计未达标，仍应拒绝
    r = client.put(f"{BASE}/programs/{pid}", headers=hdr, json={"totalCredits": 10})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert r.status_code == 400, r.text
    assert "未达毕业总学分" in r.text


def test_tr4_student_403_on_new_endpoints(client, db_mode_programs):
    hdr = _hdr(client, "school_admin01")
    pid = _new_program(client, hdr, "越权测试方案")
    stu = _hdr(client, "student01")
    assert client.get(f"{BASE}/programs/{pid}/practice-segments", headers=stu).status_code == 403
    assert client.post(f"{BASE}/programs/{pid}/practice-segments", headers=stu,
                       json={"segmentName": "X", "weeks": 1}).status_code == 403
    assert client.post(f"{BASE}/programs/{pid}/change-status", headers=stu,
                       json={"action": "FREEZE", "reason": "越权尝试冻结"}).status_code == 403
    assert client.get(f"{BASE}/programs/{pid}/change-log", headers=stu).status_code == 403
    assert client.get(f"{BASE}/program-archive", headers=stu).status_code == 403
