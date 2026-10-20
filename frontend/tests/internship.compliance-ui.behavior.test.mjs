import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { captureConflict, emptyConflict, isConflict } from '../src/modules/internship/composables/conflictGuard.js'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipComplianceView.vue', import.meta.url), 'utf8')).descriptor.script.content.replace(/^import[^\n]*\n/gm, '').replace(/ {2}components: \{[^\n]*\n/, '').replace('export default', 'return')
function view(api = {}) {
  const def = new Function('formatDateTime', 'complianceApi', 'emptyConflict', 'captureConflict', 'isConflict', script)(value => value, api, emptyConflict, captureConflict, isConflict)
  const calls = []
  const vm = { ...def.data(), batchStore: { selectedBatchId: '7' }, $route: { path: '/admin/internship/compliance', fullPath: '/admin/internship/compliance?tab=overview&batchId=7&filter=insurance', query: { tab: 'overview', batchId: '7', filter: 'insurance' } }, $router: { push: q => calls.push(q), replace: q => calls.push(q) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) if (key !== 'batchStore') Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, calls }
}
test('compliance student navigation retains batch and exact return filter', () => {
  const { vm, calls } = view(); vm.openStudent({ internshipId: '9007199254740999' })
  assert.equal(calls[0].path, '/admin/internship/students/9007199254740999')
  assert.equal(calls[0].query.returnTo, vm.$route.fullPath); assert.equal(calls[0].query.batchId, '7')
})
test('all blocked students stay available rather than only a five-person preview', () => {
  const { vm } = view(); const rows = Array.from({ length: 8 }, (_, id) => ({ internshipId: String(id), blockers: [{ reason: '待核验' }] }))
  vm.stats = { drilldowns: { BLOCKED: rows } }; vm.selectedFilter = 'BLOCKED'
  assert.deepEqual(vm.drilldownRows, rows)
})
test('compliance tabs and filters write refreshable URLs', () => {
  const { vm, calls } = view(); vm.goTab('consents'); vm.selectFilter('BLOCKED')
  assert.equal(calls[0].query.tab, 'consents'); assert.equal(calls[0].query.batchId, '7')
  assert.equal(calls[1].query.filter, 'BLOCKED')
})
test('late compliance summary cannot show the previous batch facts', async () => {
  let resolve; const pending = new Promise(done => { resolve = done })
  const { vm } = view({ batchStats: () => pending, workbenchSummary: () => pending, auditHealth: () => pending })
  const loading = vm.load(); vm.batchStore.selectedBatchId = '8'; vm.loadSeq++; vm.stats = { current: true }
  resolve({ code: 0, data: { old: true } }); await loading
  assert.deepEqual(vm.stats, { current: true })
})

test('consent editor returns without discarding unsent content', () => {
  const { vm, calls } = view(); vm.forms.consent.contentSnapshot = '尚未提交的知情确认正文'
  vm.openConsentEditor(); assert.equal(calls[0].query.form, 'consent')
  vm.$route.query = calls[0].query; vm.closeConsentEditor()
  assert.equal(calls[1].query.form, undefined); assert.equal(calls[1].query.batchId, '7')
  assert.equal(vm.forms.consent.contentSnapshot, '尚未提交的知情确认正文')
})
test('consent submit guards duplicate requests before invoking the API', async () => {
  let requests = 0; const { vm } = view({ createConsent: () => { requests++; return Promise.resolve({ code: 0 }) } })
  vm.acting = true; await vm.createConsent(); assert.equal(requests, 0)
})

const pendingGuardian = { id: '9007199254740999', version: 3, consentType: 'GUARDIAN', status: 'PENDING' }

test('guardian resend preserves exact ID/version and reads back delivery without claiming confirmation', async () => {
  const requests = []; let reads = 0
  const { vm } = view({ redeliverConsent: async (...args) => { requests.push(args); return { code: 0, data: { deliveryStatus: 'SENT' } } } })
  vm.can = () => true; vm.load = async () => { reads++ }
  await vm.redeliverConsent(pendingGuardian)
  assert.deepEqual(requests, [[pendingGuardian.id, 3]]); assert.equal(reads, 1)
  assert.equal(vm.consentDelivery.error, false); assert.match(vm.consentDelivery.message, /旧链接已失效/)
  assert.equal(pendingGuardian.status, 'PENDING')
})

