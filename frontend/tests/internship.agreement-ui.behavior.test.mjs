import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'

function view(file, api = {}, templateApi = {}, permission = () => true, sdk = {}) {
  const script = parse(fs.readFileSync(new URL(`../src/modules/internship/views/${file}.vue`, import.meta.url), 'utf8')).descriptor.script.content
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
    .replace(/ {2}components: \{[\s\S]*?\},\r?\n/, '')
    .replace('export default', 'return')
  const batch = { selectedBatchId: '7', withBatchQuery: query => ({ ...query, batchId: '7' }) }
  const definition = new Function('agreementApi', 'agreementTemplateApi', 'useInternshipBatchStore', 'canCode', 'toast', 'fileSdk', 'normalizeUiError', 'AGREEMENT_CLAUSE', 'window', script)(api, templateApi, () => batch, permission, { success() {}, error() {} }, sdk, () => ({ userMessage: '无法读取' }), [], { __SAAS_DIRTY_FORM_GUARD__: { markSaved() {}, markDirty() {} } })
  const calls = []
  const vm = { ...definition.data(), ctx: { permissionPatterns: ['*'] }, $route: { name: 'internship-agreements', path: '/admin/internship/agreements', query: { panel: 'confirm', batchId: '7', keyword: '测试', page: '3', status: 'PENDING_ENTERPRISE' } }, $router: { push: to => calls.push(to), replace: to => calls.push(to) } }
  for (const [key, method] of Object.entries(definition.methods)) vm[key] = method.bind(vm)
  for (const [key, getter] of Object.entries(definition.computed)) Object.defineProperty(vm, key, { get: () => getter.call(vm) })
  return { vm, calls, batch }
}

test('agreement filters restore from URL and carry into the exact dossier', () => {
  const { vm, calls } = view('AgreementView')
  vm.load = () => {}
  vm.applyPanel('confirm')
  assert.equal(vm.currentPanel, 'position-apply')
  assert.equal(vm.page, 3)
  assert.equal(vm.keyword, '测试')
  vm.openDossier({ id: '9007199254740997' })
  assert.deepEqual(calls[0], { path: '/admin/internship/agreements/9007199254740997', query: { panel: 'confirm', status: 'PENDING_ENTERPRISE', keyword: '测试', page: 3, batchId: '7' } })
})

test('archive detail refresh returns to its filtered list without relying on browser history', () => {
  const { vm, calls } = view('AgreementDetailView')
  vm.$route.query = { panel: 'archive', batchId: '7', page: '2', keyword: '测试', section: 'files' }
  assert.equal(vm.activeSection, 'files')
  vm.backToList()
  assert.deepEqual(calls[0], { path: '/admin/internship/agreements', query: { panel: 'archive', batchId: '7', page: '2', keyword: '测试' } })
})

test('new agreement opens as a deep link carrying the current list context', async () => {
  const { vm, calls } = view('AgreementView')
  vm.load = () => {}; vm.applyPanel('confirm')
  await vm.openGenerate()
  assert.equal(calls[0].path, '/admin/internship/agreements/new')
  assert.equal(calls[0].query.batchId, '7'); assert.equal(calls[0].query.page, 3)
})

test('archive work queue opens eligible agreements while explicit historical filters survive detail return', () => {
  const { vm, calls } = view('AgreementView')
  vm.load = () => {}
  vm.$route.query = { panel: 'archive', batchId: '7' }
  vm.applyPanel('archive')
  assert.equal(vm.appliedFilters.status, 'EFFECTIVE')
  vm.$route.query = { panel: 'archive', batchId: '7', status: 'ARCHIVED', page: '2' }
  vm.applyPanel('archive')
  vm.openDossier({ id: '9007199254740997' })
  assert.equal(calls[0].query.status, 'ARCHIVED')
  assert.equal(calls[0].query.page, 2)
  assert.equal(calls[0].query.batchId, '7')
})

test('archive origin survives agreement filters and dossier navigation only within the same batch', () => {
  const { vm, calls } = view('AgreementView')
  const origin = '/admin/internship/archive?batchId=7&id=9007199254740999&page=2'
  vm.$route.query.returnTo = origin
  vm.openDossier({ id: '12' })
  assert.equal(vm.workspaceReturnTo, origin)
  assert.equal(calls[0].query.returnTo, origin)
  for (const invalid of ['https://outside.invalid', '/admin/internship/archive?batchId=8&id=1', '/admin/internship/agreements?batchId=7']) {
    vm.$route.query.returnTo = invalid
    assert.equal(vm.workspaceReturnTo, '')
    assert.equal(vm.listQuery().returnTo, undefined)
  }
})

