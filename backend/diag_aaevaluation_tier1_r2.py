"""教学评价 Tier1 R2（学生评教PC查看/教师自评/同行评价/督导评价/评价统计/评价归档）
—— 独立 SQLite 自测脚本（不连 MySQL，不跑 pytest 默认 MySQL-only conftest）。

用法：VENV_PYTHON diag_aaevaluation_tier1_r2.py
仅用于本轮子智能体自测证据留存，非正式 pytest 用例（正式回归用例见
backend/tests/test_aa_evaluation.py，由总控后续统一在 MySQL 环境执行）。
"""
from __future__ import annotations

import os
import sys

os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "true"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./diag_aaevaluation_tier1_r2.db"
os.environ["TEST_DATABASE_URL"] = "sqlite+pysqlite:///./diag_aaevaluation_tier1_r2.db"
os.environ["MOCK_LOGIN_ENABLED"] = "true"

if os.path.exists("./diag_aaevaluation_tier1_r2.db"):
    os.remove("./diag_aaevaluation_tier1_r2.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

from app.db.base import metadata  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402

engine = get_engine()
metadata.create_all(bind=engine)
print("[1] metadata.create_all OK（复用既有 t_aa_evaluation_* 5 表，本轮不新建表）")

TID = 1000000000000000001

from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major  # noqa: E402

db = get_sessionmaker()()
term = AaTerm(tenant_id=TID, year_code="2025-2026", term_no=1, term_name="2025秋", is_current=True, status="PUBLISHED")
db.add(term); db.flush()
college = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
db.add(college); db.flush()
major = Major(tenant_id=TID, college_id=college.id, major_name="软件技术", status="ACTIVE")
db.add(major); db.flush()
tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2025秋教学任务", college_id=college.id, status="ACTIVE")
db.add(tb); db.flush()
tt = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=1, course_name="高等数学",
                    teacher_key="counselor01", teacher_name="王莉")
db.add(tt); db.flush()
TASK_ID = tt.id
db.commit(); db.close()
print(f"[2] 种子数据 OK（教学任务 id={TASK_ID}，授课教师=counselor01）")


def login(name):
    r = client.post("/api/v1/auth/mock-login", json={"loginName": name, "password": "any"})
    assert r.status_code == 200, f"{name} 登录失败 {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['data']['accessToken']}"}


ADMIN = login("school_admin01")
SELF_TEACHER = login("counselor01")   # 授课教师本人（自评）
PEER = login("academic01")            # 同行评价人
SUPERVISOR = login("teacher01")       # 督导评价人（本项目未建专属督导角色，按 evaluator_key 匹配核验，见 D-07）
WRONG = login("employment01")         # 越权用户

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'OK ' if ok else 'FAIL'} {name} {'' if ok else detail}")


BASE = "/api/v1/academic-affairs"

# ═══════════ 建批次 → 生成 STUDENT + SELF + PEER + SUPERVISOR 四类任务 ═══════════
bid = client.post(f"{BASE}/evaluation/batches", headers=ADMIN,
                  json={"batchName": "2025秋评教R2", "termId": str(term.id)}).json()["data"]["batchId"]
check("建批次", bool(bid))

gen_stu = client.post(f"{BASE}/evaluation/batches/{bid}/tasks", headers=ADMIN,
                      json={"teachingTaskIds": [str(TASK_ID)]}).json()
check("生成STUDENT任务", gen_stu["data"]["taskCount"] == 1, str(gen_stu))

gen_self = client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=ADMIN,
                       json={"evaluatorType": "SELF", "assignments": [{"teachingTaskId": str(TASK_ID)}]}).json()
check("生成SELF任务(自动=授课教师)", gen_self["data"]["taskCount"] == 1, str(gen_self))

gen_peer = client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=ADMIN,
                       json={"evaluatorType": "PEER", "assignments": [{"teachingTaskId": str(TASK_ID), "evaluatorKey": "academic01"}]}).json()
check("生成PEER任务(指定评价人)", gen_peer["data"]["taskCount"] == 1, str(gen_peer))

gen_peer_missing_key = client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=ADMIN,
                                   json={"evaluatorType": "PEER", "assignments": [{"teachingTaskId": str(TASK_ID)}]})
