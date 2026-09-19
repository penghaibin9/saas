import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const homePage = read('src/pages/student/home/index.vue')
const shortcuts = read('src/pages/student/home/HomeQuickServices.vue')
const agendaPage = read('src/pages/student/agenda/index.vue')
const adapter = read('src/services/realApi.js')
const homeAdapter = adapter.match(/export async function studentHomeReal\(\)[\s\S]*?\n\}/)[0]

// ── S3 首页只消费 canonical server truth ──

test('S3 首页指标不再硬编码 null，真值缺失时显示 —', () => {
  assert.doesNotMatch(homeAdapter, /progress: null/)
  assert.doesNotMatch(homeAdapter, /creditRate: null\b/)
  assert.match(homeAdapter, /summary\.stageProgress/)
  assert.match(homeAdapter, /summary\.creditRate/)
  // 真值缺失必须保持 null 交给页面显示“—”，不得回落成 0
  assert.match(homeAdapter, /summary\.stageProgress === null \|\| summary\.stageProgress === undefined\s*\n\s*\? null/)
  assert.match(homeAdapter, /summary\.creditRate === null \|\| summary\.creditRate === undefined\s*\n\s*\? null/)
  assert.match(homePage, /Number\.isFinite\(value\) \? `\$\{value\}%` : '—'/)
})

test('S3 首页业务对象走 runAction，全部服务是独立目录入口', () => {
  assert.match(homePage, /import \{ canNavigate, disabledReasonOf, runAction \} from '@\/services\/actionRouter'/)
  assert.match(homePage, /@click\.stop="runAction\(home\.nextAction\)"/)
  assert.match(homePage, /<HomeQuickServices :key="loadedContextKey" :defaults="home.quickServices"/)
  assert.match(shortcuts, /runAction\(item.action, \{ side: 'student' \}\)/)
  assert.match(homePage, /@click="runAction\(t\.action\)"/)
  assert.match(homePage, /@click="runAction\(n\.action\)"/)
  // 阻断项不得再统一丢去“我的申请”大厅
  assert.doesNotMatch(homePage, /go\('\/pages\/student\/my-applications\/index'\)/)
  const blockerSection = homePage.slice(homePage.indexOf('<!-- 当前阻断 -->'), homePage.indexOf('<!-- 今日安排'))
  assert.doesNotMatch(blockerSection, /go\('\/pages\/student\/campus-service\/index'\)/)
  assert.match(shortcuts, /allServices\(\) \{ go\('\/pages\/student\/campus-service\/index'\)/)
  assert.match(homePage, /@click="runAction\(b\.action\)"/)
})

test('S3 首页阻断项没有安全入口时明确说明，不给假按钮', () => {
  assert.match(homePage, /v-if="canRun\(b\.action\)"/)
  assert.match(homePage, /disabledReason\(b\.action\)/)
})

test('S3 projectionVersion 变化必须立刻作废本地 20s freshness', () => {
  assert.match(homePage, /loadedProjectionVersion/)
  assert.match(homePage, /this\.loadedProjectionVersion === \(this\.home\.projectionVersion \|\| ''\)/)
  assert.match(homePage, /HOME_TTL_MS = 20_000/, '20s 本地缓存仍在，只是不再能盖过 projectionVersion')
  assert.match(homeAdapter, /projectionVersion: \(ov && ov\.projectionVersion\) \|\| ''/)
  assert.match(homeAdapter, /asOf: \(ov && ov\.asOf\) \|\| ''/)
})

// ── S4 Agenda ──

test('S4 首页“今天”消费 Agenda 投影而不是本地课表拼装', () => {
  assert.match(homePage, /v-for="c in home\.today"/)
  assert.doesNotMatch(homePage, /home\.todayCourses/)
  assert.match(homePage, /查看7天/)
  assert.match(homePage, /go\('\/pages\/student\/agenda\/index'\)/)
})

test('S4 Agenda 页做真网络分页，且过期响应按 epoch 丢弃', () => {
  assert.match(agendaPage, /studentApi\.getAgenda\(7, '', 20\)/)
  assert.match(agendaPage, /studentApi\.getAgenda\(7, this\.cursor, 20\)/)
  assert.match(agendaPage, /nextCursor/)
  assert.match(agendaPage, /this\._epoch !== epoch/)
  // 按 stable id 去重，避免翻页重复
  assert.match(agendaPage, /seen\.has\(item\.eventId\)/)
  // 不得把整段数据拉回来再本地切片
  assert.doesNotMatch(agendaPage, /pagedSlice|listPaging/)
})

test('S4 Agenda 没有 action 的条目不给假按钮', () => {
  assert.match(agendaPage, /if \(!item\.action\) return/)
  assert.match(agendaPage, /canNavigate\(item\.action, 'student'\)/)
  assert.match(agendaPage, /disabledReasonOf\(item\.action\)/)
})

test('S4 Agenda 路由已注册且未占用 tabBar 位置', () => {
  const manifest = JSON.parse(read('src/pages.json'))
  const student = manifest.subPackages.find((pkg) => pkg.root === 'pages/student')
  assert.ok(student.pages.some((page) => page.path === 'agenda/index'), 'Agenda 页必须注册在学生分包')
  assert.match(homePage, /<MobileTabBar side="student" active="home"/, '底部 Tab 仍是四个稳定入口')
})