test('student onboarding origin survives agreement list and detail navigation within the same batch', () => {
  const { vm, calls } = view('AgreementView')
  const origin = '/admin/internship/students/9007199254740999?batchId=7&section=placement&returnTo=%2Fadmin%2Finternship%2Finsurance%2F1%3FbatchId%3D7'
  vm.$route.query.returnTo = origin; vm.openDossier({ id: '12' })
  assert.equal(vm.workspaceReturnTo, origin); assert.equal(calls[0].query.returnTo, origin)
  for (const invalid of [origin.replace('batchId=7', 'batchId=8'), '/admin/internship/students/not-a-record?batchId=7', 'https://external.invalid' + origin]) {
    vm.$route.query.returnTo = invalid; assert.equal(vm.workspaceReturnTo, '')
  }
})

test('late filtered response cannot replace the newly selected queue', async () => {
  let firstResolve
  const first = new Promise(resolve => { firstResolve = resolve })
  let calls = 0
  const { vm } = view('AgreementView', { getAgreements: () => ++calls === 1 ? first : Promise.resolve({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }) })
  const pending = vm.load()
  await vm.load()
  firstResolve({ code: 0, data: { list: [{ id: 'old' }], total: 1 } }); await pending
  assert.equal(vm.rows[0].id, 'new')
})

test('template scope pickers retain exact IDs and grade strings in the existing payload', () => {
  const { vm } = view('AgreementTemplateFormView')
  vm.form.scopeCollegeIds = ['9007199254740997']
  vm.form.scopeMajorIds = ['22']; vm.form.scopeGrades = ['2024级']; vm.form.scopeBatchIds = ['7']
  const body = vm._buildBody()
  assert.deepEqual(body.scopeCollegeIds, ['9007199254740997'])
  assert.deepEqual(body.scopeMajorIds, ['22']); assert.deepEqual(body.scopeGrades, ['2024级']); assert.deepEqual(body.scopeBatchIds, ['7'])
})

const ok = data => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }

test('list return and export retain applied filters while the search input is being edited', async () => {
  const exports = []
  const { vm, calls } = view('AgreementView', { exportAgreements: async query => { exports.push(query); return ok({}) } })
  vm.load = () => {}; vm.applyPanel('confirm')
  vm.keyword = '尚未查询'; vm.statusFilter = 'DRAFT'
  vm.openDossier({ id: '1' }); await vm.exportFn()
  assert.equal(calls[0].query.keyword, '测试')
  assert.equal(calls[0].query.status, 'PENDING_ENTERPRISE')
  assert.equal(exports[0].keyword, '测试')
})

test('template loading failure keeps generation unavailable and offers a successful retry', async () => {
  let failed = true
  const { vm } = view('AgreementView', {}, {
    getEnabledOptions: async () => failed ? { code: 503001, message: '模板服务暂不可用' } : ok([{ id: '9', isDefault: true }]),
    previewTemplate: async () => ok({ renderedBody: '所选学生的真实正文' })
  })
  vm.genForm.internshipId = '3'
  await vm.refreshTemplateOptions()
  assert.equal(vm.templateError, '模板服务暂不可用')
  assert.equal(vm.generationReady, false)
  failed = false; await vm.retryPreview()
  assert.equal(vm.generationReady, true)
  assert.equal(vm.previewText, '所选学生的真实正文')
})

test('a late template response cannot replace the newly selected student templates', async () => {
  const pending = deferred()
  const { vm } = view('AgreementView', {}, {
    getEnabledOptions: ({ internshipId }) => internshipId === 'old' ? pending.promise : Promise.resolve(ok([{ id: 'new-template' }])),
    previewTemplate: async id => ok({ renderedBody: id })
  })
  vm.genForm.internshipId = 'old'; const first = vm.refreshTemplateOptions()
  vm.genForm.internshipId = 'new'; await vm.refreshTemplateOptions()
  pending.resolve(ok([{ id: 'old-template' }])); await first
  assert.equal(vm.effectiveTemplateId, 'new-template')
  assert.equal(vm.previewText, 'new-template')
})

