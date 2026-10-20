import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { POSITION_STATUS } from '../src/modules/internship/constants/position.constants.js'

const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipPositionListView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/ {2}components: \{[^\n]*\},/, '').replace('export default', 'return')
const ok = data => ({ code: 0, data })
const rights = ['internship.position.view', 'internship.position.manage', 'internship.position.publish', 'internship.position.export', 'internship.enterprise.view']
function setup(api = {}, query = { batchId: '1' }, permissions = rights) {
  const def = new Function('positionApi', 'internshipApi', 'canCode', 'POSITION_STATUS', script)(api, api, (ctx, code) => ctx.permissionPatterns?.includes(code), POSITION_STATUS)
  const targets = []
  const vm = { ...def.data(), ctx: { permissionPatterns: permissions }, $route: { path: '/admin/internship/positions', query }, $router: { push: t => targets.push(t) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, targets }
}

test('position list template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'InternshipPositionListView.vue', id: 'position-list' }).errors, [])
})

test('building a publish link cannot mutate the cached query shared by other row links', () => {
  const { def } = setup()
  const cached = Object.freeze({ batchId: '1', keyword: '测试', page: '2' })
  const target = def.methods.positionLink.call({ listQuery: cached }, '7', '', 'publish')
  assert.equal(target.query.section, 'publish'); assert.equal(cached.section, undefined)
  const basic = def.methods.positionLink.call({ listQuery: cached }, '7')
  assert.equal(basic.query.section, undefined)
})

test('query restore accepts an explicit empty status and keeps precise company and batch identifiers', () => {
  const { vm } = setup({}, { panel: 'publish', status: '', companyId: '9007199254740999', batchId: '8', page: '3' })
  vm.load = () => {}; vm.applyPanel('publish')
  assert.equal(vm.appliedFilters.status, ''); assert.equal(vm.page, 3)
  const target = vm.positionLink('9007199254740998', '', 'publish')
  assert.equal(target.query.companyId, '9007199254740999'); assert.equal(target.query.batchId, '8'); assert.equal(target.query.section, 'publish')
})

test('unsubmitted input cannot change paging, detail or export scope', async () => {
  let exported
  const { vm, targets } = setup({ exportPositions: async p => { exported = p; return ok({}) } })
  vm.appliedFilters = { keyword: '已经查询', companyId: '7', status: 'PENDING', risk: 'true' }
  vm.filters = { keyword: '尚未查询', companyId: '9', status: '', risk: '' }
  vm.turnPage(3); assert.equal(targets[0].query.keyword, '已经查询'); assert.equal(targets[0].query.companyId, '7')
  assert.equal(vm.positionLink('8').query.keyword, '已经查询')
  await vm.exportFn(); assert.deepEqual(exported, { keyword: '已经查询', companyId: '7', status: 'PENDING', batchId: '1' })
  vm.search(); assert.equal(targets[1].query.keyword, '尚未查询'); assert.equal(targets[1].query.page, '1')
})

test('list requests require batch and view permission, without blocking explicitly school-wide statistics', async () => {
  let calls = 0
  const { vm } = setup({ getPositions: () => assert.fail('unscoped list'), getPositionStats: async () => { calls++; return ok({ total: 0 }) } }, {})
  await vm.load(); assert.match(vm.error, /批次/)
  vm.activePanel = 'stats'; await vm.load(); assert.equal(calls, 1)
  vm.ctx.permissionPatterns = []; await vm.load(); assert.equal(calls, 1); assert.match(vm.error, /权限/); assert.equal(vm.posStats, null)
})

test('risk filter is a real boolean and an empty risk means no filter', async () => {
  const calls = []
  const { vm } = setup({ getPositions: async p => { calls.push(p); return ok({ list: [], total: 0 }) } })
  vm.appliedFilters.risk = 'false'; await vm.load(); assert.equal(calls[0].risk, false)
  vm.appliedFilters.risk = 'true'; await vm.load(); assert.equal(calls[1].risk, true)
  vm.appliedFilters.risk = ''; await vm.load(); assert.equal(calls[2].risk, undefined)
})

test('failed statistics remove old numbers and remain errors', async () => {
  const { vm } = setup({ getPositionStats: async () => ({ code: 1, message: '统计服务不可用' }) })
  vm.activePanel = 'stats'; vm.posStats = { total: 99 }; await vm.load()
  assert.equal(vm.posStats, null); assert.equal(vm.error, '统计服务不可用'); assert.equal(vm.loading, false)
})

test('late list results cannot overwrite another request or an unmounted page', async () => {
  const replies = []
  const { vm, def } = setup({ getPositions: () => new Promise(r => replies.push(r)) })
  const first = vm.load(), second = vm.load()
  replies[1](ok({ list: [{ id: 'new' }], total: 1 })); await second
  replies[0](ok({ list: [{ id: 'old' }], total: 8 })); await first
  assert.equal(vm.rows[0].id, 'new')
  const last = vm.load(); def.beforeUnmount.call(vm); replies[2](ok({ list: [{ id: 'old' }], total: 1 })); await last
  assert.deepEqual(vm.rows, [])
})

test('company filter delegates search to the shared picker and keeps a readable fallback without permission', () => {
  const { vm } = setup({}, { batchId: '1' }, ['internship.position.view'])
  vm.filters.companyId = '7'
  assert.deepEqual(vm.enterpriseFallbackOptions, [{ value: '7', label: '已按企业筛选' }])
  vm.ctx.permissionPatterns = rights
  assert.deepEqual(vm.enterpriseFallbackOptions, [])
})

test('old export cannot enter a changed identity or batch', async () => {
  let resolveExport
  const { vm } = setup({ exportPositions: () => new Promise(r => { resolveExport = r }) })
  const exported = vm.exportFn(); vm.scopeEpoch++; vm.$route.query.batchId = '2'
  resolveExport(ok({ downloadUrl: '/old-file' }))
  assert.equal((await exported).code, 1)
})

test('statistics and back navigation retain the original list filters', () => {
  const { vm, targets } = setup({}, { batchId: '1', panel: 'publish' })
  vm.appliedFilters.companyId = '7'; vm.appliedFilters.status = 'PENDING'; vm.page = 4
  vm.showPanel('stats'); assert.equal(targets[0].query.companyId, '7'); assert.equal(targets[0].query.page, '4')
  vm.$route.query = targets[0].query; vm.showPanel('list'); assert.equal(targets[1].query.status, 'PENDING'); assert.equal(targets[1].query.batchId, '1')
})