test('guardian resend guards permissions, nonpending tasks, missing versions and duplicates', async () => {
  let requests = 0
  const { vm } = view({ redeliverConsent: async () => { requests++; return { code: 0 } } })
  vm.can = () => false; await vm.redeliverConsent(pendingGuardian)
  vm.can = () => true
  await vm.redeliverConsent({ ...pendingGuardian, status: 'VALID' })
  await vm.redeliverConsent({ ...pendingGuardian, consentType: 'STUDENT' })
  await vm.redeliverConsent({ ...pendingGuardian, version: null })
  assert.match(vm.consentDelivery.message, /版本缺失/)
  vm.acting = true; await vm.redeliverConsent(pendingGuardian)
  assert.equal(requests, 0)
})

test('guardian resend reports partial delivery and keeps the original task', async () => {
  const { vm } = view({ redeliverConsent: async () => ({ code: 0, data: { deliveryStatus: 'SKIPPED', deliveryReason: '短信服务未启用' } }) })
  vm.can = () => true; vm.load = async () => {}
  await vm.redeliverConsent(pendingGuardian)
  assert.equal(vm.consentDelivery.error, true)
  assert.match(vm.consentDelivery.message, /链接已更新，但短信未确认送达/)
  assert.match(vm.consentDelivery.message, /短信服务未启用/)
})

test('guardian resend conflict never retries the same stale version or fabricates success', async () => {
  let requests = 0
  const { vm } = view({ redeliverConsent: async () => { requests++; return { code: 409001, message: '任务版本已变化' } } })
  vm.can = () => true
  await vm.redeliverConsent(pendingGuardian); await vm.redeliverConsent(pendingGuardian)
  assert.equal(requests, 1); assert.equal(vm.consentDelivery.blockedVersion, 3)
  assert.match(vm.consentDelivery.message, /本次未重新发送/)
})

test('guardian resend network failure offers readback before retry and releases submitting state', async () => {
  const { vm } = view({ redeliverConsent: async () => { throw new Error('网络中断') } })
  vm.can = () => true
  await vm.redeliverConsent(pendingGuardian)
  assert.match(vm.consentDelivery.message, /先刷新核对送达结果/); assert.equal(vm.acting, false)
})

test('guardian resend late response cannot display facts from a previous batch', async () => {
  let resolve
  const { vm } = view({ redeliverConsent: () => new Promise(done => { resolve = done }) })
  vm.can = () => true; vm.load = async () => assert.fail('must not refresh another batch')
  const pending = vm.redeliverConsent(pendingGuardian)
  vm.batchStore.selectedBatchId = '8'
  resolve({ code: 0, data: { deliveryStatus: 'SENT' } }); await pending
  assert.equal(vm.consentDelivery.message, ''); assert.equal(vm.acting, false)
})

test('safety course editor preserves batch context and unsaved course on return', () => {
  const { vm, calls } = view(); vm.forms.safety.title = '未发布课程'; vm.openSafetyEditor()
  assert.equal(calls[0].query.form, 'safety'); assert.equal(calls[0].query.batchId, '7')
  vm.$route.query = calls[0].query; vm.closeSafetyEditor()
  assert.equal(calls[1].query.form, undefined); assert.equal(vm.forms.safety.title, '未发布课程')
})
test('invalid safety course never reaches the creation API', async () => {
  let requests = 0; const { vm } = view({ createSafetyCourse: () => { requests++; return Promise.resolve({ code: 0 }) } }); vm.can = () => true
  await vm.createSafetyCourse(); assert.equal(requests, 0); assert.match(vm.safetyError, /课程名称/)
})
test('safety course creation blocks duplicate requests before API execution', async () => {
  let requests = 0; const { vm } = view({ createSafetyCourse: () => { requests++; return Promise.resolve({ code: 0 }) } }); vm.acting = true
  await vm.createSafetyCourse(); assert.equal(requests, 0)
})

