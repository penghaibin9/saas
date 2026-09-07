import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipEnterpriseListView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/  components: \{[^\n]*\},/, '').replace('export default', 'return')
const ok = data => ({ code: 0, data })
function setup(api = {}, query = {}, allowed = true) {
  const def = new Function('internshipApi', 'toast', 'canCode', script)(api, { error() {} }, () => allowed)
  const targets = []
  const vm = { ...def.data(), ctx: { permissionActions: {}, statusOptions: {} }, $route: { query }, $router: { replace: t => targets.push(t), push: t => targets.push(t) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, targets }
}

test('enterprise list template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'InternshipEnterpriseListView.vue', id: 'enterprise-list' }).errors, [])
})

test('qualification preset allows an explicit all-status filter and restores page and keyword', () => {
  const { vm } = setup({}, { panel: 'qualification', batchId: '8', coopStatus: '', keyword: '虚构企业', page: '3' })
  vm.restoreQuery()
  assert.equal(vm.activePanel, 'qualification'); assert.equal(vm.appliedFilters.coopStatus, '')
  assert.equal(vm.page, 3); assert.equal(vm.appliedFilters.keyword, '虚构企业')
  vm.reset(); assert.equal(vm.appliedFilters.coopStatus, 'PENDING'); assert.equal(vm.page, 1)
})

test('list, details, edit and creation preserve applied filters and large IDs', () => {
  const { vm, targets } = setup({}, { panel: 'qualification', keyword: '虚构企业', batchId: '8', page: '3' })
  vm.restoreQuery()
  vm.filters.keyword = '尚未查询的输入'
  const detail = vm.detailLink({ id: '9007199254740999' }, 'coop')
  assert.equal(detail.path, '/admin/internship/enterprises/9007199254740999')
  assert.equal(detail.query.section, 'coop'); assert.equal(detail.query.keyword, '虚构企业')
  assert.equal(detail.query.page, '3'); assert.equal(detail.query.batchId, '8')
  assert.deepEqual(vm.editLink({ id: '9007199254740999' }).query, vm.listQuery)
  vm.ctx.permissionActions.createEnterprise = { allowed: true }
  vm.onToolbar('create'); assert.deepEqual(targets[0].query, vm.listQuery)
})

test('search resets page while pagination retains the applied rather than unsubmitted filter', () => {
  const { vm, targets } = setup({}, { panel: 'list', page: '4' }); vm.restoreQuery()
  vm.filters.keyword = '已查询企业'; vm.search()
  assert.equal(targets[0].query.page, '1'); assert.equal(targets[0].query.keyword, '已查询企业')
  vm.filters.keyword = '尚未查询'; vm.turnPage(2)
  assert.equal(targets[1].query.keyword, '已查询企业'); assert.equal(targets[1].query.page, '2')
})

test('blacklist filters use real booleans and the school-wide list request has no batch filter', async () => {
  const calls = []
  const { vm } = setup({ getEnterprises: async p => { calls.push(p); return ok({ list: [], total: 0 }) } }, { panel: 'blacklist', batchId: '8' })
  vm.restoreQuery(); await vm.load(); assert.equal(calls[0].blacklist, true); assert.equal(calls[0].batchId, undefined)
  vm.appliedFilters.blacklist = 'false'; await vm.load(); assert.equal(calls[1].blacklist, false)
  vm.appliedFilters.blacklist = ''; await vm.load(); assert.equal(calls[2].blacklist, undefined)
})

test('stale list responses cannot overwrite newer filters or an unmounted workspace', async () => {
  const replies = []
  const { vm, def } = setup({ getEnterprises: () => new Promise(r => replies.push(r)) })
  const first = vm.load(), second = vm.load()
  replies[1](ok({ list: [{ id: 'new' }], total: 1 })); await second
  replies[0](ok({ list: [{ id: 'old' }], total: 2 })); await first
  assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.total, 1)
  const last = vm.load(); def.beforeUnmount.call(vm)
  replies[2](ok({ list: [{ id: 'old' }], total: 1 })); await last; assert.deepEqual(vm.rows, [])
})

test('failed reads clear previous facts and are distinct from empty results', async () => {
  const { vm } = setup({ getEnterprises: async () => ({ code: 1, message: '读取失败' }) })
  vm.rows = [{ id: 'old' }]; vm.total = 9; await vm.load()
  assert.deepEqual(vm.rows, []); assert.equal(vm.total, 0); assert.equal(vm.error, '读取失败'); assert.equal(vm.loading, false)
})

test('missing permissions hide maintenance entries and block list, statistics and export calls', async () => {
  const never = () => assert.fail('unauthorized API request')
  const { vm } = setup({ getEnterprises: never, getEnterpriseStats: never, exportEnterprises: never }, {}, false)
  await vm.load(); await vm.loadStats(); const result = await vm.exportFn()
  assert.match(vm.error, /权限/); assert.match(vm.statsError, /权限/); assert.equal(result.code, 1)
  assert.deepEqual(vm.toolbarActions, [])
})

test('statistics load on demand and failures never appear as zero counts', async () => {
  let calls = 0
  const { vm } = setup({ getEnterpriseStats: async () => { calls++; return { code: 1, message: '统计不可用' } } })
  vm.restoreQuery(); assert.equal(calls, 0)
  await vm.loadStats(); assert.equal(vm.entStats, null); assert.equal(vm.statsError, '统计不可用')
})

test('old statistics and export results are discarded after identity changes', async () => {
  let resolveStats, resolveExport
  const { vm } = setup({ getEnterpriseStats: () => new Promise(r => { resolveStats = r }), exportEnterprises: () => new Promise(r => { resolveExport = r }) })
  vm.ctx.permissionActions.exportEnterprises = { allowed: true }
  const stats = vm.loadStats(), exp = vm.exportFn(); vm.scopeEpoch++
  resolveStats(ok({ total: 50 })); resolveExport(ok({ downloadUrl: '/old-identity-file' })); await stats
  assert.equal(vm.entStats, null); assert.equal((await exp).code, 1)
})

test('export follows applied filters and only parameters accepted by the existing export API', async () => {
  let params
  const { vm } = setup({ exportEnterprises: async p => { params = p; return ok({ rowCount: 1 }) } })
  vm.ctx.permissionActions.exportEnterprises = { allowed: true }
  vm.appliedFilters = { keyword: '已查询企业', coopStatus: 'ACTIVE', industry: '制造', region: '长沙', blacklist: 'true' }
  vm.filters.keyword = '尚未查询'
  await vm.exportFn()
  assert.deepEqual(params, { keyword: '已查询企业', coopStatus: 'ACTIVE', industry: '制造', region: '长沙' })
})
