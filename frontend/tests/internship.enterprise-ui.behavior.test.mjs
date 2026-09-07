import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { formatDateTime } from '../src/utils/dateUtils.js'

// Run the actual Options API methods, with network and UI feedback replaced.
function view(file, api = {}, overrides = {}) {
  const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/' + file, import.meta.url), 'utf8')).descriptor.script.content
    .replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '')
    .replace(/components:\s*\{[^}]*\},/, 'components: {},').replace('export default', 'return')
  const routes = []
  const options = new Function('internshipApi', 'positionApi', 'complianceApi', 'toast', 'canCode', 'emptyConflict', 'window', 'formatDateTime', script)(
    api, api, api, { success() {}, error() {} }, (ctx, code) => ctx.permissionPatterns?.includes(code), () => ({}), {}, formatDateTime)
  const instance = { ...options.data(), ctx: { permissionActions: { editEnterprise: { allowed: true }, createEnterprise: { allowed: true } } },
    $route: { params: { id: '1' }, path: '/admin/internship/enterprises/1/edit', query: { batchId: '23' } },
    $router: { push: (route) => routes.push(route) }, $refs: { entForm: { validate: async () => ({ valid: true }) } }, ...overrides }
  for (const [key, fn] of Object.entries(options.methods)) instance[key] = fn.bind(instance)
  for (const [key, fn] of Object.entries(options.computed)) Object.defineProperty(instance, key, { get: () => fn.call(instance) })
  return { instance, options, routes }
}
const ok = (data) => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r }); return { promise, resolve } }

test('enterprise editing preserves a masked phone and returns to the same company and batch', async () => {
  let submitted
  const { instance: page, routes } = view('EnterpriseFormView.vue', {
    getEnterpriseDetail: async () => ok({ id: '1', name: '虚构验收企业', version: 4, contactPhoneMasked: '138****0000' }),
    updateEnterprise: async (id, body) => { submitted = { id, body }; return ok({ id }) }
  })
  await page.init()
  await page.onSubmit()
  assert.equal(submitted.id, '1')
  assert.equal(submitted.body.expectedVersion, 4)
  assert.equal(Object.hasOwn(submitted.body, 'contactPhone'), false)
  assert.deepEqual(routes[0], { path: '/admin/internship/enterprises/1', query: { batchId: '23' } })
})

test('archived enterprises cannot submit even when the role can maintain companies', async () => {
  let calls = 0
  const { instance: page } = view('EnterpriseFormView.vue', {
    getEnterpriseDetail: async () => ok({ id: '1', coopStatus: 'ARCHIVED' }), updateEnterprise: async () => { calls++ }
  })
  await page.init()
  assert.equal(page.readonly, true)
  await page.onSubmit()
  assert.equal(calls, 0)
})

test('a late enterprise form response cannot overwrite a more recent load of the same ID', async () => {
  const old = deferred()
  let calls = 0
  const { instance: page } = view('EnterpriseFormView.vue', { getEnterpriseDetail: () => ++calls === 1 ? old.promise : Promise.resolve(ok({ id: '1', name: '最新名称' })) })
  const pending = page.init()
  await page.init()
  old.resolve(ok({ id: '1', name: '旧名称' }))
  await pending
  assert.equal(page.form.name, '最新名称')
})

test('a save finishing after switching companies does not navigate or clear the new draft', async () => {
  const save = deferred()
  const { instance: page, routes } = view('EnterpriseFormView.vue', {
    getEnterpriseDetail: async (id) => ok({ id, name: id === '1' ? '第一企业' : '第二企业', version: 1 }),
    updateEnterprise: () => save.promise
  })
  await page.init()
  const pending = page.onSubmit()
  await Promise.resolve()
  page.$route.params.id = '2'
  await page.init()
  page.form.name = '第二企业未保存草稿'
  save.resolve(ok({ id: '1' }))
  await pending
  assert.equal(routes.length, 0)
  assert.equal(page.form.name, '第二企业未保存草稿')
})

test('enterprise section deep links preserve batch and list context', () => {
  const { instance: page } = view('InternshipEnterpriseDetailView.vue', {}, {
    $route: { params: { id: '1' }, path: '/admin/internship/enterprises/1', query: { section: 'inspections', panel: 'qualification', batchId: '23' } }
  })
  assert.equal(page.tab, 'inspections')
  assert.deepEqual(page.listQuery, { panel: 'qualification', batchId: '23' })
  assert.equal(page.sectionLink('contacts').query.batchId, '23')
  assert.equal(page.sectionLink('contacts').query.section, 'contacts')
  page.$route.query.inspectionId = '10'
  assert.equal(page.sectionLink('contacts').query.inspectionId, undefined)
  assert.equal(page.sectionLink('inspections').query.inspectionId, '10')
  page.$route.query.section = 'unknown'
  assert.equal(page.tab, 'basic')
})

test('enterprise detail returns to a same-batch business object and rejects external return paths', () => {
  const origin = '/admin/internship/students/9?batchId=23&section=placement'
  const { instance: page, routes } = view('InternshipEnterpriseDetailView.vue', {}, {
    $route: { params: { id: '1' }, path: '/admin/internship/enterprises/1', query: { batchId: '23', returnTo: origin } }
  })
  page.detail = { id: '1', batchId: '23' }
  page.goBack(); assert.equal(routes[0], origin)
  page.$route.query.returnTo = 'https://outside.invalid/admin/internship/students/9?batchId=23'
  page.goBack(); assert.deepEqual(routes[1], { path: '/admin/internship/enterprises', query: { batchId: '23' } })
})

test('inspection deep links cannot open a record absent from the current enterprise', () => {
  const { instance: page } = view('InternshipEnterpriseDetailView.vue', {}, {
    $route: { params: { id: '1' }, path: '/admin/internship/enterprises/1', query: { section: 'inspections', inspectionId: '99' } }
  })
  page.detail = { id: '1' }; page.loading = false
  page.inspections = [{ id: '10', companyId: '1' }]
  assert.equal(page.inspectionRequested, true)
  assert.equal(page.inspectionForm, null)
  page.$route.query.inspectionId = '10'
  assert.equal(page.inspectionForm.record.id, '10')
})

test('late related company positions cannot enter another enterprise detail', async () => {
  const old = deferred()
  const { instance: page } = view('InternshipEnterpriseDetailView.vue', {
    getEnterpriseDetail: async (id) => ok({ id }),
    getPositions: ({ companyId }) => companyId === '1' ? old.promise : Promise.resolve(ok({ list: [{ id: 'new-position' }] }))
  })
  const pending = page.load()
  await Promise.resolve()
  page.$route.params.id = '2'
  await page.load()
  old.resolve(ok({ list: [{ id: 'old-position' }] }))
  await pending
  assert.equal(page.detail.id, '2')
  assert.deepEqual(page.positions, [{ id: 'new-position' }])
})

test('company positions report a failed request instead of a false empty catalog', async () => {
  const { instance: page } = view('InternshipEnterpriseDetailView.vue', {
    getEnterpriseDetail: async () => ok({ id: '1' }), getPositions: async () => ({ code: 503, message: '岗位服务不可用' })
  })
  await page.load()
  assert.equal(page.positionsError, '岗位服务不可用')
  assert.equal(page.positionsLoading, false)
})
