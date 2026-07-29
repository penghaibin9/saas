import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (relative) => fs.readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8')

test('student home uses one aggregate request and lightweight message summary', () => {
  const page = read('src/pages/student/home/index.vue')
  const api = read('src/services/studentApi.js')
  const adapter = read('src/services/realApi.js')
  assert.doesNotMatch(page, /loadEmergency|getMessages\(\)/)
  assert.match(page, /messageSummary\?\.latestEmergency/)
  assert.match(page, /HOME_TTL_MS = 20_000/)
  assert.match(page, /_loadEpoch/)
  assert.match(api, /real\.studentHomeReal\(\)/)
  assert.match(adapter, /quickServices: \[\]/)
  assert.match(adapter, /todayCourses: \[\]/)
  assert.doesNotMatch(adapter.match(/export async function studentHomeReal\(\)[\s\S]*?export const enrichHome/)[0], /\.\.\.mock|mockHome/)
})

test('teacher workbench has TTL dirty-context checks and one workbench call', () => {
  const page = read('src/pages/teacher/workbench/index.vue')
  const adapter = read('src/services/realApi.js')
  assert.doesNotMatch(page, /onShow\(\) \{ this\.load\(\) \}/)
  assert.match(page, /WORKBENCH_TTL_MS = 20_000/)
  assert.match(page, /getTeacherWorkbenchVersion/)
  assert.match(page, /loadInternshipContext/)
  const loadBlock = page.match(/load\(\{ force = false[\s\S]*?\n    \},\n    quick\(q\)/)[0]
  assert.equal((loadBlock.match(/teacherApi\.getWorkbench/g) || []).length, 1)
  const adapterBlock = adapter.match(/export async function teacherWorkbenchReal[\s\S]*?export const enrichTeacherWorkbench/)[0]
  assert.doesNotMatch(adapterBlock, /\.\.\.mock/)
  assert.match(adapterBlock, /Promise\.allSettled/)
})

test('ordinary GETs are single-flight and writes are rejected rather than deduplicated', () => {
  const request = read('src/services/request.js')
  assert.match(request, /const _getInflight = new Map\(\)/)
  assert.match(request, /if \(normalizedMethod === 'GET'\)/)
  assert.match(request, /return _getInflight\.get\(key\)/)
  assert.match(request, /const _mutationInflight = new Set\(\)/)
  assert.match(request, /正在提交，请勿重复点击/)
  assert.match(request, /markMobileViewsDirty\(path\)/)
  assert.match(request, /body\.code === 401001[\s\S]*?_retried: true/)
  for (const code of ['403001', '409001', '422001', '429001']) assert.match(request, new RegExp(code))
  assert.doesNotMatch(request, /while \(current\.hasMore/)
  assert.match(request, /export function realUpload/)
  assert.match(request, /export function realDownload/)
})

test('production session skeleton contains no fixed student or teacher identity', () => {
  const session = read('src/stores/session.js')
  assert.match(session, /import\.meta\.env && import\.meta\.env\.PROD/)
  assert.match(session, /neutralUser/)
  assert.match(session, /name: '', studentNo: '', className: ''/)
})

test('high-frequency message, todo and risk pages use server pagination', () => {
  const messages = read('src/pages/student/messages/index.vue')
  const todos = read('src/pages/teacher/todos/index.vue')
  const risks = read('src/pages/teacher/risk-students/index.vue')
  assert.match(messages, /getMessagesPage/)
  assert.match(todos, /getTodosPage/)
  assert.match(risks, /getRiskStudentsPage/)
  for (const source of [messages, todos, risks]) {
    assert.match(source, /hasMore/)
    assert.match(source, /_loadEpoch/)
    assert.doesNotMatch(source, /pagedSlice/)
  }
})