test('filing retry submits the saved draft rather than recreating it', async () => {
  let creates = 0; const submissions = []
  const { vm } = view({
    createFiling: async () => { creates++; return { code: 0, data: { id: '9007199254740999', version: 2 } } },
    reviewFiling: async (id, level, action, body) => { submissions.push({ id, level, action, body }); return submissions.length === 1 ? { code: 1, message: '提交暂不可用' } : { code: 0 } }
  })
  vm.can = () => true; vm.load = async () => {}; vm.closeFilingEditor = () => {}
  vm.forms.filing = { internshipId: '12', filingType: 'OTHER', triggerReason: '符合要求的备案原因', riskDescription: '', fileIds: ['99'] }
  await vm.createFiling(); assert.equal(vm.filingDraft.id, '9007199254740999'); assert.equal(vm.filingError, '提交暂不可用')
  await vm.createFiling(); assert.equal(creates, 1); assert.equal(submissions.length, 2)
  assert.deepEqual(submissions[1], { id: '9007199254740999', level: 'COLLEGE', action: 'submit', body: { expectedVersion: 2 } })
  assert.equal(vm.filingDraft, null)
})
test('filing creation failure retains entered fields and does not submit', async () => {
  const { vm } = view({ createFiling: async () => ({ code: 1, message: '依据材料失效' }), reviewFiling: async () => assert.fail('must not submit') })
  vm.can = () => true; vm.forms.filing = { internshipId: '12', filingType: 'OTHER', triggerReason: '符合要求的备案原因', riskDescription: '', fileIds: ['99'] }
  await vm.createFiling(); assert.equal(vm.filingDraft, null); assert.equal(vm.filingError, '依据材料失效'); assert.equal(vm.forms.filing.triggerReason, '符合要求的备案原因')
})

test('compliance review conflict retains original version and comment and blocks resubmission', async () => {
  let requests = 0
  const { vm } = view({ reviewFiling: async () => { requests++; return { code: 409001, message: '记录已更新' } } })
  vm.openAction('filing-review', { id: '9', version: 1, status: 'PENDING_COLLEGE' }, 'APPROVE', 'COLLEGE')
  vm.dialog.comment = '老师原有审核意见'
  vm.load = async () => { vm.workbench = { filings: [{ id: '9', version: 2, status: 'PENDING_SCHOOL' }] } }
  await vm.confirmDialog()
  assert.equal(vm.conflict.active, true); assert.equal(vm.dialog.row.version, 1); assert.equal(vm.dialog.comment, '老师原有审核意见')
  await vm.confirmDialog(); assert.equal(requests, 1)
  assert.equal(vm.conflict.latest.find(item => item.label === '最新版本').value, 2)
})
test('failed conflict refresh is explicitly stale and keeps old review disabled', async () => {
  const { vm } = view(); vm.openAction('filing-review', { id: '9', version: 1 }, 'APPROVE', 'COLLEGE')
  vm.load = async () => { vm.groupError = '明细读取失败' }
  await vm.onDialogConflict({ code: 409001 }); assert.equal(vm.conflict.stale, true); assert.equal(vm.conflict.active, true)
})
test('review double click is blocked before an API request is started', async () => {
  const { vm } = view({ reviewFiling: () => assert.fail('duplicate request') }); vm.acting = true
  await vm.confirmDialog()
})

test('direct safety review link resolves an exact visible pending record', () => {
  const { vm } = view(); vm.$route.query = { tab: 'safety', batchId: '7', reviewId: '9007199254740999', reviewAction: 'APPROVE' }
  vm.loadedGroups.add('safety'); vm.can = () => true
  vm.workbench.safetyCompletions = [{ id: '9007199254740999', status: 'PENDING_REVIEW', version: 4 }]
  vm.restoreReview(); assert.equal(vm.dialog.open, true); assert.equal(vm.dialog.row.version, 4)
})
test('old or inaccessible review links cannot open an actionable form', () => {
  const { vm } = view(); vm.$route.query = { tab: 'filings', reviewId: '9', reviewAction: 'APPROVE', reviewLevel: 'COLLEGE' }
  vm.loadedGroups.add('filings'); vm.can = () => true
  vm.workbench.filings = [{ id: '9', status: 'APPROVED' }]; vm.restoreReview()
  assert.equal(vm.dialog.open, false); assert.match(vm.reviewError, /记录已变为/)
  vm.workbench.filings = []; vm.restoreReview(); assert.equal(vm.dialog.open, false); assert.match(vm.reviewError, /可见范围/)
})
test('return from independent review preserves original tab and batch', () => {
  const { vm, calls } = view(); vm.$route.query = { tab: 'filings', batchId: '7', reviewId: '9', reviewAction: 'APPROVE', reviewLevel: 'COLLEGE', filter: 'BLOCKED' }
  vm.closeReview(); assert.deepEqual(calls[0].query, { tab: 'filings', batchId: '7', filter: 'BLOCKED' })
})

