import test from 'node:test'
import assert from 'node:assert/strict'
import { requestAllowed, flagText, inventory, detailRoutePattern, captureStatus, renderReport, rolePatterns, scrollOffsets, mergeAuditRuns, buildAssetPath, chooseScrollRegion } from './ui-language-audit.mjs'
import path from 'node:path'

test('写请求默认拒绝，认证白名单限定方法、来源和完整路径', () => {
  const origins = ['http://127.0.0.1:8000']
  const allowed = (method, p) => requestAllowed(method, origins[0] + p, origins)
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
    assert.equal(allowed(method, '/api/v1/student/1'), false)
  }
  assert.equal(allowed('GET', '/api/v1/student/1'), true)
  assert.equal(allowed('POST', '/api/v1/auth/browser-login'), true)
  assert.equal(allowed('DELETE', '/api/v1/auth/browser-login'), false)
  assert.equal(allowed('POST', '/api/v1/auth/browser-login/extra'), false)
  assert.equal(allowed('POST', '/api/v1/auth/password'), false)
  assert.equal(allowed('GET', '/api/v1/admin/message-campaigns/ops/reconcile'), false)
  assert.equal(allowed('GET', '/api/v1/admin/message-campaigns/ops/reconcile/?page=1'), false)
  assert.equal(requestAllowed('POST', 'https://example.com/api/v1/auth/browser-login', origins), false)
})

test('岗位核验不能把指导教师当管理员，也不能把学院毕设管理员当校级管理', () => {
  assert.ok(rolePatterns.GRADUATION.test('毕设管理员\n按岗位业务关系授权'))
  assert.equal(rolePatterns.GRADUATION.test('毕设指导教师 本人指导毕设学生'), false)
  assert.equal(rolePatterns.GRADUATION.test('学院毕设管理员'), false)
  assert.equal(rolePatterns.INTERNSHIP.test('实习指导教师'), false)
  assert.ok(rolePatterns.LEADER.test('校院领导'))
  assert.ok(rolePatterns.ADMIN.test('学校管理员本校配置与授权范围'))
  assert.ok(rolePatterns.ACADEMIC.test('教务老师'))
  assert.ok(rolePatterns.AFFAIRS.test('学工管理员'))
})

test('标记代码、编号、开发词和重复句，不把待确认改成失败', () => {
  const flags = flagText('RISK_HANDLE expectedVersion 1000000000000000007\n请只读核对提交结果。请只读核对提交结果。')
  assert.equal(flags.length, 4)
  assert.equal(flagText('正在确认提交结果，请稍后刷新查看').length, 0)
})

test('清单包含全部可见菜单及四端，保留动态路由而不造编号', async () => {
  const items = await inventory()
  assert.equal(items.filter(s => s.source).length, 477)
  for (const client of ['staff', 'student', 'enterprise', 'mini']) assert.ok(items.some(s => s.client === client))
  assert.ok(items.some(s => s.route.includes(':companyId')))
  assert.ok(items.some(s => s.route === '/admin/approval/todos/:taskId'))
  assert.ok(items.some(s => s.route === '/admin/messages/outbox/:campaignId'))
  assert.ok(items.some(s => s.route === '/admin/approval/templates' && !s.view))
  assert.ok(items.some(s => s.route === '/admin/approval/templates' && s.view === 'first-template'))
  assert.ok(items.filter(s => s.client === 'student').every(s => s.widths.includes(390)))
})

test('详情只接受对应路由，不能把列表页截图当详情', () => {
  const pattern = detailRoutePattern('/enterprise/applications/:id')
  assert.ok(pattern.test('/enterprise/applications/123'))
  assert.equal(pattern.test('/enterprise/applications'), false)
  assert.equal(pattern.test('/enterprise/applications/123/delete'), false)
})

test('首页重定向、丢失筛选和移动端跳转不能记作目标页', () => {
  const capture = { expectedUrl: 'http://localhost:5173/admin/students?status=PENDING', actualUrl: 'http://localhost:5173/admin/students?status=PENDING', httpStatus: 200, settled: true }
  assert.equal(captureStatus(capture), '已截图，待人工通读')
  assert.equal(captureStatus({ ...capture, actualUrl: 'http://localhost:5173/workbench' }), '页面已跳转，非目标页面')
  assert.equal(captureStatus({ ...capture, actualUrl: 'http://localhost:5173/admin/students' }), '页面已跳转，非目标页面')
  assert.equal(captureStatus({ ...capture, actualUrl: 'http://localhost:5173/login' }), '登录失效，非目标页面')
  assert.equal(captureStatus({ ...capture, expectedUrl: 'http://localhost:5188/#/pages/student/profile/index', actualUrl: 'http://localhost:5188/#/pages/student/home/index' }), '页面已跳转，非目标页面')
})

