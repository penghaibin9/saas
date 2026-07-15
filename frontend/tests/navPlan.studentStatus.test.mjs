/**
 * 教务中心·学籍管理 Tier1 R3 侧栏高亮回归（2026-07-16）。
 * 只覆盖 navPlan.js 纯函数（无 @ 别名依赖），用 Node 内置 test runner：`node --test tests/`。
 * 验证新增 8 个三级菜单叶子（休学/复学/退学/转专业学生、保留学籍、学籍信息更正、学籍统计、学籍归档）
 * 各自命中唯一 leafKey，不与「学籍名册」「教务统计·学籍统计」「教务归档」等既有叶子混淆
 * （防止「同 path 多叶子全部连成一片高亮」，见 BasePortalLayout.vue leafKey 唯一性规则）。
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { findActiveInPlan } from '../src/config/navPlan.js'

function leafLabel(navRef) {
  const { leafKey } = findActiveInPlan(navRef.split('?')[0], navRef)
  return leafKey
}

test('学籍管理：休学/退学/保留学籍按 roster?status= 深链命中各自叶子，不与「学籍名册」混淆', () => {
  assert.equal(leafLabel('/admin/academic-affairs/roster?status=SUSPENDED'), '休学学生')
  assert.equal(leafLabel('/admin/academic-affairs/roster?status=WITHDRAWN'), '退学学生')
  assert.equal(leafLabel('/admin/academic-affairs/roster?status=RETAINED'), '保留学籍')
  // 裸路径 /admin/academic-affairs/roster：该二级模块自身注册 path 与「学籍名册」叶子 path 相同，
  // FLAT_NAV_INDEX 中模块行先于叶子行插入、同分时旧逻辑保留模块行 → leafKey 为空（不高亮具体叶子，
  // 仅二级模块本身高亮）。这是 mod()/I() 复用同一 path 时的既有平台行为（aa-stats 等多个模块同样如此），
  // 不属于本次新增叶子引入的问题，此处只验证不会被我的新叶子错误抢占。
  const bare = findActiveInPlan('/admin/academic-affairs/roster', '/admin/academic-affairs/roster')
  assert.equal(bare.modKey, 'aa-student-status')
  assert.equal(bare.leafKey, '')
})

test('学籍管理：复学/转专业学生命中独立路由叶子', () => {
  assert.equal(leafLabel('/admin/academic-affairs/roster/resumed-students'), '复学学生')
  assert.equal(leafLabel('/admin/academic-affairs/roster/transferred-major-students'), '转专业学生')
})

test('学籍管理：学籍信息更正命中独立叶子', () => {
  assert.equal(leafLabel('/admin/academic-affairs/roster/corrections'), '学籍信息更正')
})

test('学籍管理：学籍统计深链不与「教务统计」模块下的同名叶子冲突', () => {
  // navRefMatches 比较候选 query 用原始字符串（不重新排序）：候选串必须已按 key 字母序书写
  // （navPlan.js 内 scope < tab），此处按真实点击该叶子后 $route.fullPath 的形态传入（同样已排序）。
  assert.equal(leafLabel('/admin/academic-affairs/stats?scope=roster&tab=statusChange'), '学籍统计')
  // 教务统计模块自己的「学籍统计」叶子（无 scope=roster）应命中它自己，而不是学籍管理这条
  assert.equal(leafLabel('/admin/academic-affairs/stats?tab=statusChange'), '学籍统计')
  const a = findActiveInPlan('/admin/academic-affairs/stats',
    '/admin/academic-affairs/stats?scope=roster&tab=statusChange')
  const b = findActiveInPlan('/admin/academic-affairs/stats', '/admin/academic-affairs/stats?tab=statusChange')
  assert.notEqual(a.modKey, b.modKey, '两条「学籍统计」应分属不同二级模块（aa-student-status vs aa-stats）')
})

test('学籍管理：学籍归档深链不与「教务归档」模块下的批次页混淆', () => {
  const roster = findActiveInPlan('/admin/academic-affairs/archive',
    '/admin/academic-affairs/archive?entry=studentStatus')
  const archive = findActiveInPlan('/admin/academic-affairs/archive', '/admin/academic-affairs/archive')
  assert.equal(roster.leafKey, '学籍归档')
  assert.notEqual(roster.modKey, archive.modKey, '「学籍归档」与「归档批次...」应分属不同二级模块')
})