test('incident and emergency editors preserve batch and unsaved input on return', () => {
  const { vm, calls } = view(); vm.activeTab = 'incidents'; vm.forms.incident.summary = '尚未提交的事故情况'
  vm.openIncidentEditor('incident'); vm.$route.query = calls[0].query
  assert.equal(vm.incidentEditor, 'incident'); assert.equal(calls[0].query.batchId, '7')
  vm.closeIncidentEditor(); assert.equal(calls[1].query.form, undefined)
  assert.equal(vm.forms.incident.summary, '尚未提交的事故情况')
  vm.openIncidentEditor('emergency'); vm.$route.query = calls[2].query
  assert.equal(vm.incidentEditor, 'emergency')
})

test('incident report validates and blocks repeated clicks before API execution', async () => {
  const { vm } = view({ reportIncident: () => assert.fail('must not submit') }); vm.can = () => true
  await vm.reportIncident(); assert.match(vm.incidentError, /完整填写/)
  vm.acting = true; await vm.reportIncident()
})


test('incident deep link restores visible permitted transition without changing version', () => {
  const { vm } = view(); vm.can = () => true; vm.loadedGroups.add('incidents')
  vm.$route.query = { tab: 'incidents', batchId: '7', reviewId: '9007199254740999', reviewKind: 'incident-transition', reviewAction: 'INVESTIGATING' }
  vm.workbench = { incidents: [{ id: '9007199254740999', status: 'REPORTED', version: 3 }] }
  vm.restoreReview(); assert.equal(vm.dialog.open, true); assert.equal(vm.dialog.row.version, 3)
  assert.equal(vm.dialog.action, 'INVESTIGATING')
})

test('incident deep link cannot bypass close permission or closure prerequisites', () => {
  const { vm } = view(); vm.loadedGroups.add('incidents'); vm.can = p => p !== 'internship.incident.close'
  vm.$route.query = { tab: 'incidents', reviewId: '1', reviewKind: 'incident-transition', reviewAction: 'CLOSED' }
  vm.workbench = { incidents: [{ id: '1', status: 'PENDING_REVIEW', closeAllowed: true }] }
  vm.restoreReview(); assert.equal(vm.dialog.open, false); assert.match(vm.reviewError, /权限/)
  vm.can = () => true; vm.workbench.incidents[0].closeAllowed = false
  vm.restoreReview(); assert.equal(vm.dialog.open, false); assert.match(vm.reviewError, /条件/)
})

test('emergency review link preserves exact identity and rejects completed plans', () => {
  const { vm, calls } = view(); vm.can = () => true; vm.loadedGroups.add('incidents')
  vm.openAction('emergency-review', { id: '9007199254740999', status: 'PENDING_REVIEW' }, 'REJECT')
  assert.equal(calls[0].query.reviewKind, 'emergency-review')
  vm.$route.query = calls[0].query; vm.dialog.open = false
  vm.workbench = { emergencyPlans: [{ id: '9007199254740999', status: 'APPROVED' }] }
  vm.restoreReview(); assert.equal(vm.dialog.open, false); assert.match(vm.reviewError, /状态/)
  vm.closeReview(); assert.equal(calls[1].query.reviewKind, undefined)
})

test('emergency submit retries original saved draft with its original version', async () => {
  let creates = 0; const submissions = []
  const { vm } = view({
    createEmergencyPlan: async () => { creates++; return { code: 0, data: { id: '9007199254740999', version: 4 } } },
    reviewEmergencyPlan: async (id, action, body) => { submissions.push({ id, action, body }); return submissions.length === 1 ? { code: 1, message: '提交暂不可用' } : { code: 0 } }
  })
  vm.can = () => true; vm.load = async () => {}
  vm.forms.emergency = { planName: '批次应急预案', responsiblePerson: '测试老师', emergencyContact: '13800000000', responseSteps: '先联系救援人员再执行转运及家校沟通', fileIds: ['99'] }
  await vm.createEmergency()
  assert.equal(vm.emergencyDraft.id, '9007199254740999'); assert.equal(vm.emergencyError, '提交暂不可用')
  assert.equal(vm.forms.emergency.planName, '批次应急预案')
  await vm.createEmergency(); assert.equal(creates, 1); assert.equal(submissions.length, 2)
  assert.deepEqual(submissions[1], { id: '9007199254740999', action: 'SUBMIT', body: { expectedVersion: 4 } })
  assert.equal(vm.emergencyDraft, null)
})