check("PEER缺evaluatorKey应400", gen_peer_missing_key.status_code == 400, str(gen_peer_missing_key.status_code))

gen_sup = client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=ADMIN,
                      json={"evaluatorType": "SUPERVISOR", "assignments": [{"teachingTaskId": str(TASK_ID), "evaluatorKey": "teacher01"}]}).json()
check("生成SUPERVISOR任务(指定评价人)", gen_sup["data"]["taskCount"] == 1, str(gen_sup))

# 越权：非管理员不可生成任务
gen_forbidden = client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=SELF_TEACHER,
                            json={"evaluatorType": "SELF", "assignments": [{"teachingTaskId": str(TASK_ID)}]})
check("普通教师生成任务应403", gen_forbidden.status_code == 403, str(gen_forbidden.status_code))

tasks = client.get(f"{BASE}/evaluation/batches/{bid}/tasks", headers=ADMIN).json()["data"]["items"]
by_type = {t["evaluatorType"]: t["taskId"] for t in tasks}
check("四类任务均已生成", set(by_type.keys()) == {"STUDENT", "SELF", "PEER", "SUPERVISOR"}, str(by_type))

# ═══════════ 发布 → 开放 ═══════════
client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=ADMIN)
op = client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=ADMIN).json()
check("发布+开放", op["data"]["status"] == "OPEN", str(op))

# ═══════════ my-role-tasks：各自只看到分配给自己的任务 ═══════════
my_self = client.get(f"{BASE}/evaluation/my-role-tasks", headers=SELF_TEACHER, params={"evaluatorType": "SELF"}).json()["data"]["items"]
check("自评本人my-role-tasks可见1条", len(my_self) == 1 and my_self[0]["taskId"] == by_type["SELF"], str(my_self))

my_peer_wrong = client.get(f"{BASE}/evaluation/my-role-tasks", headers=SUPERVISOR, params={"evaluatorType": "PEER"}).json()["data"]["items"]
check("非同行评价人my-role-tasks应为空", len(my_peer_wrong) == 0, str(my_peer_wrong))

# ═══════════ 越权提交：非指定评价人 → 403 ═══════════
wrong_submit = client.post(f"{BASE}/evaluation/submit", headers=WRONG,
                           json={"taskId": by_type["SELF"], "objectiveScore": 90, "comment": "冒充提交"})
check("非指定评价人提交SELF任务应403", wrong_submit.status_code == 403, str(wrong_submit.status_code))

wrong_peer_submit = client.post(f"{BASE}/evaluation/submit", headers=SELF_TEACHER,
                                json={"taskId": by_type["PEER"], "objectiveScore": 88, "comment": "冒充同行评价"})
check("授课教师本人提交PEER任务(非本人)应403", wrong_peer_submit.status_code == 403, str(wrong_peer_submit.status_code))

# ═══════════ 正向提交：本人提交成功 ═══════════
ok_self = client.post(f"{BASE}/evaluation/submit", headers=SELF_TEACHER,
                      json={"taskId": by_type["SELF"], "objectiveScore": 92, "comment": "本学期教学态度端正，持续改进教法"})
check("授课教师本人提交自评成功", ok_self.json().get("code") == 0, str(ok_self.json()))

ok_peer = client.post(f"{BASE}/evaluation/submit", headers=PEER,
                      json={"taskId": by_type["PEER"], "objectiveScore": 85, "comment": "同行听课：课堂互动充分"})
check("同行评价人提交成功", ok_peer.json().get("code") == 0, str(ok_peer.json()))

ok_sup = client.post(f"{BASE}/evaluation/submit", headers=SUPERVISOR,
                     json={"taskId": by_type["SUPERVISOR"], "objectiveScore": 80, "comment": "督导听课：教学规范，建议加强互动"})
check("督导评价人提交成功", ok_sup.json().get("code") == 0, str(ok_sup.json()))

# ═══════════ 重复提交 → 409（非STUDENT类幂等拦截） ═══════════
dup_self = client.post(f"{BASE}/evaluation/submit", headers=SELF_TEACHER,
                       json={"taskId": by_type["SELF"], "objectiveScore": 60, "comment": "重复提交"})
