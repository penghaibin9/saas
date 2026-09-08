import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { isConflict } from '../src/modules/internship/composables/conflictGuard.js'
import { getVisibleNavPlan } from '../src/config/navPlan.js'
import { workspaceCurrentPage, workspacePages } from '../src/components/workspace/teacherWorkspace.js'

const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/ScoreView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/ {2}components: \{[\s\S]*?AppTextarea, ActionReceipt, AppPagination, ScoreAppealWorkspace \},/, '').replace('export default', 'return')
function setup(api = {}, permission = () => true, files = {}) {
  const def = new Function('scoreApi', 'canCode', 'toast', 'isConflict', 'fileSdk', 'window', script)(api, permission, { success() {}, error() {}, info() {} }, isConflict, files, { addEventListener() {}, removeEventListener() {}, confirm: () => false })
  const targets = []
  const vm = { ...def.data(), ctx: {}, batchStore: { selectedBatchId: '1', batchStatus: 'DRAFT', withBatchQuery: q => ({ ...q, batchId: '1' }) }, $route: { query: {} }, $router: { replace: t => targets.push(t), push: t => targets.push(t) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) if (key !== 'batchStore') Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, targets }
}
const config = () => ({ checkinWeight: 20, weeklyWeight: 20, monthlyWeight: 20, enterpriseWeight: 20, schoolWeight: 20, passLine: 60, scope: 'TENANT_DEFAULT', configId: '9007199254740999' })

test('score workspace template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'ScoreView.vue', id: 'score' }).errors, [])
})

test('formal appeal menu opens the appeal queue and its object stays in the same shared-shell page', () => {
  const pages = workspacePages(getVisibleNavPlan({ permissionPatterns: ['*'] }).find(group => group.key === 'internship').children)
  const menu = pages.find(page => page.title === '成绩申诉')
  const { vm, targets } = setup()
  let appealReads = 0
  vm.loadAppeals = () => appealReads++
  vm.load = () => assert.fail('appeal menu must not load the score list')
  vm.$route.query = Object.fromEntries(new URL(menu.path, 'https://local.invalid').searchParams)
  vm.applyStageFromRoute()
  assert.equal(appealReads, 1)
  assert.equal(vm.pageTitle, '成绩申诉')
  vm.openAppeal({ id: '9007199254740999' })
  vm.$route.query = targets[0].query
  assert.equal(vm.pageTitle, '申诉办理')
  assert.equal(workspaceCurrentPage(pages, `/admin/internship/scores?${new URLSearchParams(vm.$route.query)}`).id, menu.id)
  vm.closeAppeal()
  vm.$route.query = targets[1].query
  assert.equal(vm.pageTitle, '成绩申诉')
})

test('score and rule headings identify the current task', () => {
  const { vm } = setup()
  assert.equal(vm.pageTitle, '综合成绩')
  vm.$route.query = { stage: 'config' }
  assert.equal(vm.pageTitle, '评分规则')
  vm.$route.query = { stage: 'overview' }
  selectScore(vm)
  assert.equal(vm.pageTitle, '成绩核对 · 测试学生')
})

test('rules are read and saved for the selected batch without copying default-scope metadata', async () => {
  const writes = [], reads = []
  const { vm } = setup({ getConfig: async q => { reads.push(q); return { code: 0, data: config() } }, saveConfig: async body => { writes.push(body); return { code: 0 } } })
  await vm.loadConfig(); await vm.saveConfig()
  assert.deepEqual(reads, [{ batchId: '1' }, { batchId: '1' }])
  assert.deepEqual(writes, [{ batchId: '1', passLine: 60, checkinWeight: 20, weeklyWeight: 20, monthlyWeight: 20, enterpriseWeight: 20, schoolWeight: 20 }])
})

test('missing, failed, active-batch and forbidden rules cannot be saved', async () => {
  const { vm } = setup({ getConfig: async () => ({ code: 1, message: '读取失败' }), saveConfig: () => assert.fail('rules must be loaded and editable') })
  await vm.loadConfig(); await vm.saveConfig(); assert.equal(vm.cfgLoaded, false); assert.equal(vm.cfgError, '读取失败'); assert.deepEqual(vm.cfg, {})
  vm.cfg = config(); vm.cfgLoaded = true; vm.cfgError = ''; vm.batchStore.batchStatus = 'ACTIVE'; await vm.saveConfig()
  vm.batchStore.batchStatus = 'DRAFT'; vm.canBtn = () => false; await vm.saveConfig()
})

