import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const api=fs.readFileSync(new URL('../src/modules/platform/api/moduleCommerce.api.js',import.meta.url),'utf8')
const view=fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformCommercialControlView.vue',import.meta.url),'utf8')
test('module lifecycle workspace wires M3 portfolio and delivery endpoints',()=>{assert.match(api,/commercial\/tenants\/\$\{tenantId\}\/modules/);assert.match(api,/delivery-acceptance/);assert.match(view,/商业授权与模块生命周期/);assert.match(view,/模块交付验收已冻结/)})
test('planned cancellation and resume are explicit reversible commands',()=>{assert.match(api,/cancel-at-period-end/);assert.match(api,/resume-renewal/);assert.match(view,/期末停续/);assert.match(view,/撤销停续/);assert.match(view,/当前已付服务期不受影响/)})
test('module exit is distinct from tenant offboarding and carries lifecycle version',()=>{assert.match(api,/offboarding-preview/);assert.match(view,/expectedLifecycleVersion/);assert.match(view,/单模块退出/);assert.match(view,/不是整校退租/);assert.match(view,/其他模块和整校状态未改变/)})
test('M5 UI selects only server-verified export candidates instead of database ids or hashes',()=>{assert.match(api,/module-offboarding\/\$\{jobId\}\/export/);assert.match(api,/export-acceptance/);assert.match(view,/exportCandidates/);assert.match(view,/服务端已核验/);assert.match(view,/scopeHash/);assert.doesNotMatch(view,/placeholder="ExportJob ID"/);assert.doesNotMatch(view,/placeholder="Manifest ID"/);assert.doesNotMatch(view,/v-model[^>]*(sha|hash)/i)})
test('source changes invalidate stale delivery acceptance visibly',()=>{assert.match(view,/staleDeliveryAcceptance/);assert.match(view,/合同来源已变化/);assert.match(view,/重新验收/)})
test('retention copy clearly stops before physical purge',()=>{assert.match(view,/保留期从签收时间开始/);assert.match(view,/未启动物理销毁/);assert.match(view,/M5 到此停止/)})
test('workspace retains original reconciliation instead of replacing it',()=>{assert.match(view,/全校商业与存储对账/);assert.match(view,/commercialStorageLimitBytes/);assert.match(view,/actualConsumptionBytes/);assert.match(view,/UNAUTHORIZED_MODULE_USAGE/)})
test('four canonical product centers stay explicit',()=>{for(const label of ['岗位实习中心','毕业设计中心','学工中心','教务中心'])assert.match(view,new RegExp(label))})
test('risky module freeze requires explicit acknowledgement and a successful server preview',()=>{
  assert.match(view,/offboardForm\.confirmed/)
  assert.match(view,/:disabled="busy\|\|!offboardForm\.confirmed\|\|!preview\.canRequest"/)
  assert.match(view,/if\(!m\|\|!this\.preview\?\.canRequest\)return/)
  assert.match(view,/当前不执行物理销毁/)
  assert.match(view,/冻结此模块 generation/)
})
