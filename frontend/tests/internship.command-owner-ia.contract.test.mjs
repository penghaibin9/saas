import assert from 'node:assert/strict'
import test from 'node:test'

import { NAV_PLAN, getVisibleNavPlan } from '../src/config/navPlan.js'

function internshipGroup(plan) {
  return plan.find((group) => group.key === 'internship')
}

function byWorkspace(group, key) {
  return group.children.find((workspace) => workspace.key === key)
}

test('W4 exposes one bounded command-owner IA and keeps compatibility routes hidden', () => {
  const visible = internshipGroup(getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['*'],
    ctxKey: 'internship-v8-w4-owner'
  }))
  const all = internshipGroup(NAV_PLAN)

  assert.equal(visible.children.length, 11)
  assert.equal(visible.children.flatMap((workspace) => workspace.children).length, 33)

  const expectedOwners = {
    'in-match-assign': ['选岗 / 匹配工作台', '调岗退岗', '分配记录'],
    'in-apply-agreement': ['实习申请审核', '三方协议工作台', '自主实习申请'],
    'in-attendance-leave': ['考勤工作台', '异常核验', '请假审批 / 台账'],
    'in-weekly-task': ['计划任务', '过程报告批阅'],
    'in-guidance-visit': ['指导巡访工作台', '指导计划 / 不足预警'],
    'in-risk': ['风险工作台', '风险处置', '上岗 / 监管合规', '事故与应急'],
    'in-eval-score': ['评价工作台', '成绩工作台', '成绩申诉'],
    'in-employment-archive-stats': ['材料与归档', '实习统计', '就业衔接']
  }

  for (const [workspaceKey, labels] of Object.entries(expectedOwners)) {
    assert.deepEqual(byWorkspace(visible, workspaceKey).children.map((leaf) => leaf.label), labels)
  }

  const compatibilityLabels = [
    '手动匹配', '批量匹配', '匹配冲突', '岗位申请', '审核台账',
    '补卡申请台账', '补卡审批', '请假台账', '已批准请假', '超期未归',
    '日报台账', '周报台账', '月报台账', '周报退回', '报告问题',
    '企业沟通', '巡访计划', '巡访记录', '巡访问题', '整改跟进',
    '风险提醒', '未落实岗位', '长期未打卡', '周报逾期', '离岗异常',
    '成绩审核', '成绩发布', '成绩复核', '实习档案包'
  ]
  const allLeaves = all.children.flatMap((workspace) => workspace.children)
  const visibleLabels = new Set(visible.children.flatMap((workspace) => workspace.children).map((leaf) => leaf.label))

  for (const label of compatibilityLabels) {
    const leaf = allLeaves.find((candidate) => candidate.label === label)
    assert.ok(leaf?.path, `${label} must keep its historical deep link`)
    assert.equal(leaf.hidden, true, `${label} must be a hidden compatibility entry`)
    assert.equal(visibleLabels.has(label), false, `${label} must not compete in the daily sidebar`)
  }
})

test('W4 high-exposure entries never expose detail or action-only leaves', () => {
  const visible = internshipGroup(getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['*'],
    ctxKey: 'internship-v8-w4-entry-types'
  }))
  const leaves = visible.children.flatMap((workspace) => workspace.children)
  assert.equal(leaves.some((leaf) => ['DETAIL', 'ACTION', 'CAPABILITY_ONLY'].includes(leaf.entryType)), false)
})