test('weight validation and failed save keep the entered draft', async () => {
  let calls = 0
  const { vm } = setup({ saveConfig: async () => { calls++; return { code: 1, message: '保存失败' } } })
  vm.cfg = config(); vm.cfgLoaded = true; vm.cfg.checkinWeight = 20.5; await vm.saveConfig(); assert.match(vm.cfgSaveError, /整数/)
  vm.cfg.checkinWeight = 21; await vm.saveConfig(); assert.match(vm.cfgSaveError, /之和/)
  vm.cfg.checkinWeight = 20; vm.cfg.passLine = ''; await vm.saveConfig(); assert.match(vm.cfgSaveError, /及格线/)
  vm.cfg.passLine = 65; await vm.saveConfig(); assert.equal(calls, 1); assert.equal(vm.cfg.passLine, 65); assert.equal(vm.cfgSaveError, '保存失败')
})

test('duplicate save is blocked and an old save cannot overwrite another batch', async () => {
  let finish, calls = 0
  const { vm } = setup({ saveConfig: () => { calls++; return new Promise(r => { finish = r }) }, getConfig: () => assert.fail('old success cannot reload') })
  vm.cfg = config(); vm.cfgLoaded = true
  const pending = vm.saveConfig(); await vm.saveConfig(); assert.equal(calls, 1)
  vm.batchStore.selectedBatchId = '2'; vm.cfg = { passLine: 70 }; finish({ code: 0 }); await pending
  assert.equal(vm.cfg.passLine, 70)
})

test('late rules cannot populate a changed batch or an unmounted page', async () => {
  let finish
  const { vm, def } = setup({ getConfig: () => new Promise(r => { finish = r }) })
  const first = vm.loadConfig(); vm.batchStore.selectedBatchId = '2'; finish({ code: 0, data: config() }); await first; assert.equal(vm.cfgLoaded, false)
  const second = vm.loadConfig(); def.beforeUnmount.call(vm); finish({ code: 0, data: config() }); await second; assert.deepEqual(vm.cfg, {})
})

test('deep links restore explicit empty filters and keep batch, keyword and page', () => {
  const { vm, targets } = setup(); vm.load = () => {}; vm.loadAppeals = () => {}
  vm.$route.query = { stage: 'review', status: '', incompleteOnly: '', keyword: '测试学生', page: '3' }; vm.applyStageFromRoute()
  assert.equal(vm.statusFilter, ''); assert.equal(vm.missingOnly, ''); assert.equal(vm.page, 3)
  vm.setQueue('config'); assert.equal(targets[0].query.page, '3'); assert.equal(targets[0].query.keyword, '测试学生'); assert.equal(targets[0].query.batchId, '1')
  vm.$route.query = { stage: 'appeal', appealPage: '2' }; vm.applyStageFromRoute(); assert.equal(vm.activeArea, 'appeal'); assert.equal(vm.appealsPage, 2)
})

test('appeal failures remain errors and pagination requests the selected page', async () => {
  let params
  const { vm } = setup({ getAppeals: async q => { params = q; return { code: 1, message: '申诉读取失败' } } })
  vm.appealsPage = 3; await vm.loadAppeals(); assert.deepEqual(params, { batchId: '1', page: 3, pageSize: 20 }); assert.equal(vm.appealsError, '申诉读取失败')
  vm.canBtn = () => false; params = null; await vm.loadAppeals(); assert.equal(params, null); assert.match(vm.appealsError, /权限/)
})

test('late list and appeal responses cannot overwrite a newer request', async () => {
  const lists = [], appeals = []
  const { vm } = setup({ getScores: () => new Promise(r => lists.push(r)), getAppeals: () => new Promise(r => appeals.push(r)) })
  const first = vm.load(), second = vm.load(), appeal1 = vm.loadAppeals(), appeal2 = vm.loadAppeals()
  lists[1]({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }); appeals[1]({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }); await second; await appeal2
  lists[0]({ code: 0, data: { list: [{ id: 'old' }], total: 1 } }); appeals[0]({ code: 0, data: { list: [{ id: 'old' }], total: 1 } }); await first; await appeal1
  assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.appeals[0].id, 'new')
})

test('appeal object deep link preserves list context and return removes only the object', () => {
  const { vm, targets } = setup(); vm.$route.query = { stage: 'appeal', appealPage: '3', keyword: '测试学生', status: 'PUBLISHED', page: '2' }
  vm.openAppeal({ id: '9007199254740999' }); assert.equal(targets[0].query.appealId, '9007199254740999'); assert.equal(targets[0].query.appealPage, '3')
  vm.$route.query = targets[0].query; vm.closeAppeal(); assert.equal(targets[1].query.appealId, undefined); assert.equal(targets[1].query.page, '2'); assert.equal(targets[1].query.keyword, '测试学生'); assert.equal(targets[1].query.batchId, '1')
})

