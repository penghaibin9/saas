#!/usr/bin/env bash
set -euo pipefail

# 教务“虚拟学校完整学期”真实 MySQL 演练门禁。
# 这不是把 11 个孤立测试冒充同一条学生数据链：
# - 本脚本负责逐关验证真实写端点、状态机、事务与下游投影能在 MySQL 上执行；
# - R11 真实学校完整学期试点负责最终同租户/同学期事实连续性与证据哈希冻结。

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR/backend"

DB_URL="${TEST_DATABASE_URL:-${DATABASE_URL:-}}"
if [[ -z "$DB_URL" ]]; then
  echo "[academic-semester-rehearsal] TEST_DATABASE_URL/DATABASE_URL 未设置" >&2
  exit 2
fi
if [[ "$DB_URL" != mysql* ]]; then
  echo "[academic-semester-rehearsal] 只接受 MySQL，拒绝 SQLite 冒充演练通过: $DB_URL" >&2
  exit 2
fi
if [[ "${DB_ENABLED:-}" != "true" && "${DB_ENABLED:-}" != "1" ]]; then
  echo "[academic-semester-rehearsal] DB_ENABLED 必须为 true" >&2
  exit 2
fi

run_stage() {
  local code="$1"
  local title="$2"
  shift 2
  echo
  echo "================================================================"
  echo "[academic-semester-rehearsal] ${code} | ${title}"
  echo "================================================================"
  python -m pytest -q --maxfail=1 -p no:warnings "$@"
}

# 先锁静态入口与本轮已确认的移动成绩断点，避免业务演练跑在错误公开 Service 上。
run_stage "S00" "公开 Service 装配与教师微信成绩静态合同" \
  tests/test_aa_service_entrypoint_integrity.py \
  tests/test_aa_mobile_grade_entry_v2.py::test_teacher_wechat_page_keeps_grades_memory_only_and_uses_server_save

# 11 环核心写链。每一环失败立即停止，禁止跳关或把失败收进白名单。
run_stage "S01" "建学期/发布校历" \
  tests/test_aa_calendar_period.py::test_r6_publish_calendar_gate_and_lock

run_stage "S02" "培养方案发布/绑定/生命周期" \
  tests/test_aa_program_tier1_r3.py::test_tr2_resume_to_enabled_when_active_binding

run_stage "S03" "教学任务生成/分配/教师确认/两级审核" \
  tests/test_aa_teaching_task.py::test_tt1_full_chain

run_stage "S04" "排课预发布/正式发布/通知" \
  tests/test_aa_schedule.py::test_s6_publish_notifies

run_stage "S05" "选课发布/开选/选退/截止/锁定/归档" \
  tests/test_aa_selection.py::test_s1_full_lifecycle

run_stage "S06" "课堂考勤建场/名单/点名/提交/提交后锁定" \
  tests/test_mobile_attendance.py::test_attendance_full_flow

run_stage "S07" "考务完整生命周期" \
  tests/test_aa_exam.py::test_e1_full_lifecycle

run_stage "S08" "成绩录入/审核/发布/正式成绩投影" \
  tests/test_aa_grade.py::test_g1_compose_publish_project

run_stage "S09" "挂科→补考→学院审→发布有效成绩" \
  tests/test_aa_makeup.py::test_m1_makeup_full_flow

run_stage "S10" "毕业资格生成/预审" \
  tests/test_aa_graduation.py::test_gr1_precheck_passed

# ar1 用真实十三域检查；ar2 验证不可逆归档/Manifest，但其 endpoint 工作流测试会
# monkeypatch “实时 Manifest 复核已通过”。真正语义完整性仍由 archive semantic gates + R11 负责。
run_stage "S11" "归档十三域预检/正式归档不可逆/Manifest" \
  tests/test_aa_archive.py::test_ar1_batch_and_check \
  tests/test_aa_archive.py::test_ar2_confirm_archive_creates_manifest_and_freezes_term \
  tests/test_aa_archive_semantic_gates.py

# R11 不是数据生成器，只读真实事实并冻结证据；这里先保证其控制台合同本身不回退。
run_stage "S12" "R11 同租户同学期事实核验控制台合同" \
  tests/test_aa_semester_pilot_r11.py

echo
echo "[academic-semester-rehearsal] PASS: MySQL 核心写链 11 环 + R11 控制台合同全部通过"
