import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import * as constants from '../src/modules/internship/constants/recruitmentCampaign.constants.js'
import * as formHelpers from '../src/modules/internship/utils/campaignForm.js'
import { reactive } from 'vue'

const ok = (data) => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r }); return { promise, resolve } }
const campaign = (id = '1', status = 'OPEN') => ({ id, campaignName: '虚构招聘季', batchId: '23', version: 4, status,
  inviteStartAt: new Date(Date.now() - 86400000).toISOString(), inviteEndAt: new Date(Date.now() + 86400000).toISOString(), enterpriseAccessEndAt: new Date(Date.now() + 172800000).toISOString() })

function view(api = {}, overrides = {}, file = 'RecruitmentCampaignDetailView.vue') {
  const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/' + file, import.meta.url), 'utf8')).descriptor.script.content
    .replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '')
    .replace(/components:\s*\{[^}]*\},/, 'components: {},').replace('export default', 'return')
  const bindings = { ...constants, ...formHelpers, recruitmentCampaignApi: api, internshipApi: { getBatches: async () => ok({ list: [{ id: '23', batchName: '虚构批次' }], total: 1 }) }, positionApi: {},
    canCode: (ctx, code) => ctx.permissionPatterns?.includes(code), currentUserFromToken: () => ({ tenantCode: 'fixture' }),
    toast: { success() {}, error() {} }, formatDate: (v) => v, formatDateTime: (v) => v, ENTERPRISE_LOGIN_URL: '/enterprise/login', window: { location: { origin: 'http://fixture.local' } } }
  const options = new Function(...Object.keys(bindings), script)(...Object.values(bindings))
  const routes = []
  const page = { ...options.data(), ctx: { permissionPatterns: ['internship.recruitment.view', 'internship.recruitment.invite', 'internship.recruitment.manage'] },
    $nextTick: () => Promise.resolve(),
    $route: { params: { id: '1' }, path: '/admin/internship/recruitment-campaigns/1', query: { batchId: '23', page: '2', section: 'schedule', epStatus: 'INVITED', epPage: '3' } },
    $router: { push: (r) => { routes.push(r); return Promise.resolve() }, replace: (r) => { routes.push(r); return Promise.resolve() } },
    $refs: { inviteForm: { validate: async () => ({ valid: true }) }, campaignForm: { validate: async () => ({ valid: true }) } }, ...overrides }
  for (const [key, fn] of Object.entries(options.methods)) page[key] = fn.bind(page)
  for (const [key, fn] of Object.entries(options.computed)) Object.defineProperty(page, key, { get: () => fn.call(page) })
  return { page, options, routes }
}

test('detail sections retain list context while participation filters stay in the detail', () => {
  const { page, routes } = view()
  assert.equal(page.section, 'schedule')
  assert.equal(page.sectionLink('enterprises').query.epPage, '3')
  page.restoreEnterpriseQuery(); assert.equal(page.epPage, 3); assert.equal(page.epFilters.status, 'INVITED')
  page.goBack(); assert.deepEqual(routes[0].query, { batchId: '23', page: '2' })
})

test('view-only role cannot invoke invitation, revocation or state transitions', async () => {
  let calls = 0
  const { page } = view({ inviteEnterprise() { calls++ }, revokeEnterprise() { calls++ } }, { ctx: { permissionPatterns: ['internship.recruitment.view'] } })
  page.detail = campaign(); page.loading = false; page.inviteVisible = true
  assert.equal(page.canInvite, false); assert.deepEqual(page.lifecycleActions, []); assert.deepEqual(page.enterpriseRowActions({ status: 'ACCEPTED' }), [])
  await page.submitInvite(); page.askTransition('freeze'); await page.onRevokeConfirm({ reason: '测试' })
  assert.equal(calls, 0); assert.equal(page.transition.visible, false)
})

