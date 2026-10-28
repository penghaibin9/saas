import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { formatDateTime } from '../src/utils/dateUtils.js'

const source = fs.readFileSync(new URL('../src/modules/internship/views/ChangeRequestListView.vue', import.meta.url), 'utf8')
const template = source.slice(source.indexOf('<template>') + 10, source.indexOf('\n<script>')).replace(/<\/template>\s*$/, '')
async function render(row) {
  const names = ['ModulePageShell','EmptyState','DualPaneWorkspace','AppStatusTag','AppConfirmDialog','AppDescriptionList','AppAuditTrail','AppPermissionButton','AppPagination','ActionReceipt','AppSearchBox','AppInlineAlert','AppButton','AppExportButton']
  const scope = Object.fromEntries(names.map(name => [name, {}]))
  Object.assign(scope, { formatDateTime, REJECT_CHANGE: [], emptyConflict: () => ({}), canCode: () => false, useInternshipBatchStore: () => ({ selectedBatchId: '18' }) })
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(scope), script)(...Object.values(scope))
  const vm = { ...component.data(), ctx: {}, selectedId: '1', loading: false, rows: [row], detail: { loading: false, data: row } }
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = (...args) => fn.apply(vm, args)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  const passthrough = { setup: (_, { slots }) => () => h('section', [slots.aside?.(), slots.default?.()]) }
  const components = Object.fromEntries(names.map(name => [name, { render: () => null }]))
  Object.assign(components, { ModulePageShell: passthrough, DualPaneWorkspace: passthrough })
  return renderToString(createSSRApp({ components, setup: () => vm, render: compile(template) }))
}
const approved = () => ({ id: '1', status: 'APPROVED', currentEnterprise: '丙企业', currentPosition: '丙岗位',
  targetEnterpriseName: '乙企业', targetPositionName: '乙岗位', approvedHistory: {
    before: { enterpriseName: '甲企业', positionName: '甲岗位' }, after: { enterpriseName: '乙企业', positionName: '乙岗位' }, applicationBasisMatched: true } })

test('已通过原单显示审批前后历史，并单列后来当前去向', async () => {
  const html = await render(approved())
  assert.match(html, /本次变更前<\/small><strong>甲企业/)
  assert.match(html, /本次变更后<\/small><strong>乙企业/)
  assert.match(html, /当前实习去向：丙企业/)
  assert.match(html, /甲企业 \/ 甲岗位 → 乙企业 \/ 乙岗位/)
  assert.doesNotMatch(html, /与本申请依据的实习记录版本一致/)
  const unchanged=approved();unchanged.currentEnterprise='乙企业';unchanged.currentPosition='乙岗位'
  const same=await render(unchanged);assert.doesNotMatch(same,/class="change-impact__next"/);assert.match(same,/本次变更前/);assert.match(same,/本次变更后/)
})

test('历史未记录时不把当前或申请目标冒充审批结果，版本不一致不称申请依据', async () => {
  const row = approved(); row.approvedHistory = null
  const missing = await render(row)
  assert.match(missing, /历史去向未记录/)
  assert.doesNotMatch(missing, /本次变更前<\/small><strong>丙企业/)
  assert.doesNotMatch(missing, /本次变更后<\/small><strong>乙企业/)
  const mismatch = approved(); mismatch.approvedHistory.applicationBasisMatched = false
  assert.match(await render(mismatch), /仅记录本次审批前后去向，不能确认申请时去向/)
})

test('待审核继续显示当前去向和申请目标，不伪造历史', async () => {
  const row = approved(); row.status = 'PENDING'; row.approvedHistory = null
  const html = await render(row)
  assert.match(html, /当前实习去向<\/small><strong>丙企业/)
  assert.match(html, /本次申请目标<\/small><strong>乙企业/)
  assert.doesNotMatch(html, /本次变更前/)
})