test('a late preview cannot replace a more recently selected template', async () => {
  const pending = deferred()
  const { vm } = view('AgreementView', {}, {
    previewTemplate: id => id === 'old' ? pending.promise : Promise.resolve(ok({ renderedBody: '新版正文' }))
  })
  vm.genForm = { internshipId: '3', templateId: 'old' }; vm.templatesReady = true
  const first = vm.loadPreview()
  vm.genForm.templateId = 'new'; await vm.loadPreview()
  pending.resolve(ok({ renderedBody: '旧版正文' })); await first
  assert.equal(vm.previewText, '新版正文')
})

test('empty eligible templates retain the existing system-body generation contract', async () => {
  const { vm } = view('AgreementView', {}, { getEnabledOptions: async () => ok([]) })
  vm.genForm.internshipId = '3'; await vm.refreshTemplateOptions()
  assert.equal(vm.templatesReady, true)
  assert.equal(vm.effectiveTemplateId, '')
  assert.equal(vm.previewText, '')
  assert.equal(vm.generationReady, true)
})

test('generation opens the returned agreement ID directly and prevents duplicate clicks', async () => {
  const pending = deferred(), writes = []
  const { vm, calls } = view('AgreementView', { generate: body => { writes.push(body); return pending.promise } })
  vm.$route.name = 'internship-agreement-new'
  vm.applyPanel('confirm'); vm.genForm = { internshipId: '9007199254740997', templateId: '9' }
  vm.templatesReady = true; vm.previewText = '已核对正文'
  const first = vm.submitGenerate(); await vm.submitGenerate()
  assert.equal(writes.length, 1)
  assert.deepEqual(writes[0], { internshipId: '9007199254740997', templateId: '9' })
  pending.resolve(ok({ id: '9007199254740998', status: 'DRAFT' })); await first
  assert.equal(calls[0].path, '/admin/internship/agreements/9007199254740998')
  assert.equal(calls[0].query.keyword, '测试')
  assert.equal(vm.genDlg.submitting, false)
})

test('generation failure preserves the object and template with inline error', async () => {
  const { vm, calls } = view('AgreementView', { generate: async () => ({ code: 409001, message: '已有进行中的协议' }) })
  vm.genForm = { internshipId: '3', templateId: '9' }; vm.templatesReady = true; vm.previewText = '原正文'
  await vm.submitGenerate()
  assert.equal(vm.generationError, '已有进行中的协议')
  assert.equal(vm.genForm.internshipId, '3')
  assert.equal(vm.previewText, '原正文')
  assert.equal(calls.length, 0)
})

test('switching batch invalidates an in-flight generation navigation', async () => {
  const pending = deferred()
  const { vm, batch, calls } = view('AgreementView', { generate: () => pending.promise })
  vm.genForm.internshipId = '3'; vm.templatesReady = true
  const first = vm.submitGenerate()
  batch.selectedBatchId = '8'; vm.resetGeneration()
  pending.resolve(ok({ id: 'old-batch-agreement' })); await first
  assert.equal(calls.length, 0)
  assert.equal(vm.genForm.internshipId, '')
})

test('agreement deep links reject mismatched batch records and clear previous facts', async () => {
  const { vm } = view('AgreementDetailView', { getDetail: async () => ok({ id: '5', batchId: '8' }) })
  vm.$route.params = { id: '5' }; vm.detail = { id: 'old' }
  await vm.load()
  assert.equal(vm.detail, null)
  assert.match(vm.error, /不属于当前批次/)
  assert.equal(vm.loading, false)
})

test('school confirmation uses its dedicated permission rather than general management', () => {
  for (const allowed of [true, false]) {
    const { vm } = view('AgreementDetailView', {}, {}, (_ctx, code) => code === 'internship.agreement.schoolConfirm' && allowed)
    vm.loading = false; vm.detail = { studentName: '测试学生', status: 'PENDING_SCHOOL' }
    vm.confirmAct('school')
    assert.equal(vm.cd.visible, allowed)
  }
})