test('invalid invitation is blocked and draft retained', async () => {
  let calls = 0
  const { page } = view({ inviteEnterprise() { calls++ } })
  page.loading = false; page.detail = campaign(); page.inviteVisible = true; page.inviteModel.realName = '待补完整的联系人'
  page.$refs.inviteForm.validate = async () => ({ valid: false })
  await page.submitInvite()
  assert.equal(calls, 0); assert.equal(page.inviteSubmitting, false); assert.equal(page.inviteModel.realName, '待补完整的联系人')
})

test('double invitation while validating submits only once and displays failure beside draft', async () => {
  const validation = deferred(); let calls = 0
  const { page } = view({ inviteEnterprise: async () => { calls++; return { code: 409, message: '联系人已存在' } } })
  page.loading = false; page.detail = campaign(); page.inviteVisible = true
  page.$refs.inviteForm.validate = () => validation.promise
  const first = page.submitInvite(); await page.submitInvite(); validation.resolve({ valid: true }); await first
  assert.equal(calls, 1); assert.equal(page.inviteVisible, true); assert.equal(page.inviteError, '联系人已存在')
})

test('school invitation result retains existing-account mode and the server-preserved role', async () => {
  const { page } = view({ inviteEnterprise: async () => ok({ inviteToken: 'synthetic-only', inviteMode: 'EXISTING_MEMBER', memberRole: 'HR', expiresAt: '2026-09-30T15:59:59Z' }) })
  page.loading = false; page.detail = campaign(); page.inviteVisible = true
  await page.submitInvite()
  assert.equal(page.inviteResultVisible, true); assert.equal(page.inviteResult.inviteMode, 'EXISTING_MEMBER'); assert.equal(page.inviteResult.memberRole, 'HR')
  page.closeInviteResult(); assert.deepEqual(page.inviteResult, {})
})

test('late campaign and enterprise reads cannot replace a newer object', async () => {
  const old = deferred(); let calls = 0
  const { page } = view({ getCampaignDetail: () => ++calls === 1 ? old.promise : Promise.resolve(ok(campaign('2'))), getCampaignEnterprises: async () => ok({ list: [{ id: 'new' }], hasMore: false }) })
  const first = page.init(); page.$route.params.id = '2'; await page.init(); old.resolve(ok(campaign('1'))); await first
  assert.equal(page.detail.id, '2'); assert.equal(page.enterpriseRows[0].id, 'new'); assert.equal(page.loading, false)
})

test('wrong-batch deep link does not expose a participation queue or write controls', async () => {
  let queues = 0
  const { page } = view({ getCampaignDetail: async () => ok({ ...campaign(), batchId: '24' }), getCampaignEnterprises: () => { queues++ } })
  await page.init()
  assert.match(page.error, /不属于当前批次/); assert.equal(page.canInvite, false); assert.equal(queues, 0)
})

test('leaving during invitation never shows its one-time token on another campaign', async () => {
  const response = deferred()
  const { page, options } = view({ inviteEnterprise: () => response.promise })
  page.loading = false; page.detail = campaign(); page.inviteVisible = true
  const request = page.submitInvite(); await Promise.resolve(); options.beforeUnmount.call(page)
  response.resolve(ok({ inviteToken: 'synthetic-only' })); await request
  assert.equal(page.inviteResultVisible, false); assert.deepEqual(page.inviteResult, {})
})

test('state action keeps the captured version and blocks replay after conflict', async () => {
  let sent, calls = 0
  const { page } = view({ transitionCampaign: async (...args) => { sent = args; calls++; return { code: 409, message: '版本已更新' } } })
  page.loading = false; page.detail = campaign('1', 'DRAFT'); page.askTransition('open'); page.detail.version = 8
  await page.confirmTransition(); await page.confirmTransition()
  assert.deepEqual(sent, ['1', 'open', 4]); assert.equal(calls, 1); assert.equal(page.transitionError, '版本已更新')
})

test('revocation captures company and version and closed rounds expose no revoke action', async () => {
  let sent
  const { page } = view({ revokeEnterprise: async (...args) => { sent = args; return { code: 409, message: '参与状态已更新' } } })
  page.loading = false; page.detail = campaign()
  const row = { companyId: '7', version: 2, status: 'ACCEPTED' }
  page.onEnterpriseRowAction('revoke', row); row.version = 3
  await page.onRevokeConfirm({ reason: '虚构测试原因' })
  assert.equal(sent[2].expectedVersion, 2); assert.equal(page.revokeError, '参与状态已更新')
  page.detail.status = 'CLOSED'; assert.deepEqual(page.enterpriseRowActions(row), [])
})