const scoreRecord = (extra = {}) => ({ id: '9007199254740999', internId: '9007199254740888', studentName: '测试学生', version: 2, status: 'PENDING_REVIEW', incomplete: false, totalScore: 80, sourceManifest: { facts: { internship: { batchId: '1' } } }, manualAdjustments: { checkin: 0, weekly: 0, monthly: 0, enterprise: 0, school: 0 }, ...extra })
function selectScore(vm, mode = 'detail', extra = {}) { vm.panel = { visible: true, mode, rowId: scoreRecord().id, loading: false, error: '', data: scoreRecord(extra), submitting: false }; if (mode === 'edit') vm.restoreCompute() }

test('score workspace deep links preserve filters and return to the originating appeal', () => {
  const { vm, targets } = setup(); vm.$route.query = { keyword: '测试学生', status: 'WITHDRAWN', page: '2', stage: 'appeal', appealPage: '3' }
  vm.openAppealScore({ id: '99', currentScore: { id: scoreRecord().id } }); assert.equal(targets[0].query.id, scoreRecord().id); assert.equal(targets[0].query.fromAppeal, '99')
  vm.$route.query = targets[0].query; vm.closePanel(); assert.equal(targets[1].query.appealId, '99'); assert.equal(targets[1].query.appealPage, '3'); assert.equal(targets[1].query.page, '2'); assert.equal(targets[1].query.id, undefined)
})

test('compute details load by ID with original version, adjustments and evidence intact', async () => {
  const { vm } = setup({ getDetail: async () => ({ code: 0, data: scoreRecord({ adjustmentReason: '原始调分原因', adjustmentEvidenceFileIds: ['9007199254740777'], manualAdjustments: { weekly: 3 } }) }) })
  await vm.openDetailById(scoreRecord().id, 'edit'); assert.equal(vm.computeVersion, 2); assert.equal(vm.cForm.internshipId, '9007199254740888'); assert.equal(vm.cForm.manualAdjustments.weekly, 3); assert.equal(vm.cForm.adjustmentReason, '原始调分原因'); assert.deepEqual(vm.cForm.evidenceFileIds, ['9007199254740777']); assert.equal(vm.computeDirty, false)
})

test('score detail rejects another batch and scopes a legacy record through the current page', async () => {
  const { vm } = setup({ getDetail: async () => ({ code: 0, data: scoreRecord({ sourceManifest: { facts: { internship: { batchId: '2' } } } }) }) })
  await vm.openDetailById(scoreRecord().id); assert.equal(vm.panel.data, null); assert.match(vm.panel.error, /当前批次/)
  const { vm: legacy } = setup({ getDetail: async () => ({ code: 0, data: scoreRecord({ sourceManifest: {} }) }), getScores: async () => ({ code: 0, data: { list: [scoreRecord()] } }) })
  await legacy.openDetailById(scoreRecord().id); assert.equal(legacy.panel.data.id, scoreRecord().id)
})

test('late score detail or evidence upload cannot populate another workspace', async () => {
  let finishDetail, finishUpload
  const { vm } = setup({ getDetail: () => new Promise(r => { finishDetail = r }), uploadEvidence: () => new Promise(r => { finishUpload = r }) })
  const oldDetail = vm.openDetailById(scoreRecord().id); vm.resetPanel(); finishDetail({ code: 0, data: scoreRecord() }); await oldDetail; assert.equal(vm.panel.data, null)
  selectScore(vm, 'edit'); const upload = vm.uploadAdjustmentEvidence({ target: { files: [{ size: 1 }], value: 'file' } }); vm.resetPanel(); finishUpload({ code: 0, data: { id: 'file-8' } }); await upload; assert.deepEqual(vm.cForm.evidenceFileIds, [])
})

test('compute blocks missing scope, permission, active upload, invalid delta and missing evidence', async () => {
  const { vm } = setup({ compute: () => assert.fail('invalid compute must not write') }); selectScore(vm, 'edit')
  vm.batchStore.selectedBatchId = ''; await vm.submitCompute(false); vm.batchStore.selectedBatchId = '1'
  vm.cForm.uploading = true; await vm.submitCompute(false); vm.cForm.uploading = false
  vm.cForm.manualAdjustments.weekly = 1.2; await vm.submitCompute(false); assert.match(vm.panelError, /整数/)
  vm.cForm.manualAdjustments.weekly = 2; vm.cForm.adjustmentReason = '足够长的人工调分理由'; await vm.submitCompute(false); assert.match(vm.panelError, /依据文件/)
  vm.canBtn = () => false; await vm.submitCompute(false)
})

