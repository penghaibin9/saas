import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { WORKSPACE_CENTERS, availableCenters, flattenPages, normalizePreferences, pageForRoute, searchPages } from '../src/platform/workspaceNavigation.js'
import { normalizeTheme, themeTokens, WORKSPACE_THEMES } from '../src/platform/workspaceTheme.js'

const allPages = flattenPages(WORKSPACE_CENTERS)
const fullConfig = { enabled: true, modules: Object.fromEntries(WORKSPACE_CENTERS.flatMap(center => center.groups.map(group => [group.module, true]))) }
test('学生菜单全部指向当前已登记路由，不带教师管理入口；三级名称保留完整称呼', async () => {
  const [router, academic] = await Promise.all(['index.js', 'academicRoutes.js'].map(file => readFile(new URL(`../src/router/${file}`, import.meta.url), 'utf8')))
  const fixed = [...router.matchAll(/path: '([^':]*)'/g)].map(match => '/' + match[1].replace(/^\//, ''))
  const academicPaths = [...academic.matchAll(/(?:path: |academicSection\(|academicReadOnly\()'([^':]*)'/g)].map(match => '/academic/' + match[1])
  const registered = new Set([...fixed, ...academicPaths, '/academic'])
  assert.equal(new Set(allPages.map(item => item.id)).size, allPages.length)
  for (const item of allPages) {
    assert.ok(registered.has(item.to.split('?')[0]), `${item.title} 缺少真实路由`)
    assert.doesNotMatch(item.to, /\/admin|\/teacher|\/platform/)
    assert.ok([...item.short].length <= 2)
    assert.match(item.title, /[\u4e00-\u9fff]/)
  }
})
test('未开通业务不会进入菜单、跨模块搜索、恢复页签或快捷栏', () => {
  const pages = flattenPages(availableCenters({ enabled: true, modules: { profile: true } }))
  assert.deepEqual(pages.map(item => item.id), ['home', 'hall', 'profile', 'departure'])
  assert.equal(searchPages(pages, '请假', 'student').length, 0)
  const saved = normalizePreferences({ tabs: ['home', 'leave', 'grades'], shortcuts: ['leave', 'profile', 'grades'] }, pages)
  assert.deepEqual(saved.tabs, ['home'])
  assert.deepEqual(saved.shortcuts, ['profile'])
  assert.equal(availableCenters({ enabled: false, modules: fullConfig.modules }).length, 1)
})
test('请假、宿舍、奖助可在同一路由切换并保持菜单定位；无效分类安全回落', () => {
  for (const tab of ['leave', 'dorm', 'aid', 'funding', 'activity', 'talk', 'psy', 'discipline']) {
    assert.equal(pageForRoute({ path: '/campus-service', query: { tab, studentId: 'ignored' } }, allPages).id, tab)
  }
  assert.equal(pageForRoute({ path: '/campus-service', query: { tab: 'teacher-internal' } }, allPages).id, 'leave')
  assert.equal(pageForRoute({ path: '/internship/selection/company/123' }, allPages), null)
})
test('外部存储值只恢复登记的菜单和有限的显示偏好，不恢复表单、令牌或动态详情', () => {
  const input = { second: 'unknown', third: 'full', tabs: ['leave', 'leave', '/profile?studentId=3'], shortcuts: ['profile', 'leave'], appearance: { profile: { label: '我的资料'.repeat(10), color: 'url(bad)' } }, theme: { secret: 'never-store' }, token: 'never-store', form: { reason: 'never-store' }, extra: 'never-store' }
  const actual = normalizePreferences(input, allPages)
  assert.equal(actual.second, 'compact')
  assert.equal(actual.third, 'full')
  assert.deepEqual(actual.tabs, ['leave'])
  assert.ok(actual.appearance.profile.label.length <= 12)
  assert.equal(actual.appearance.profile.color, 'blue')
  assert.doesNotMatch(JSON.stringify(actual), /never-store|studentId|url\(/)
  assert.doesNotThrow(() => normalizePreferences({ tabs: {}, shortcuts: 1, appearance: null }, allPages))
  assert.equal(normalizePreferences({ shortcuts: [] }, allPages).shortcuts.length, 0)
  assert.equal(normalizePreferences({ shortcuts: allPages.map(item => item.id) }, allPages).shortcuts.length, 8)
})
test('搜索优先准确名称；跨中心结果带完整所属路径', () => {
  assert.equal(searchPages(allPages, '我的成绩', 'student')[0].id, 'grades')
  assert.equal(searchPages(allPages, ' 材料 ', 'student')[0].centerId, 'student')
  assert.ok(searchPages(allPages, '教务', 'student').every(item => item.trail.includes('教务')))
})
function contrast(a, b) {
  const luminance = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4).reduce((n, v, i) => n + v * [0.2126, 0.7152, 0.0722][i], 0)
  const x = luminance(a), y = luminance(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}
test('四套主题保持既有业务变量，并保证正文、辅助文字和主题按钮文字对比', () => {
  assert.deepEqual(WORKSPACE_THEMES.map(item => item.key), ['dark', 'blue', 'sage', 'plum'])
  for (const theme of WORKSPACE_THEMES) {
    const tokens = themeTokens(theme.key)
    for (const key of ['--bg', '--surface', '--field-bg', '--pri', '--pri-on', '--t1', '--t3', '--line']) assert.ok(tokens[key])
    for (const surface of [theme.bg, theme.surface, theme.header, theme.soft]) {
      assert.ok(contrast(theme.ink, surface) >= 4.5, `${theme.label} 正文对比`)
      assert.ok(contrast(theme.muted, surface) >= 4.5, `${theme.label} 辅助文字对比`)
    }
    assert.ok(contrast(theme.on, theme.accent) >= 4.5, `${theme.label} 按钮对比`)
  }
  assert.equal(normalizeTheme('green'), 'sage')
  assert.equal(normalizeTheme('purple'), 'plum')
  assert.equal(normalizeTheme('unknown'), 'blue')
})
test('首页待办先于成长航线；学工分类变化保持真实加载链，保留深链白名单', async () => {
  const home = await readFile(new URL('../src/views/home/HomeView.vue', import.meta.url), 'utf8')
  assert.ok(home.indexOf('class="home-grid"') < home.indexOf('class="home-card home-journey"'))
  assert.doesNotMatch(home.split('<script')[0], /MY STUDENT JOURNEY|GPA/)
  const affairs = await readFile(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8')
  assert.match(affairs, /watch\(\(\) => route\.query\.tab/)
  assert.match(affairs, /tabs\.some\(item => item\.key === key\)/)
  assert.match(affairs, /watch\(tab, \(key\) => \{ loadTab\(key, \{ force: key === 'dorm' \}\) \}, \{ immediate: true \}\)/)
})
