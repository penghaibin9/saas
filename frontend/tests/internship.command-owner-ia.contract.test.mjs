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

  assert.equal(visible.children.length, 9)
  assert.equal(visible.children.flatMap((workspace) => workspace.children).length, 29)

  const expectedOwners = {
    'in-command-screen': ['实习中心大屏'],
    'in-workbench': ['待办与进度'],
    'in-batch-rules': ['批次管理', '学生名单', '资格认定'],
    'in-enterprise-position': ['企业库', '岗位库', '企业准入'],
    'in-match-assign': ['岗位确认', '申请审核', '岗位匹配', '三方协议', '保险核验', '上岗核验'],
    'in-attendance-leave': ['考勤与异常', '请假与返岗', '报告与任务', '指导与巡访'],
    'in-risk': ['风险预警', '风险处置', '调岗退岗', '事故与应急'],
    'in-eval-score': ['企业评价', '学生与教师评价', '综合成绩', '成绩申诉'],
    'in-employment-archive-stats': ['材料归档', '实习统计', '就业衔接']
  }

  for (const [workspaceKey, labels] of Object.entries(expectedOwners)) {
    assert.deepEqual(byWorkspace(visible, workspaceKey).children.map((leaf) => leaf.label), labels)
  }

  const compatibilityLabels = [
    '招聘与邀请', '导师分配', '分配记录', '异常核验', '计划任务', '指导计划',
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