test('compute conflict preserves old input/version and does not silently replay', async () => {
  const calls = []
  const { vm } = setup({ compute: async body => { calls.push(body); return { code: 409001, message: '来源已变化' } }, getDetail: async () => ({ code: 0, data: scoreRecord({ version: 4 }) }) }); selectScore(vm, 'edit')
  vm.cForm.manualAdjustments.weekly = 2; vm.cForm.adjustmentReason = '我的人工调整依据'; vm.cForm.evidenceFileIds = ['123']
  await vm.submitCompute(false); await vm.submitCompute(false); assert.equal(calls.length, 1); assert.equal(calls[0].expectedVersion, 2); assert.equal(vm.computeVersion, 2); assert.equal(vm.panel.data.version, 4); assert.equal(vm.cForm.manualAdjustments.weekly, 2); assert.equal(vm.computeConflict, true)
  vm.restoreCompute(); assert.equal(vm.computeVersion, 4); assert.equal(vm.cForm.manualAdjustments.weekly, 0); assert.equal(vm.computeDirty, false)
})

test('successful compute sends only deltas and stops queue navigation on readback failure', async () => {
  let body
  const { vm, targets } = setup({ compute: async b => { body = b; return { code: 0, data: { id: scoreRecord().id, version: 3, status: 'PENDING_REVIEW', total: 82 } } }, getScores: async () => ({ code: 1, message: '列表读取失败' }) }); selectScore(vm, 'edit')
  vm.cForm.manualAdjustments.school = 2; vm.cForm.adjustmentReason = '核对后的增减分理由'; vm.cForm.evidenceFileIds = ['123']; await vm.submitCompute(true)
  assert.equal(body.expectedVersion, 2); assert.equal(body.manualAdjustments.school, 2); assert.equal(body.schoolScore, undefined); assert.equal(body.internshipId, '9007199254740888'); assert.equal(vm.lastReceipt.actionLabel, '成绩已核算'); assert.equal(vm.computeVersion, 3); assert.equal(targets.length, 0); assert.match(vm.panelError, /刷新失败/)
})

test('review and publish use separate valid states and incomplete records cannot pass', () => {
  const { vm } = setup(); selectScore(vm)
  assert.equal(vm.canAct(vm.panel.data, 'review'), true); assert.equal(vm.canAct(vm.panel.data, 'publish'), false)
  vm.panel.data.incomplete = true; assert.equal(vm.canAct(vm.panel.data, 'review'), false); assert.equal(vm.canAct(vm.panel.data, 'return'), true)
  vm.panel.data = scoreRecord({ status: 'PENDING_PUBLISH' }); assert.equal(vm.canAct(vm.panel.data, 'publish'), true); assert.equal(vm.canRecalc(vm.panel.data), false)
})

test('review conflict blocks repeats, retains reason, and requires a new explicit operation', async () => {
  let calls = 0
  const { vm } = setup({ review: async () => { calls++; return { code: 409001, message: '另一人已复核' } }, getDetail: async () => ({ code: 0, data: scoreRecord({ status: 'PENDING_PUBLISH', version: 3 }) }) }); selectScore(vm)
  vm.confirmAct(vm.panel.data, 'review'); await vm.onConfirm({ reason: '我核对时填写的内容' }); await vm.onConfirm({ reason: '再次点击' })
  assert.equal(calls, 1); assert.equal(vm.pending.expectedVersion, 2); assert.equal(vm.actionConflict, true); assert.equal(vm.keptReason, '我核对时填写的内容')
  vm.acknowledgeAction(); assert.equal(vm.pending, null); assert.equal(vm.cd.visible, false)
})

test('old decision cannot produce a receipt after context switch', async () => {
  let finish
  const { vm } = setup({ review: () => new Promise(r => { finish = r }) }); selectScore(vm); vm.confirmAct(vm.panel.data, 'review')
  const old = vm.onConfirm({ reason: '' }); vm.resetPanel(); finish({ code: 0, data: { id: scoreRecord().id, version: 3 } }); await old; assert.equal(vm.lastReceipt, null)
})

test('score form navigation blocks unsaved adjustments and active uploads', () => {
  const { vm, def } = setup(); let guard; vm.$router.beforeEach = fn => { guard = fn; return () => {} }; def.mounted.call(vm); selectScore(vm, 'edit')
  const from = { path: '/scores', fullPath: '/scores?id=8&mode=compute', query: { id: '8', mode: 'compute', batchId: '1' } }, to = { path: '/scores', fullPath: '/scores', query: {} }
  vm.cForm.manualAdjustments.weekly = 2; assert.equal(guard(to, from), false)
  vm.computeInitial = vm.computeSnapshot(); assert.equal(guard(to, from), true)
  vm.cForm.uploading = true; assert.equal(guard(to, from), false)
})
