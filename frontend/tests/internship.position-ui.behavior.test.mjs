import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { presentAuditRecord } from '../src/utils/presentationSafety.js'
import { REMUNERATION_TYPE_LABEL, REMUNERATION_CYCLE_LABEL, REMUNERATION_TYPE, REMUNERATION_CYCLE, POSITION_STATUS } from '../src/modules/internship/constants/position.constants.js'

function view(file, api = {}, overrides = {}) {
  const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/' + file, import.meta.url), 'utf8')).descriptor.script.content
    .replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '')
    .replace(/components:\s*\{[^}]*\},/, 'components: {},').replace('export default', 'return')
  const routes = [], saved = []
  const options = new Function('positionApi', 'toast', 'canCode', 'useInternshipBatchStore', 'REMUNERATION_TYPE_LABEL', 'REMUNERATION_CYCLE_LABEL', 'REMUNERATION_TYPE', 'REMUNERATION_CYCLE', 'POSITION_STATUS', 'window', script)(
    api, { success() {}, error() {} }, (ctx, code) => ctx.permissionPatterns?.includes(code), () => ({ selectedBatchId: '23' }),
    REMUNERATION_TYPE_LABEL, REMUNERATION_CYCLE_LABEL, REMUNERATION_TYPE, REMUNERATION_CYCLE, POSITION_STATUS, { __SAAS_DIRTY_FORM_GUARD__: { markSaved: () => saved.push(true) } })
  const instance = { ...options.data(), ctx: { permissionPatterns: ['internship.position.view', 'internship.position.manage', 'internship.position.publish', 'internship.enterprise.view'] },
    $route: { params: { id: '1' }, path: '/admin/internship/positions/1', query: { batchId: '23', section: 'rights' } },
    $router: { push: (route) => { routes.push(route); return Promise.resolve() } }, $refs: { posForm: { validate: async () => ({ valid: true }) } }, ...overrides }
  for (const [key, fn] of Object.entries(options.methods)) instance[key] = fn.bind(instance)
  for (const [key, fn] of Object.entries(options.computed)) Object.defineProperty(instance, key, { get: () => fn.call(instance) })
  return { page: instance, options, routes, saved }
}
const ok = (data) => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r }); return { promise, resolve } }
const detail = (id = '1') => ({ id, title: '虚构验收岗位', status: 'DRAFT', version: 4, batchId: '23', compliance: { passed: true } })

test('school position audit preserves the business action label through the shared presenter', () => {
  const { page } = view('InternshipPositionDetailView.vue')
  page.detail = { ...detail(), auditTrail: [{ action: 'STATUS_RETURN', operator: '虚构老师', detail: { reason: '补充工作地址' } }] }
  assert.equal(presentAuditRecord(page.auditRecords[0]).displayAction, '退回补正')
  assert.equal(presentAuditRecord(page.auditRecords[0]).displayReason, '补充工作地址')
})

test('school return requires an enterprise-visible correction note and the current position version', async () => {
  const calls=[]
  const {page}=view('InternshipPositionDetailView.vue',{setPositionStatus:async(id,body)=>{calls.push({id,body});return ok({})}})
  page.detail={...detail(),status:'PENDING'};page.loading=false;page.load=async()=>{}
  page.askStatus('RETURN')
  assert.equal(page.confirm.requireReason,true);assert.match(page.confirm.message,/企业可见/)
  await page.onConfirm({reason:'  '});assert.equal(calls.length,0)
  await page.onConfirm({reason:'补充工作地址'})
  assert.deepEqual(calls,[{id:'1',body:{action:'RETURN',reason:'补充工作地址',expectedVersion:4}}])
})

test('school return is unavailable for published positions and retains conflict feedback', async () => {
  const {page}=view('InternshipPositionDetailView.vue',{setPositionStatus:async()=>({code:409,message:'岗位已被其他审核人处理'})})
  page.detail={...detail(),status:'PUBLISHED'};page.loading=false;page.askStatus('RETURN');assert.equal(page.confirm.visible,false)
  page.detail.status='PENDING';page.askStatus('RETURN');await page.onConfirm({reason:'补充具体事项'})
  assert.match(page.actionError,/其他审核人/);assert.equal(page.confirm.visible,true)
})

test('position deep links and full editing retain batch, source filters and selected section', () => {
  const { page } = view('InternshipPositionDetailView.vue')
  page.detail = detail()
  page.$route.query.companyId = '7'
  assert.equal(page.tab, 'rights')
  assert.deepEqual(page.editLink, { path: '/admin/internship/positions/1/edit', query: { batchId: '23', companyId: '7', section: 'rights' } })
  assert.equal(page.sectionLink('publish').query.section, 'publish')
  assert.equal(page.listQuery.section, undefined)
  page.$route.query.section = 'invalid'
  assert.equal(page.tab, 'basic')
})

test('read-only teacher cannot invoke position state or risk methods', async () => {
  let calls = 0
  const { page } = view('InternshipPositionDetailView.vue', { markPositionRisk: () => { calls++ } }, { ctx: { permissionPatterns: ['internship.position.view'] } })
  page.loading = false; page.detail = detail()
  assert.equal(page.canEdit, false)
  assert.deepEqual(page.statusActions, [])
  page.askStatus('SUBMIT'); page.askRisk(true); await page.onConfirm()
  assert.equal(calls, 0)
  assert.equal(page.confirm.visible, false)
})

