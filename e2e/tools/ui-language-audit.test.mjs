import test from 'node:test'
import assert from 'node:assert/strict'
import { requestAllowed, flagText, inventory, detailRoutePattern } from './ui-language-audit.mjs'

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
  assert.equal(requestAllowed('POST', 'https://example.com/api/v1/auth/browser-login', origins), false)
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
  assert.ok(items.filter(s => s.client === 'student').every(s => s.widths.includes(390)))
})

test('详情只接受对应路由，不能把列表页截图当详情', () => {
  const pattern = detailRoutePattern('/enterprise/applications/:id')
  assert.ok(pattern.test('/enterprise/applications/123'))
  assert.equal(pattern.test('/enterprise/applications'), false)
  assert.equal(pattern.test('/enterprise/applications/123/delete'), false)
})