test('template list routes and export preserve applied filters rather than unsent search edits', async () => {
  const exports = []
  const { vm, calls } = view('InternshipAgreementTemplateListView', {}, { exportTemplates: async p => { exports.push(p); return ok({}) } })
  vm.appliedFilters = { keyword: '通用', status: 'ENABLED', category: '三方协议' }; vm.page = 3
  vm.filters.keyword = '未查询'
  vm.openDetail({ id: '9007199254740997' }); await vm.exportFn()
  assert.equal(calls[0].query.templateKeyword, '通用')
  assert.equal(calls[0].query.templatePage, 3)
  assert.equal(calls[0].query.keyword, '测试')
  assert.equal(exports[0].keyword, '通用')
})

test('late template-list response cannot replace a newer query and failures clear old rows', async () => {
  const pending = deferred(); let requests = 0
  const { vm } = view('InternshipAgreementTemplateListView', {}, {
    getTemplates: () => ++requests === 1 ? pending.promise : Promise.resolve(ok({ list: [{ id: 'new' }], total: 1 }))
  })
  const first = vm.load(); await vm.load()
  pending.resolve(ok({ list: [{ id: 'old' }], total: 1 })); await first
  assert.equal(vm.rows[0].id, 'new')
  const failed = view('InternshipAgreementTemplateListView', {}, { getTemplates: async () => { throw new Error('暂不可用') } }).vm
  failed.rows = [{ id: 'old' }]; await failed.load()
  assert.equal(failed.error, '暂不可用'); assert.deepEqual(failed.rows, []); assert.equal(failed.loading, false)
})

test('variable dictionary failure blocks template saving until retry succeeds', async () => {
  let failed = true
  const { vm } = view('AgreementTemplateFormView', {}, { getVariablePresets: async () => failed ? { code: 503001, message: '变量不可用' } : ok([{ key: 'studentName', label: '学生姓名', example: '示例' }]) })
  vm.$route.params = {}; await vm.loadVariables()
  assert.equal(vm.variablesReady, false); assert.equal(vm.variablesError, '变量不可用')
  failed = false; await vm.loadVariables()
  vm.form.body = '实习学生：{{studentName}}'
  assert.equal(vm.variablesReady, true)
  assert.equal(vm._buildBody().variables[0].key, 'studentName')
})

test('template creation opens its returned draft and carries both list contexts', async () => {
  const writes = []
  const { vm, calls } = view('AgreementTemplateFormView', {}, { createTemplate: async body => { writes.push(body); return ok({ id: '9007199254740997' }) } })
  vm.$route.params = {}; vm.variablesReady = true; vm.form.name = '三方模板'
  vm.$route.query.templateKeyword = '通用'
  vm.$refs = { tplForm: { validate: async () => ({ valid: true }) } }
  await vm.onSubmit()
  assert.equal(writes.length, 1)
  assert.equal(calls[0].path, '/admin/internship/agreement-templates/9007199254740997')
  assert.equal(calls[0].query.templateKeyword, '通用'); assert.equal(calls[0].query.keyword, '测试')
})

test('template form save error keeps input and prevents duplicate validation submissions', async () => {
  const pending = deferred(); let writes = 0
  const { vm, calls } = view('AgreementTemplateFormView', {}, { createTemplate: async () => { writes++; return { code: 409001, message: '模板已更新' } } })
  vm.$route.params = {}; vm.variablesReady = true; vm.form.name = '保留内容'
  vm.$refs = { tplForm: { validate: () => pending.promise } }
  const first = vm.onSubmit(); await vm.onSubmit()
  pending.resolve({ valid: true }); await first
  assert.equal(writes, 1); assert.equal(vm.form.name, '保留内容')
  assert.equal(vm.saveError, '模板已更新'); assert.equal(calls.length, 0)
})

test('an old template load cannot repopulate the new-template form', async () => {
  const pending = deferred()
  const { vm } = view('AgreementTemplateFormView', {}, { getTemplateDetail: () => pending.promise })
  vm.$route.params = { id: 'old' }; const first = vm.init()
  vm.$route.params = {}; await vm.init()
  pending.resolve(ok({ id: 'old', name: '旧模板' })); await first
  assert.equal(vm.form.name, ''); assert.equal(vm.detail, null)
})