test('invalid creation form cannot create a recruitment campaign', async () => {
  let calls = 0
  const { page } = view({ createCampaign() { calls++ } }, {}, 'RecruitmentCampaignFormView.vue')
  page.$route.params = {}; page.loading = false; page.$refs.campaignForm.validate = async () => ({ valid: false })
  await page.save()
  assert.equal(calls, 0); assert.equal(page.submitting, false); assert.match(page.saveError, /必填/)
})

const validForm = () => formHelpers.campaignFormModel({ batchId: '23', campaignCode: 'UI-R1', campaignName: '虚构草稿' })

test('new route preserves current batch and list page without opening an old drawer', () => {
  const { page, routes } = view({}, {}, 'RecruitmentCampaignListView.vue')
  page.restoreQuery(); page.onToolbar('create')
  assert.equal(routes[0].path, '/admin/internship/recruitment-campaigns/new')
  assert.equal(routes[0].query.batchId, '23'); assert.equal(routes[0].query.page, '2')
})

test('reactive form saves an empty-window draft with default privacy intact', () => {
  const body = formHelpers.campaignFormBody(reactive(validForm()))
  assert.equal(body.inviteStartAt, null); assert.equal(body.enterpriseAccessEndAt, null)
  assert.deepEqual(body.applicationMaterialPolicy.allowedContactSharingModes, ['MASKED_ONLY', 'AFTER_INTERVIEW', 'AFTER_ACCEPT_INTENT'])
  assert.equal(body.teacherConfirmSlaHours, 48)
})

test('editing a name preserves exact timestamps and explicit clearing sends null', () => {
  const detail = { ...validForm(), version: 7, inviteStartAt: '2026-09-06T01:23:45.123Z', inviteEndAt: '2026-09-06T02:23:45Z' }
  const form = formHelpers.campaignFormModel(detail); form.campaignName = '更名'
  const body = formHelpers.campaignFormBody(form, detail)
  assert.equal(body.inviteStartAt, detail.inviteStartAt); assert.equal(body.expectedVersion, 7)
  form.inviteStartAt = ''; form.inviteEndAt = ''
  assert.equal(formHelpers.campaignFormBody(form, detail).inviteEndAt, null)
})

test('window pair, reversed interval and early access cutoff are rejected; overlaps are permitted', () => {
  const form = validForm(); form.inviteStartAt = '2026-09-06T08:00:00'
  assert.match(formHelpers.campaignFormErrors(form).inviteEndAt, /同时填写/)
  form.inviteEndAt = '2026-09-05T08:00:00'
  assert.match(formHelpers.campaignFormErrors(form).inviteEndAt, /早于/)
  form.inviteEndAt = '2026-09-07T08:00:00'; form.enterpriseAccessEndAt = '2026-09-06T23:00:00'
  assert.match(formHelpers.campaignFormErrors(form).enterpriseAccessEndAt, /任一/)
  form.enterpriseAccessEndAt = '2026-09-07T08:00:00'; form.positionSubmitStartAt = form.inviteStartAt; form.positionSubmitEndAt = form.inviteEndAt
  assert.deepEqual(formHelpers.campaignFormErrors(form), {})
})

test('unsupported legacy material rules survive edits without re-sending or dropping their keys', () => {
  const detail = { ...validForm(), version: 8, applicationMaterialPolicy: { requiredProfileFields: ['headline'], minItemCount: 2 } }
  const form = formHelpers.campaignFormModel(detail)
  assert.equal(formHelpers.unsupportedMaterialPolicy(detail.applicationMaterialPolicy), true)
  const body = formHelpers.campaignFormBody(form, detail)
  assert.equal('applicationMaterialPolicy' in body, false)
  assert.equal(form.applicationMaterialPolicy.minItemCount, 2)
})