test('emergency creation response from previous batch cannot start a submission', async () => {
  let resolve; const { vm } = view({
    createEmergencyPlan: () => new Promise(done => { resolve = done }),
    reviewEmergencyPlan: () => assert.fail('previous batch must not submit')
  })
  vm.can = () => true
  vm.forms.emergency = { planName: '批次应急预案', responsiblePerson: '测试老师', emergencyContact: '13800000000', responseSteps: '先联系救援人员再执行转运及家校沟通', fileIds: ['99'] }
  const pending = vm.createEmergency(); vm.batchStore.selectedBatchId = '8'
  resolve({ code: 0, data: { id: '1', version: 0 } }); await pending
  assert.equal(vm.emergencyDraft, null)
})

test('emergency double click and invalid fields never start creation', async () => {
  const { vm } = view({ createEmergencyPlan: () => assert.fail('must not create') }); vm.can = () => true
  await vm.createEmergency(); assert.match(vm.emergencyError, /预案名称/)
  vm.acting = true; await vm.createEmergency()
})

test('exemption editor retains batch and unsent reason when returning', () => {
  const { vm, calls } = view(); vm.activeTab = 'exemptions'; vm.forms.exemption.reason = '未提交的特殊情况与替代措施'
  vm.openExemptionEditor(); vm.$route.query = calls[0].query
  assert.equal(vm.exemptionEditor, true); vm.closeExemptionEditor()
  assert.equal(calls[1].query.batchId, '7'); assert.equal(calls[1].query.form, undefined)
  assert.equal(vm.forms.exemption.reason, '未提交的特殊情况与替代措施')
})

test('exemption review deep link restores evidence attachments and original version', () => {
  const { vm, calls } = view(); vm.can = () => true; vm.loadedGroups.add('exemptions')
  const row = { id: '9007199254740999', status: 'PENDING_REVIEW', version: 3, evidenceFileIds: ['9007199254740998'] }
  vm.openAction('exemption-review', row, 'APPROVE'); vm.$route.query = calls[0].query; vm.dialog.open = false
  vm.workbench = { exemptions: [row] }; vm.restoreReview()
  assert.equal(vm.dialog.kind, 'exemption-review'); assert.equal(vm.dialog.row.version, 3)
  assert.deepEqual(vm.dialog.row.fileIds, row.evidenceFileIds)
  vm.dialog.open = false; vm.can = () => false; vm.restoreReview()
  assert.equal(vm.dialog.open, false); assert.match(vm.reviewError, /权限/)
})

test('invalid exemption request and repeated click cannot call API', async () => {
  const { vm } = view({ grantExemption: () => assert.fail('must not submit') }); vm.can = () => true
  await vm.requestExemption(); assert.match(vm.exemptionError, /补齐/)
  vm.acting = true; await vm.requestExemption()
})

test('evidence generation keeps exact selected target and blocks repeated calls', async () => {
  const requests = []; const { vm } = view({ generateEvidencePackage: (type, id) => { requests.push({ type, id }); return Promise.resolve({ code: 0 }) } })
  vm.can = () => true; vm.run = async promise => promise
  vm.forms.package = { packageType: 'BATCH', targetId: '' }
  await vm.generatePackage(); assert.deepEqual(requests, [{ type: 'BATCH', id: '7' }])
  vm.acting = true; await vm.generatePackage(); assert.equal(requests.length, 1)
})

test('evidence generation rejects missing student selection', async () => {
  const { vm } = view({ generateEvidencePackage: () => assert.fail('must not generate') }); vm.can = () => true
  vm.forms.package = { packageType: 'STUDENT', targetId: '' }
  await vm.generatePackage(); assert.match(vm.packageError, /请选择/)
})