test('template lifecycle remains available in detail and submits one real command', async () => {
  const pending = deferred(); const writes = []
  const { vm } = view('AgreementTemplateDetailView', {}, {
    setStatus: (id, body) => { writes.push({ id, body }); return pending.promise },
    getTemplateDetail: async () => ok({ id: '5', status: 'ENABLED' })
  })
  vm.$route.params = { id: '5' }; vm.loading = false; vm.detail = { id: '5', name: '通用模板', status: 'DRAFT' }
  vm.askStatus('ENABLE'); const first = vm.onConfirm(); await vm.onConfirm()
  pending.resolve(ok({ id: '5' })); await first
  assert.deepEqual(writes, [{ id: '5', body: { action: 'ENABLE', reason: '' } }])
  assert.equal(vm.confirm.visible, false); assert.equal(vm.detail.status, 'ENABLED')
})

test('template default setting retains its category-replacement explanation and exact target', async () => {
  const calls = []
  const { vm } = view('AgreementTemplateDetailView', {}, {
    setDefault: async (id, on) => { calls.push({ id, on }); return ok({}) },
    getTemplateDetail: async () => ok({ id: '5', status: 'ENABLED', isDefault: true })
  })
  vm.$route.params = { id: '5' }; vm.detail = { id: '5', name: '通用模板', status: 'ENABLED' }
  vm.askDefault(true)
  assert.match(vm.confirm.message, /同类型原默认会被替换/)
  await vm.onConfirm()
  assert.deepEqual(calls, [{ id: '5', on: true }]); assert.equal(vm.detail.isDefault, true)
})

test('template insertion replaces selection and restores the cursor without losing surrounding text', () => {
  const { vm } = view('AgreementTemplateFormView')
  vm.$route.params = {}; vm.form.body = '甲方：学校；乙方：企业'
  const selections = []
  vm.$refs = { bodyInput: { $el: { querySelector: () => ({ focus() {}, setSelectionRange: (...args) => selections.push(args) }) } } }
  vm.$nextTick = fn => fn()
  vm.rememberBodySelection({ target: { tagName: 'TEXTAREA', selectionStart: 3, selectionEnd: 5 } })
  vm.onPickVariable('{{schoolName}}')
  assert.equal(vm.form.body, '甲方：{{schoolName}}；乙方：企业')
  assert.deepEqual(selections.at(-1), [17, 17])
  vm.onPickVariable('{{studentName}}')
  assert.equal(vm.form.body, '甲方：{{schoolName}}{{studentName}}；乙方：企业')
})

test('clause insertion separates paragraphs and read-only or busy forms keep their input', () => {
  const { vm } = view('AgreementTemplateFormView')
  vm.$route.params = {}; vm.$refs = {}; vm.$nextTick = fn => fn()
  vm.form.body = '首段尾段'; vm.bodySelection = { start: 2, end: 2 }
  vm.onPickClause('新条款')
  assert.equal(vm.form.body, '首段\n新条款\n尾段')
  vm.submitting = true; vm.onPickVariable('{{schoolName}}')
  assert.equal(vm.form.body, '首段\n新条款\n尾段')
  vm.submitting = false; vm.ctx.permissionPatterns = null; vm.onPickClause('禁止插入')
  assert.equal(vm.form.body, '首段\n新条款\n尾段')
})

test('late variable dictionary response cannot replace a successful retry', async () => {
  const pending = deferred(); let calls = 0
  const { vm } = view('AgreementTemplateFormView', {}, { getVariablePresets: () => ++calls === 1 ? pending.promise : Promise.resolve(ok([{ key: 'schoolName' }])) })
  const first = vm.loadVariables(); await vm.loadVariables()
  pending.resolve({ code: 503001, message: '旧请求失败' }); await first
  assert.equal(vm.variablesReady, true); assert.equal(vm.variablesError, '')
  assert.equal(vm.variablePresets[0].key, 'schoolName')
})

function enterpriseSigning(api) {
  const result = view('AgreementDetailView', api)
  Object.assign(result.vm, { loading: false, detail: { id: '5', status: 'PENDING_ENTERPRISE', version: 4 }, entForm: { confirmBy: '测试经办人', fileId: 'old-file' } })
  result.vm.entFile = { fileId: 'old-file', readyForBusiness: true, canPreview: true }
  result.vm.$route.params = { id: '5' }
  return result
}