test('unknown boolean conditions remain unknown and false remains a confirmed no', () => {
  const { page } = view('InternshipPositionDetailView.vue')
  page.detail = { ...detail(), nightShift: false, overtimeAllowed: null, remunerationAmount: 0 }
  const hours = page.rightsGroups[0].items
  assert.equal(hours.find((item) => item.label === '是否夜班').value, '否')
  assert.equal(hours.find((item) => item.label === '允许加班').value, '待补充')
  assert.equal(page.rightsGroups[1].items.find((item) => item.label === '报酬金额').value, '0 元')
})

test('same-ID late loads cannot replace latest position facts', async () => {
  const old = deferred(); let calls = 0
  const { page } = view('InternshipPositionDetailView.vue', { getPositionDetail: () => ++calls === 1 ? old.promise : Promise.resolve(ok({ ...detail(), title: '最新' })) })
  const pending = page.load(); await page.load(); old.resolve(ok({ ...detail(), title: '旧数据' })); await pending
  assert.equal(page.detail.title, '最新')
})

test('status confirmation snapshots version and does not replay a failed action', async () => {
  let submitted, calls = 0
  const { page } = view('InternshipPositionDetailView.vue', { setPositionStatus: async (id, body) => { calls++; submitted = { id, body }; return { code: 409, message: '岗位已修改' } } })
  page.detail = detail(); page.loading = false; page.askStatus('SUBMIT')
  page.detail.version = 5
  await page.onConfirm(); await page.onConfirm()
  assert.equal(submitted.body.expectedVersion, 4)
  assert.equal(calls, 1)
  assert.equal(page.actionError, '岗位已修改')
})

test('late action receipt cannot reload another position or close its dialog', async () => {
  const save = deferred(); let loads = 0
  const { page } = view('InternshipPositionDetailView.vue', { setPositionStatus: () => save.promise, getPositionDetail: async (id) => { loads++; return ok(detail(id)) } })
  page.detail = detail(); page.loading = false; page.askStatus('SUBMIT')
  const pending = page.onConfirm()
  page.$route.params.id = '2'; await page.load(); page.askStatus('SUBMIT')
  save.resolve(ok(detail('1'))); await pending
  assert.equal(page.detail.id, '2'); assert.equal(page.confirm.visible, true); assert.equal(loads, 1)
})

test('full position form saves complete rights and returns to original section', async () => {
  let submitted
  const { page, routes, saved } = view('PositionFormView.vue', { getPositionDetail: async () => ok(detail()), updatePosition: async (id, body) => { submitted = body; return ok(detail(id)) } })
  await page.init(); page.form.dailyHours = 8; page.form.nightShift = false; await page.onSubmit()
  assert.equal(saved.length, 1)
  assert.equal(submitted.dailyHours, 8); assert.equal(submitted.nightShift, false); assert.equal(submitted.expectedVersion, 4)
  assert.deepEqual(routes[0], { path: '/admin/internship/positions/1', query: { batchId: '23', section: 'rights' } })
})

test('full form late save does not navigate away from a new draft', async () => {
  const save = deferred()
  const { page, routes, saved } = view('PositionFormView.vue', { getPositionDetail: async (id) => ok(detail(id)), updatePosition: () => save.promise })
  await page.init(); const pending = page.onSubmit(); await Promise.resolve()
  page.$route.params.id = '2'; await page.init(); page.form.title = '新草稿'
  save.resolve(ok(detail('1'))); await pending
  assert.equal(saved.length, 0)
  assert.equal(routes.length, 0); assert.equal(page.form.title, '新草稿')
})

test('position list restores company and batch scope and passes it into detail', async () => {
  let query
  const { page } = view('InternshipPositionListView.vue', { getPositions: async (p) => { query = p; return ok({ list: [], total: 0 }) } },
    { $route: { params: {}, path: '/admin/internship/positions', query: { batchId: '23', companyId: '7', status: 'PENDING', page: '2' } } })
  page.applyPanel('list'); await Promise.resolve()
  assert.equal(query.batchId, '23'); assert.equal(query.companyId, '7'); assert.equal(query.page, 2)
  assert.equal(page.positionLink('1', '', 'publish').query.companyId, '7')
})

test('position detail returns to a same-batch business object and rejects cross-batch return paths', () => {
  const origin = '/admin/internship/students/9?batchId=23&section=placement'
  const { page, routes } = view('InternshipPositionDetailView.vue')
  page.detail = detail(); page.$route.query.returnTo = origin
  page.goBack(); assert.equal(routes[0], origin)
  page.$route.query.returnTo = origin.replace('batchId=23', 'batchId=24')
  page.goBack(); assert.deepEqual(routes[1], { path: '/admin/internship/positions', query: { batchId: '23' } })
})

test('a failed full-form save keeps its draft and unsaved protection', async () => {
  const { page, saved, routes } = view('PositionFormView.vue', {
    getPositionDetail: async () => ok(detail()), updatePosition: async () => ({ code: 409, message: '版本冲突' })
  })
  await page.init(); page.form.title = '应保留的草稿'; await page.onSubmit()
  assert.equal(saved.length, 0); assert.equal(routes.length, 0)
  assert.equal(page.form.title, '应保留的草稿')
})