test('audit read failure preserves the usable compliance workbench and retries only health', async () => {
  let reads = 0; let statsReads = 0; let summaryReads = 0
  const { vm } = view({
    batchStats: async () => { statsReads++; return { code: 0, data: { total: 3 } } },
    workbenchSummary: async () => { summaryReads++; return { code: 0, data: { generatedAt: 'now' } } },
    auditHealth: async () => ++reads === 1 ? { code: 503001, message: '网络不可用' } : { code: 0, data: { healthy: true } }
  })
  await vm.load()
  assert.equal(vm.error, ''); assert.equal(vm.stats.total, 3)
  assert.equal(vm.workbench.generatedAt, 'now'); assert.equal(vm.auditHealth, null)
  assert.equal(vm.auditNotice.type, 'warning'); assert.match(vm.auditNotice.title, /暂未取得/)
  await vm.loadAuditHealth()
  assert.equal(vm.auditNotice, null); assert.equal(reads, 2)
  assert.equal(statsReads, 1); assert.equal(summaryReads, 1)
})

test('slow audit check does not hold the student conditions behind page loading', async () => {
  let resolve
  const { vm } = view({
    batchStats: async () => ({ code: 0, data: { total: 3 } }),
    workbenchSummary: async () => ({ code: 0, data: { generatedAt: 'now' } }),
    auditHealth: () => new Promise(done => { resolve = done })
  })
  await vm.load()
  assert.equal(vm.loading, false); assert.equal(vm.stats.total, 3)
  assert.equal(vm.auditHealthLoading, true); assert.equal(vm.auditNotice.type, 'info')
  resolve({ code: 0, data: { healthy: false, stalled: true, backlog: 29, dead: 0 } })
  await Promise.resolve()
  assert.equal(vm.auditNotice.type, 'danger'); assert.match(vm.auditNotice.description, /29 条/)
  assert.match(vm.auditNotice.description, /超过 1 小时/)
})

test('audit exception or malformed health never becomes a confirmed failure or a healthy result', async () => {
  for (const auditHealth of [async () => { throw new Error('连接中断') }, async () => ({ code: 0, data: {} })]) {
    const { vm } = view({ auditHealth })
    vm.auditHealth = { healthy: true }
    await vm.loadAuditHealth()
    assert.equal(vm.auditHealth, null); assert.equal(vm.auditNotice.type, 'warning')
    assert.equal(vm.auditHealthLoading, false)
  }
})

test('clearing the batch releases loading and rejects late health and summary results', async () => {
  let resolve
  const pending = new Promise(done => { resolve = done })
  const { vm } = view({ batchStats: () => pending, workbenchSummary: () => pending, auditHealth: () => pending })
  const oldLoad = vm.load()
  vm.batchStore.selectedBatchId = ''; await vm.load()
  assert.equal(vm.loading, false); assert.equal(vm.auditHealthLoading, false)
  assert.equal(vm.auditNotice, null); assert.deepEqual(vm.stats, {})
  resolve({ code: 0, data: { healthy: false, total: 99 } }); await oldLoad
  assert.equal(vm.auditHealth, null); assert.deepEqual(vm.stats, {}); assert.equal(vm.error, '')
})

test('rechecking health blocks duplicate clicks and cannot overwrite the next batch', async () => {
  let resolve; let reads = 0
  const { vm } = view({ auditHealth: () => { reads++; return new Promise(done => { resolve = done }) } })
  const first = vm.loadAuditHealth(); await vm.loadAuditHealth()
  assert.equal(reads, 1)
  vm.batchStore.selectedBatchId = '8'; vm.auditHealthSeq++; vm.auditHealthLoading = false
  vm.auditHealth = { healthy: true }
  resolve({ code: 0, data: { healthy: false } }); await first
  assert.deepEqual(vm.auditHealth, { healthy: true })
})

test('identity correction carries the exact student and original compliance location', () => {
  const { vm, calls } = view(); vm.can = () => true
  const row = { studentId: '9007199254740999', blockers: [{ code: 'guardianConsent', reason: '出生日期待核实，暂无法判定是否需监护人确认' }] }
  vm.openIdentityCorrection(row)
  assert.deepEqual(calls[0], { path: '/admin/academic-affairs/roster/corrections', query: {
    studentId: row.studentId, fieldKey: 'ID_CARD', returnTo: vm.$route.fullPath
  } })
  vm.can = () => false; vm.openIdentityCorrection(row); assert.equal(calls.length, 1)
  vm.can = () => true; vm.openIdentityCorrection({ ...row, blockers: [{ code: 'guardianConsent', reason: '未成年须监护人确认' }] })
  assert.equal(calls.length, 1)
})