test('agreement attachment upload cannot bind a late file to a different dossier', async () => {
  const pending = deferred()
  const { vm } = enterpriseSigning({ uploadAttachment: () => pending.promise })
  const event = { target: { files: [{ name: '签署件.pdf' }], value: 'picked' } }
  const first = vm.onEntFile(event)
  vm.loadTicket++; vm.$route.params.id = '6'; vm.detail = { id: '6', status: 'PENDING_ENTERPRISE' }
  vm.entForm = { confirmBy: '下一对象', fileId: '' }; vm.uploadingFile = false
  pending.resolve(ok({ fileId: 'late-file' })); await first
  assert.deepEqual(vm.entForm, { confirmBy: '下一对象', fileId: '' })
  assert.equal(vm.entAttachName, ''); assert.equal(event.target.value, '')
})

test('failed scan replacement preserves the old selection and can be retried', async () => {
  const { vm } = enterpriseSigning({ uploadAttachment: async () => { throw new Error('上传中断') } })
  const event = { target: { files: [{ name: '新扫描件.pdf' }], value: 'picked' } }
  await vm.onEntFile(event)
  assert.equal(vm.entForm.fileId, 'old-file'); assert.equal(vm.entForm.confirmBy, '测试经办人')
  assert.match(vm.entError, /上传中断.*原材料已保留/); assert.equal(vm.uploadingFile, false)
  assert.equal(event.target.value, '')
})

test('enterprise confirmation submits once with the current version and keeps inputs on conflict', async () => {
  const pending = deferred(); const writes = []
  const { vm } = enterpriseSigning({ enterpriseConfirm: (id, body) => { writes.push({ id, body }); return pending.promise } })
  const first = vm.submitEnterprise(); await vm.submitEnterprise()
  pending.resolve({ code: 409001, message: '协议版本已变化，请核对' }); await first
  assert.deepEqual(writes, [{ id: '5', body: { confirmBy: '测试经办人', fileId: 'old-file', expectedVersion: 4 } }])
  assert.equal(vm.detail.version, 4); assert.equal(vm.entForm.fileId, 'old-file')
  assert.match(vm.entError, /协议版本已变化.*扫描件已保留/); assert.equal(vm.entSubmitting, false)
})

test('uploading or missing management permission prevents enterprise confirmation', async () => {
  let writes = 0
  const { vm } = enterpriseSigning({ enterpriseConfirm: async () => { writes++; return ok({}) } })
  vm.uploadingFile = true; await vm.submitEnterprise()
  vm.uploadingFile = false; vm.ctx.permissionPatterns = null; await vm.submitEnterprise()
  assert.equal(writes, 0)
})

test('late enterprise confirmation cannot reload the newly opened dossier', async () => {
  const pending = deferred(); let reloads = 0
  const { vm } = enterpriseSigning({ enterpriseConfirm: () => pending.promise })
  vm.load = async () => { reloads++ }
  const first = vm.submitEnterprise()
  vm.$route.params.id = '6'; vm.loadTicket++
  pending.resolve(ok({ status: 'PENDING_SCHOOL' })); await first
  assert.equal(reloads, 0)
})

test('agreement confirmation uses an explicit command and the reviewed version for every action', async () => {
  for (const [kind, status, method] of [['issue', 'DRAFT', 'issue'], ['school', 'PENDING_SCHOOL', 'schoolConfirm'], ['archive', 'EFFECTIVE', 'archive'], ['reject', 'PENDING_STUDENT', 'reject'], ['void', 'DRAFT', 'voidAgreement']]) {
    const writes = []; let reloads = 0
    const { vm } = enterpriseSigning({ [method]: async (id, body) => { writes.push({ id, body }); return ok({}) } })
    vm.detail.status = status; vm.load = async () => { reloads++ }
    vm.confirmAct(kind); await vm.onConfirm({ reason: '验收测试原因' })
    assert.equal(writes.length, 1); assert.equal(writes[0].id, '5')
    assert.equal(writes[0].body.expectedVersion, 4); assert.equal(reloads, 1)
    assert.equal(vm.cd.visible, false); assert.equal(vm.actionSubmitting, false)
  }
})