check("自评重复提交应409", dup_self.status_code == 409, str(dup_self.status_code))

# ═══════════ 学生评教（STUDENT类，PC查看入口验证；不改既有匿名多次提交语义） ═══════════
from app.core.security import create_access_token  # noqa: E402


def stu_token(no):
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{no}", "realName": "学生", "studentNo": no, "userType": "STUDENT",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


for sn, sc in (("R2S01", 95), ("R2S02", 85)):
    r = client.post(f"{BASE}/evaluation/submit", headers=stu_token(sn),
                    json={"taskId": by_type["STUDENT"], "objectiveScore": sc, "comment": "很好"})
    check(f"学生{sn}匿名提交成功", r.json().get("code") == 0, str(r.json()))

se_view = client.get(f"{BASE}/evaluation/batches/{bid}/tasks", headers=ADMIN, params={"evaluatorType": "STUDENT"}).json()["data"]["items"]
check("学生评教PC查看：任务已评数=2", se_view and se_view[0]["submittedCount"] == 2, str(se_view))

# ═══════════ 评价统计：participation 按类型 ═══════════
st = client.get(f"{BASE}/evaluation/batches/{bid}/stats", headers=ADMIN).json()["data"]
part = st.get("participation", {})
check("统计participation含4类", set(part.keys()) == {"STUDENT", "SELF", "PEER", "SUPERVISOR"}, str(part))
check("SELF参评率100%", part.get("SELF", {}).get("rate") == 100.0, str(part.get("SELF")))
check("STUDENT应评1已评1(整门课算1个task)", part.get("STUDENT") == {"total": 1, "submitted": 1, "rate": 100.0}, str(part.get("STUDENT")))

# ═══════════ 关闭核算 → 发布结果 → 归档 ═══════════
close = client.post(f"{BASE}/evaluation/batches/{bid}/close-score", headers=ADMIN).json()
check("关闭核算", close["data"]["status"] == "RESULT_READY", str(close))
client.post(f"{BASE}/evaluation/batches/{bid}/publish-results", headers=ADMIN)
arch = client.post(f"{BASE}/evaluation/batches/{bid}/archive", headers=ADMIN).json()
check("归档", arch["data"]["status"] == "ARCHIVED", str(arch))

# ═══════════ 评价归档：列表（后端 paginate 原始键为 items；前端 callList 再映射为 list） ═══════════
arch_list = client.get(f"{BASE}/evaluation/batches", headers=ADMIN, params={"status": "ARCHIVED"}).json()["data"]["items"]
check("归档批次列表可查到本批次", any(b["batchId"] == bid for b in arch_list), str(arch_list))

# ═══════════ 导出（results/stats）xlsx ═══════════
exp_results = client.post(f"{BASE}/evaluation/batches/{bid}/export", headers=ADMIN,
                          json={"domain": "results", "purpose": "R2自测导出核对"})
check("导出评价结果200且为xlsx", exp_results.status_code == 200 and len(exp_results.content) > 100, str(exp_results.status_code))

exp_stats = client.post(f"{BASE}/evaluation/batches/{bid}/export", headers=ADMIN,
                        json={"domain": "stats", "purpose": "R2自测导出核对"})
check("导出参评统计200且为xlsx", exp_stats.status_code == 200 and len(exp_stats.content) > 100, str(exp_stats.status_code))

exp_short_purpose = client.post(f"{BASE}/evaluation/batches/{bid}/export", headers=ADMIN,
                                json={"domain": "results", "purpose": "短"})
check("导出用途过短应400", exp_short_purpose.status_code == 400, str(exp_short_purpose.status_code))

exp_bad_domain = client.post(f"{BASE}/evaluation/batches/{bid}/export", headers=ADMIN,
                             json={"domain": "bogus", "purpose": "非法domain测试用途"})
check("非法导出domain应400", exp_bad_domain.status_code == 400, str(exp_bad_domain.status_code))

# ═══════════ 汇总 ═══════════
fail_count = sum(1 for _, ok, _ in results if not ok)
print(f"\n=== 汇总：{len(results)} 项检查，{len(results) - fail_count} 通过，{fail_count} 失败 ===")
if fail_count:
    sys.exit(1)
print("ALL PASS")