test('opened campaigns and view-only users cannot save settings even via direct method calls', async () => {
  let calls = 0
  const { page } = view({ updateCampaign() { calls++ } }, {}, 'RecruitmentCampaignFormView.vue')
  page.loading = false; page.detail = campaign(); page.form = validForm()
  assert.equal(page.readonly, true); await page.save()
  page.detail.status = 'DRAFT'; page.ctx.permissionPatterns = ['internship.recruitment.view']; await page.save()
  assert.equal(page.readonly, true); assert.equal(calls, 0)
})

test('draft conflict retains edits and prevents replay with stale version', async () => {
  let calls = 0, sent
  const { page } = view({ updateCampaign: async (id, body) => { calls++; sent = { id, body }; return { code: 'DATA_CONFLICT', message: '版本已更新' } } }, {}, 'RecruitmentCampaignFormView.vue')
  page.loading = false; page.detail = { ...campaign('1', 'DRAFT'), version: 7 }; page.form = validForm()
  await page.save(); await page.save()
  assert.equal(calls, 1); assert.equal(sent.body.expectedVersion, 7); assert.equal(page.form.campaignName, '虚构草稿')
  assert.match(page.saveError, /填写内容已保留/)
})

test('double save during validation creates only one draft and returns with current batch', async () => {
  const validation = deferred(); let calls = 0
  const { page, routes } = view({ createCampaign: async () => { calls++; return ok({ id: '9', batchId: '23' }) } }, {}, 'RecruitmentCampaignFormView.vue')
  page.$route.params = {}; page.loading = false; page.form = validForm(); page.$refs.campaignForm.validate = () => validation.promise
  const first = page.save(); await page.save(); validation.resolve({ valid: true }); await first
  assert.equal(calls, 1); assert.equal(routes[0].path, '/admin/internship/recruitment-campaigns/9'); assert.equal(routes[0].query.page, '2')
})

test('a duplicate code on creation can be corrected and retried without a nonexistent detail', async () => {
  let calls = 0
  const { page } = view({ createCampaign: async () => { calls++; return { code: 409, message: '编码重复' } } }, {}, 'RecruitmentCampaignFormView.vue')
  page.$route.params = {}; page.loading = false; page.form = validForm()
  await page.save(); assert.equal(page.conflicted, false); page.form.campaignCode = 'UI-R2'; await page.save()
  assert.equal(calls, 2); assert.equal(page.saveError, '编码重复')
})

test('context change during validation cannot submit the previous draft', async () => {
  const validation = deferred(); let calls = 0
  const { page } = view({ updateCampaign() { calls++ } }, {}, 'RecruitmentCampaignFormView.vue')
  page.loading = false; page.detail = campaign('1', 'DRAFT'); page.form = validForm(); page.$refs.campaignForm.validate = () => validation.promise
  const saving = page.save(); page.$route.params.id = '2'; validation.resolve({ valid: true }); await saving
  assert.equal(calls, 0)
})

test('late settings read and late save do not navigate or replace another campaign', async () => {
  const old = deferred(), save = deferred(); let reads = 0
  const { page, options, routes } = view({ getCampaignDetail: () => ++reads === 1 ? old.promise : Promise.resolve(ok(campaign('2', 'DRAFT'))), updateCampaign: () => save.promise }, {}, 'RecruitmentCampaignFormView.vue')
  const loading = page.init(); page.$route.params.id = '2'; await page.init(); old.resolve(ok(campaign('1', 'DRAFT'))); await loading
  assert.equal(page.detail.id, '2')
  page.form = validForm(); const saving = page.save(); await Promise.resolve(); options.beforeUnmount.call(page)
  save.resolve(ok({ id: '2', batchId: '23' })); await saving
  assert.equal(routes.length, 0)
})

test('wrong batch settings deep link stops before loading or editing another batch', async () => {
  const { page } = view({ getCampaignDetail: async () => ok({ ...campaign('1', 'DRAFT'), batchId: '24' }) }, {}, 'RecruitmentCampaignFormView.vue')
  await page.init(); assert.match(page.error, /不属于当前批次/); assert.equal(page.detail, null)
})