test('unknown or closed agreement confirmation cannot fall through to void', async () => {
  let writes = 0
  const { vm } = enterpriseSigning({ voidAgreement: async () => { writes++; return ok({}) } })
  vm.confirmAct('unknown'); await vm.onConfirm()
  assert.equal(vm.cd.visible, false); assert.equal(writes, 0)
  vm.pendingKind = 'void'; await vm.onConfirm()
  assert.equal(writes, 0)
})

test('agreement changes after opening a confirmation require a fresh review', async () => {
  let writes = 0
  const { vm } = enterpriseSigning({ schoolConfirm: async () => { writes++; return ok({}) } })
  vm.detail.status = 'PENDING_SCHOOL'; vm.confirmAct('school')
  vm.detail.version = 5; await vm.onConfirm()
  assert.equal(writes, 0); assert.match(vm.actionError, /重新核对/)
})

test('a failed agreement command preserves its dialog and releases busy state without duplicate writes', async () => {
  const pending = deferred(); let writes = 0
  const { vm } = enterpriseSigning({ reject: () => { writes++; return pending.promise } })
  vm.confirmAct('reject'); const first = vm.onConfirm({ reason: '需要重新核对扫描件' })
  await vm.onConfirm({ reason: '需要重新核对扫描件' })
  pending.resolve({ code: 409001, message: '协议已更新，请重新核对' }); await first
  assert.equal(writes, 1); assert.equal(vm.cd.visible, true)
  assert.equal(vm.detail.version, 4); assert.equal(vm.pendingTarget.version, 4)
  assert.equal(vm.actionError, '协议已更新，请重新核对'); assert.equal(vm.actionSubmitting, false)
})

test('a late agreement action cannot refresh another dossier', async () => {
  const pending = deferred(); let reloads = 0
  const { vm } = enterpriseSigning({ issue: () => pending.promise })
  vm.detail.status = 'DRAFT'; vm.load = async () => { reloads++ }
  vm.confirmAct('issue'); const first = vm.onConfirm()
  vm.$route.params.id = '6'; vm.loadTicket++
  pending.resolve(ok({ status: 'PENDING_STUDENT' })); await first
  assert.equal(reloads, 0)
})

test('internal confirmation cannot start on drafts and network failure is recoverable', async () => {
  let writes = 0
  const { vm } = enterpriseSigning({ startEsign: async () => { writes++; throw new Error('服务暂不可用') } })
  vm.detail.esignStatus = 'NONE'; vm.detail.status = 'DRAFT'
  await vm.startEsign(); assert.equal(writes, 0)
  vm.detail.status = 'PENDING_STUDENT'; await vm.startEsign()
  assert.equal(writes, 1); assert.equal(vm.actionError, '服务暂不可用')
  assert.equal(vm.actionSubmitting, false)
})

test('PDF failure releases the download button and leaves the dossier intact', async () => {
  const { vm } = enterpriseSigning({ exportAgreementPdf: async () => { throw new Error('PDF 服务暂不可用') } })
  await vm.downloadPdf()
  assert.equal(vm.pdfLoading, false); assert.equal(vm.pdfError, 'PDF 服务暂不可用')
  assert.equal(vm.detail.id, '5'); assert.equal(vm.entForm.fileId, 'old-file')
})

test('enterprise signing rejects unread, unsafe and mismatched materials', async () => {
  let writes = 0
  const { vm } = enterpriseSigning({ enterpriseConfirm: async () => { writes++; return ok({}) } })
  for (const file of [null, { fileId: 'old-file', readyForBusiness: false, canPreview: true }, { fileId: 'other-file', readyForBusiness: true, canPreview: true }]) {
    vm.entFile = file; await vm.submitEnterprise()
    assert.equal(writes, 0); assert.match(vm.entError, /安全可用/)
  }
})

test('late enterprise material metadata cannot overwrite a new dossier', async () => {
  const pending = deferred()
  const { vm } = view('AgreementDetailView', {}, {}, () => true, { metadata: () => pending.promise })
  vm.$route.params = { id: '5' }; vm.detail = { id: '5' }; vm.entForm.fileId = 'material-5'
  const first = vm.loadEnterpriseFile()
  vm.loadTicket++; vm.$route.params.id = '6'; vm.entForm.fileId = 'material-6'; vm.entFile = null
  pending.resolve({ fileId: 'material-5', readyForBusiness: true, canPreview: true }); await first
  assert.equal(vm.entFile, null)
})
