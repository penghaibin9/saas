import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync(new URL('../src/modules/platform/api/moduleCommerce.api.js', import.meta.url), 'utf8')
const view = fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformCommercialControlView.vue', import.meta.url), 'utf8')

test('module lifecycle workspace wires M3 portfolio and delivery endpoints', () => {
  assert.match(api, /commercial\/tenants\/\$\{tenantId\}\/modules/)
  assert.match(api, /delivery-acceptance/)
  assert.match(view, /商业授权与模块生命周期/)
  assert.match(view, /模块交付验收已冻结/)
})

test('planned cancellation and resume are explicit reversible commands', () => {
  assert.match(api, /cancel-at-period-end/)
  assert.match(api, /resume-renewal/)
  assert.match(view, /期末停续/)
  assert.match(view, /撤销停续/)
  assert.match(view, /当前已付服务期不受影响/)
})

test('module exit is distinct from tenant offboarding and carries lifecycle version', () => {
  assert.match(api, /offboarding-preview/)
  assert.match(view, /expectedLifecycleVersion/)
  assert.match(view, /单模块退出/)
  assert.match(view, /不是整校退租/)
  assert.match(view, /其他模块和整校状态未改变/)
})

test('M5 UI selects only server-verified export candidates instead of database ids or hashes', () => {
  assert.match(api, /module-offboarding\/\$\{jobId\}\/export/)
  assert.match(api, /export-acceptance/)
  assert.match(view, /exportCandidates/)
  assert.match(view, /服务端已核验/)
  assert.match(view, /scopeHash/)
  assert.doesNotMatch(view, /placeholder="ExportJob ID"/)
  assert.doesNotMatch(view, /placeholder="Manifest ID"/)
  assert.doesNotMatch(view, /v-model[^>]*(sha|hash)/i)
})

test('source changes invalidate stale delivery acceptance visibly', () => {
  assert.match(view, /staleDeliveryAcceptance/)
  assert.match(view, /合同来源已变化/)
  assert.match(view, /重新验收/)
})

test('M4 M5 UI exposes object-level consumer evidence without ownership guessing', () => {
  assert.match(view, /consumerDependencies/)
  assert.match(view, /objectEvidence/)
  assert.match(view, /sharedObjectCounts/)
  assert.match(view, /domainFactCounts/)
  assert.match(view, /unsettledSharedObjectCounts/)
  for (const label of ['审批实例', '统一待办', '消息事件队列', '文件绑定', '学工档案包', '正式成绩']) {
    assert.match(view, new RegExp(label))
  }
  assert.match(view, /跨域消费者与正式事实/)
  assert.match(view, /当前只允许办理冻结与交付/)
})

test('school export acceptance is hard-disabled until the effective consumer snapshot is current', () => {
  assert.match(view, /deliveryAcceptanceReady/)
  assert.match(view, /deliveryAcceptanceBlockers/)
  assert.match(view, /deliveryEvidenceDigest/)
  assert.match(view, /交付包与当前消费者对象快照一致，可以签收/)
  assert.match(view, /当前交付包不能签收/)
  assert.match(view, /:disabled="busy \|\| !job\.deliveryAcceptanceReady"/)
  assert.match(view, /if \(!this\.job\?\.deliveryAcceptanceReady\)/)
  assert.match(view, /当前交付包与消费者对象快照不一致，不能签收/)
})

test('consumer drift recovery requires a new verified export and never launders the old package', () => {
  assert.match(view, /freshExportCandidates/)
  assert.match(view, /重新生成正式交付包 → 绑定新的 ExportJob\/Manifest/)
  assert.match(view, /重新绑定新交付包/)
  assert.match(view, /旧包不会被“重新确认”洗白/)
  assert.match(view, /String\(candidate\.exportJobId/)
  assert.match(view, /String\(candidate\.manifestId/)
  assert.match(view, /新交付包已重新绑定，并封存当前消费者对象快照/)
})

test('retention copy clearly stops before physical purge', () => {
  assert.match(view, /保留期从签收时间开始/)
  assert.match(view, /未启动物理销毁/)
  assert.match(view, /M5 到此停止/)
})

test('workspace retains original reconciliation instead of replacing it', () => {
  assert.match(view, /全校商业与存储对账/)
  assert.match(view, /commercialStorageLimitBytes/)
  assert.match(view, /actualConsumptionBytes/)
  assert.match(view, /UNAUTHORIZED_MODULE_USAGE/)
})

test('four canonical product centers stay explicit', () => {
  for (const label of ['岗位实习中心', '毕业设计中心', '学工中心', '教务中心']) assert.match(view, new RegExp(label))
})

test('risky module freeze requires explicit acknowledgement and a successful server preview', () => {
  assert.match(view, /offboardForm\.confirmed/)
  assert.match(view, /:disabled="busy \|\| !offboardForm\.confirmed \|\| !preview\.canRequest"/)
  assert.match(view, /if \(!module \|\| !this\.preview\?\.canRequest\) return/)
  assert.match(view, /当前不执行物理销毁/)
  assert.match(view, /冻结此模块 generation/)
})