test('空壳页面成功不能掩盖数据失败或未加载完成', () => {
  const capture = { expectedUrl: 'http://localhost:5173/workbench', actualUrl: 'http://localhost:5173/workbench', httpStatus: 200, settled: true }
  assert.equal(captureStatus({ ...capture, apiFailures: [{ status: 403 }] }), '权限受限，已留证')
  assert.equal(captureStatus({ ...capture, apiFailures: [{ status: 500 }] }), '页面或数据加载失败，已留证')
  assert.equal(captureStatus({ ...capture, apiFailures: [{ status: null }] }), '页面或数据加载失败，已留证')
  assert.equal(captureStatus({ ...capture, settled: false }), '页面加载未稳定，已留证')
})

test('报告包含入口与可点击截图，并保持人工待审状态', () => {
  const report = renderReport([{ page: '课程|列表', route: '/courses', role: '任课教师', width: 1440, status: '已截图，待人工通读', screenshot: '00001.png', flags: [], conclusion: '未人工审阅' }])
  assert.ok(report.includes('|课程／列表|/courses|'))
  assert.ok(report.includes('[查看截图](00001.png)'))
  assert.ok(report.includes('未人工审阅'))
})

test('内部滚动区分屏留证覆盖到底部，短页面不增加假分屏', () => {
  assert.deepEqual(scrollOffsets(800, 1000), [])
  assert.deepEqual(scrollOffsets(2000, 800), [700, 1200])
  assert.deepEqual(scrollOffsets(2200, 800), [700, 1400])
})

test('弹窗优先留证，无弹窗时不能被较大的不滚动外壳挡住正文', () => {
  const shell = { visible: true, viewport: 1000, height: 1000, area: 1440000 }
  const content = { visible: true, viewport: 800, height: 2400, area: 900000 }
  const dialog = { visible: true, viewport: 300, height: 300, area: 150000, dialog: true }
  assert.equal(chooseScrollRegion([shell, content]), content)
  assert.equal(chooseScrollRegion([shell, content, dialog]), dialog)
  assert.equal(chooseScrollRegion([shell, content, { ...dialog, visible: false }]), content)
  assert.equal(chooseScrollRegion([shell]), undefined)
})

test('总报告按真实页面角色尺寸去重，保留最新失败并修正图片相对路径', () => {
  const page = { client: 'staff', route: '/workbench', role: '辅导员', width: 1440 }
  const records = mergeAuditRuns([
    { name: '2026-10-24T02', scope: { runtimeSource: '主目录基线' }, records: [{ ...page, status: '加载失败', screenshot: '1.png', conclusion: '未人工审阅' }] },
    { name: '2026-10-24T01', records: [{ ...page, status: '已截图', screenshot: 'old.png', conclusion: '已通读旧图，待办代码需要汉化' }, { ...page, width: 390, screenshot: 'mobile.png' }] }
  ])
  assert.equal(records.length, 2)
  assert.equal(records[0].status, '加载失败')
  assert.equal(records[0].screenshot, '2026-10-24T02/1.png')
  assert.equal(records[0].runtimeSource, '主目录基线')
  assert.equal(records[0].conclusion, '未人工审阅')
  assert.equal(records[0].previousReview.sourceRun, '2026-10-24T01')
  assert.equal(records[1].width, 390)
})

test('候选静态资源只允许构建目录内路径，拒绝编码后的目录越界', () => {
  const directory = path.resolve('e2e/runtime/ui-audit/test-build')
  assert.equal(buildAssetPath(directory, '/assets/app.js'), path.join(directory, 'assets/app.js'))
  assert.equal(buildAssetPath(directory, '/%2e%2e/private.json'), null)
  assert.equal(buildAssetPath(directory, '/%'), null)
})

test('同一路径的列表与已打开正文分别留证，不互相覆盖', () => {
  const page = { client: 'staff', route: '/admin/messages/inbox', role: '学校管理员', width: 1440 }
  const records = mergeAuditRuns([{ name: 'one', records: [page, { ...page, view: 'first-message' }] }])
  assert.equal(records.length, 2)
  assert.equal(records[1].view, 'first-message')
})