test('actual AppForm catches blank identity, missing time endpoint and nested material length', async () => {
  const script = parse(fs.readFileSync(new URL('../src/components/common/form/AppForm.vue', import.meta.url), 'utf8')).descriptor.script.content.replace('export default', 'return')
  const options = new Function(script)()
  const { page } = view({}, {}, 'RecruitmentCampaignFormView.vue')
  page.form = validForm(); page.form.campaignCode = ''; page.form.inviteStartAt = '2026-09-06T08:00:00'; page.form.applicationMaterialPolicy.minStatementLength = -1
  const instance = { model: page.form, rules: page.formRules }
  const field = (key) => options.methods.runFieldRules.call(instance, key)
  assert.match(await field('campaignCode'), /编码/)
  assert.match(await field('inviteEndAt'), /同时填写/)
  assert.match(await field('minStatementLength'), /最低字数/)
})

test('local day boundaries carry timezone instead of shifting the recruitment window', () => {
  const form = validForm(); form.inviteStartAt = '2026-09-06T00:00:00'; form.inviteEndAt = '2026-09-06T23:59:59'
  const body = formHelpers.campaignFormBody(form)
  const start = new Date(body.inviteStartAt), end = new Date(body.inviteEndAt)
  assert.equal(start.getFullYear(), 2026); assert.equal(start.getMonth(), 8); assert.equal(start.getDate(), 6)
  assert.equal(start.getHours(), 0); assert.equal(end.getHours(), 23); assert.equal(end.getMinutes(), 59)
  assert.ok(body.inviteStartAt.endsWith('Z')); assert.ok(body.inviteEndAt.endsWith('Z'))
})

test('list restoration reads original batch and page from the detail return link', () => {
  const { page } = view({}, {}, 'RecruitmentCampaignListView.vue')
  page.restoreQuery(); assert.equal(page.batchId, '23'); assert.equal(page.page, 2)
  assert.equal(page.rowActions({ status: 'OPEN' }).some((action) => action.key === 'open'), false)
})

test('campaign list and detail templates compile after the layout changes', () => {
  for (const file of ['RecruitmentCampaignListView.vue', 'RecruitmentCampaignDetailView.vue']) {
    const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/' + file, import.meta.url), 'utf8'))
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: file }).errors, [])
  }
})

test('list uses the shared batch and preserves exact IDs and page in all object links', async () => {
  let sent
  const { page, routes } = view({ getCampaigns: async p => { sent = p; return ok({ list: [], hasMore: false }) } }, {}, 'RecruitmentCampaignListView.vue')
  page.$route.query = { batchId: '9007199254740999', page: '3', section: 'lifecycle', epStatus: 'REVOKED', epPage: '5' }
  page.restoreQuery(); await page.load()
  assert.deepEqual(sent, { batchId: '9007199254740999', page: 3, pageSize: 10 })
  assert.deepEqual(page.detailLink({ id: '9007199254740998' }).query, { batchId: '9007199254740999', page: '3', section: 'enterprises' })
  page.onToolbar('create'); assert.deepEqual(routes[0].query, { batchId: '9007199254740999', page: '3' })
  page.turnPage(4); assert.deepEqual(routes[1].query, { batchId: '9007199254740999', page: '4' })
})

test('list refuses missing batch and revoked access and clears stale results on failure', async () => {
  let calls = 0
  const { page } = view({ getCampaigns: async () => { calls++; return { code: 503, message: '当前服务不可用' } } }, {}, 'RecruitmentCampaignListView.vue')
  page.$route.query = {}; await page.load(); assert.match(page.error, /选择实习批次/); assert.equal(calls, 0)
  page.onToolbar('create'); assert.deepEqual(page.toolbarActions, [])
  page.$route.query.batchId = '23'; page.rows = [{ id: 'old' }]; page.hasMore = true
  await page.load(); assert.equal(page.error, '当前服务不可用'); assert.deepEqual(page.rows, []); assert.equal(page.hasMore, false)
  page.ctx.permissionPatterns = []; await page.load(); assert.equal(calls, 1); assert.equal(page.loading, false)
})

