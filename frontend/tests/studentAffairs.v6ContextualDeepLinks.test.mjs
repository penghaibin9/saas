import assert from 'node:assert/strict'
import test from 'node:test'
import { getVisibleNavPlan } from '../src/config/navPlan.js'
import {
  countContextualWorkspaceDeepLinks,
  projectStudentAffairsWorkspaceDeepLinks
} from '../src/config/studentAffairsWorkspaceDeepLinks.js'

function project(patterns = ['*']) {
  const group = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: patterns,
    ctxKey: `deep-links-${patterns.join(',')}`
  }).find((item) => item.key === 'student-affairs')
  return projectStudentAffairsWorkspaceDeepLinks(group, patterns)
}

function workspace(group, key) {
  const result = group.children.find((item) => item.key === key)
  assert.ok(result, key)
  return result
}

test('contextual projection exposes real D links without exposing H details or compat routes', () => {
  const group = project()
  assert.ok(countContextualWorkspaceDeepLinks(group) >= 14)
  const contextual = group.children.flatMap((item) => item.children).filter((leaf) => leaf.contextualDeepLink)
  assert.ok(contextual.every((leaf) => leaf.searchable && !leaf.hidden && leaf.path))
  assert.ok(contextual.every((leaf) => !['DETAIL', 'COMPAT'].includes(leaf.entryType)))
  assert.equal(contextual.some((leaf) => leaf.label === '学生360详情'), false)
  assert.equal(contextual.some((leaf) => leaf.label === '旧绿色通道入口'), false)
})

test('student, aid and orientation workspaces gain their existing low-frequency real pages', () => {
  const group = project()
  assert.deepEqual(
    workspace(group, 'sa-profile').children.filter((leaf) => leaf.contextualDeepLink).map((leaf) => leaf.label),
    ['学生补录']
  )
  assert.deepEqual(
    workspace(group, 'sa-aid').children.filter((leaf) => leaf.contextualDeepLink).map((leaf) => leaf.label),
    ['认定批次', '困难认定异议', '困难认定统计', '资助批次', '资助公示申诉', '助学金管理', '资助统计']
  )
  assert.deepEqual(
    workspace(group, 'sa-orientation').children.filter((leaf) => leaf.contextualDeepLink).map((leaf) => leaf.label),
    ['报到流程配置', '现场报到点', '新生数据', '新生信息核验', '缴费与绿色通道', '材料审核', '宿舍预分配', '宿舍入住', '未报到学生', '迎新通知', '迎新归档']
  )
})

test('deep-link permissions remain fail-closed and never modify the cached visible tree', () => {
  const aidOnly = project(['studentAffairs.aid.view'])
  const aid = workspace(aidOnly, 'sa-aid')
  const labels = aid.children.map((leaf) => leaf.label)
  assert.ok(labels.includes('认定批次'))
  assert.ok(labels.includes('困难认定异议'))
  assert.equal(labels.includes('资助批次'), false)
  assert.equal(labels.includes('困难认定统计'), false)

  const curated = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['*'],
    ctxKey: 'deep-links-cache-integrity'
  }).find((item) => item.key === 'student-affairs')
  assert.equal(curated.children.flatMap((item) => item.children).some((leaf) => leaf.contextualDeepLink), false)
})

test('contextual entries retain business-stage grouping and explicit type badges', () => {
  const group = project()
  const orientation = workspace(group, 'sa-orientation')
  const payment = orientation.children.find((leaf) => leaf.label === '缴费与绿色通道')
  const archive = orientation.children.find((leaf) => leaf.label === '迎新归档')
  assert.equal(payment.sectionKey, 'stage-4')
  assert.equal(payment.badge, '队列')
  assert.equal(archive.sectionKey, 'stage-6')
  assert.equal(archive.badge, '归档')
})