test('list drops responses after batch replacement or unmount and keeps pagination truthful', async () => {
  const old = deferred(); let calls = 0
  const { page, options } = view({ getCampaigns: () => ++calls === 1 ? old.promise : Promise.resolve(ok({ list: [{ id: 'new' }], hasMore: false })) }, {}, 'RecruitmentCampaignListView.vue')
  const first = page.load(); page.$route.query.batchId = '24'; await page.load(); old.resolve(ok({ list: [{ id: 'old' }], hasMore: true })); await first
  assert.equal(page.rows[0].id, 'new'); assert.equal(page.hasMore, false)
  page.page = 3; page.rows = []; assert.equal(page.paginationConf.total, 20)
  page.hasMore = true; assert.equal(page.paginationConf.total, 21)
  const pending = deferred(); const another = view({ getCampaigns: () => pending.promise }, {}, 'RecruitmentCampaignListView.vue')
  const read = another.page.load(); another.options.beforeUnmount.call(another.page); pending.resolve(ok({ list: [{ id: 'late' }], hasMore: false })); await read
  assert.deepEqual(another.page.rows, []); assert.equal(typeof options.watch.ctx.handler, 'function')
})

test('participation paging ignores unsubmitted status and request errors clear the prior queue', async () => {
  let sent
  const { page, routes } = view({ getCampaignEnterprises: async (_, p) => { sent = p; return { code: 503, message: '参与记录不可用' } } })
  page.loading = false; page.detail = campaign(); page.epFilters.status = 'REVOKED'; page.epPage = 2
  await page.loadEnterprises(); assert.equal(sent.status, 'INVITED')
  page.turnEnterprisePage(4); assert.equal(routes[0].query.epStatus, 'INVITED'); assert.equal(routes[0].query.epPage, '4')
  assert.deepEqual(page.enterpriseRows, []); assert.equal(page.epHasMore, false); assert.equal(page.epError, '参与记录不可用')
})

test('identity change clears invitation drafts and one-time results before refusing access', async () => {
  let calls = 0
  const { page } = view({ getCampaignDetail: async () => { calls++; return ok(campaign()) } })
  page.inviteResult = { inviteToken: 'synthetic-only' }; page.inviteModel.realName = '旧范围草稿'; page.companyOptions = [{ value: '1' }]
  const previous = page.contextKey; page.ctx = { ctxKey: 'other', permissionPatterns: [] }
  assert.notEqual(page.contextKey, previous); await page.init()
  assert.equal(calls, 0); assert.match(page.error, /权限/); assert.deepEqual(page.inviteResult, {}); assert.equal(page.inviteModel.realName, ''); assert.deepEqual(page.companyOptions, [])
})

test('lifecycle actions map request verbs to the actual backend target states with distinct permissions', () => {
  const { page } = view()
  page.ctx.permissionPatterns.push('internship.recruitment.close')
  const expected = { DRAFT: ['open'], OPEN: ['freeze', 'close'], FROZEN: ['close'], CLOSED: ['archive'], ARCHIVED: [] }
  for (const [status, actions] of Object.entries(expected)) {
    page.detail = campaign('1', status)
    assert.deepEqual(page.lifecycleActions.map(a => a.key), actions)
  }
  page.detail.status = 'OPEN'; page.ctx.permissionPatterns = ['internship.recruitment.view', 'internship.recruitment.manage']
  assert.deepEqual(page.lifecycleActions.map(a => a.key), ['freeze'])
  page.ctx.permissionPatterns = ['internship.recruitment.view', 'internship.recruitment.close']
  assert.deepEqual(page.lifecycleActions.map(a => a.key), ['close'])
  page.detail.status = 'CLOSED'; assert.deepEqual(page.lifecycleActions.map(a => a.key), ['archive'])
  page.ctx.permissionPatterns = ['internship.recruitment.view']; assert.deepEqual(page.lifecycleActions, [])
})
