import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { academicRoute } from '../../student-portal/src/router/academicRoutes.js'
import * as uiHelpers from '../../student-portal/src/components/academic/studentAcademicUi.js'
import * as commandGuard from '../../student-portal/src/components/academic/studentAcademicCommandGuard.js'
import { TYPE_LABEL, STATUS_LABEL, NODE_LABEL, statusColor } from '../src/modules/academicAffairs/constants/status-change.js'

const printUrl = new URL('../src/modules/academicAffairs/views/AaStatusChangePrintView.vue', import.meta.url)
const adminListUrl = new URL('../src/modules/academicAffairs/views/AaStatusChangeListView.vue', import.meta.url)
const portalStatusUrl = new URL('../../student-portal/src/views/academic/StudentStatusView.vue', import.meta.url)
const portalEnumsUrl = new URL('../../student-portal/src/services/visibleEnumLocalization.js', import.meta.url)
const portalTableUrl = new URL('../../student-portal/src/components/AutoTable.vue', import.meta.url)
const miniappUrl = new URL('../../miniapp/src/pages/student/academic-affairs/status.vue', import.meta.url)

test('D3-U print shows scheduled effective time independently from suspend expiry', async () => {
  const source = await readFile(printUrl, 'utf8')

  assert.match(source, /<th>生效方式<\/th>/)
  assert.match(source, /<th>计划生效时间<\/th>/)
  assert.match(source, /change\.effectiveDate \? '指定日期' : '终审通过立即生效'/)
  assert.match(source, /<tr v-if="change\.expireDate"><th>休学到期<\/th><td colspan="3">/)
  assert.doesNotMatch(source, /v-if="change\.expireDate"[^\n]*change\.effectiveDate/)
})

test('D3-U admin list surfaces scheduled effective time without opening detail', async () => {
  const source = await readFile(adminListUrl, 'utf8')

  assert.match(source, /\{ key: 'effective', title: '计划生效' \}/)
  assert.match(source, /#cell-effective="\{ row \}"/)
  assert.match(source, /effectiveDateText\(row\.effectiveDate, row\.status\)/)
  assert.match(source, /row\.status === 'APPROVED_PENDING_EFFECTIVE'/)
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
    .replace(/components\s*:\s*\{[^}]*\},?/, '').replace('export default', 'return')
  const component = new Function('TYPE_LABEL', 'STATUS_LABEL', 'NODE_LABEL', 'statusColor', script)(TYPE_LABEL, STATUS_LABEL, NODE_LABEL, statusColor)
  // The date is planning data; only the formal status reports whether execution happened.
  assert.equal(component.methods.effectiveDateText(null, 'SUBMITTED'), '终审通过即生效')
  assert.equal(component.methods.effectiveDateText(null, 'APPROVED_PENDING_EFFECTIVE'), '计划时间缺失，待核对')
  assert.equal(component.methods.effectiveDateText('2099-09-01T08:30:00'), '2099-09-01 08:30')
  assert.equal(component.methods.statusLabel('APPROVED_PENDING_EFFECTIVE'), '已通过·待生效')
  assert.equal(component.methods.statusLabel('EFFECTIVE'), '已生效')
})

test('D3-U student portal locks the real status route to canonical pending-effective display', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [academicRoute] })
  const route = router.resolve('/academic/status')
  assert.equal(route.name, 'academic-status')
  assert.equal(route.meta.modulePath, 'academic')
  assert.match(route.matched.at(-1).components.default.toString(), /StudentStatusView\.vue/)

  const { descriptor } = parse(await readFile(portalStatusUrl, 'utf8'))
  const modules = {
    vue: { ...vue, onMounted() {}, onBeforeUnmount() {} },
    '../../components/academic/studentAcademicUi': uiHelpers,
    '../../components/academic/studentAcademicCommandGuard': commandGuard,
    '../../services/systemDialog': { systemConfirm: async () => false },
    '../../stores/session': { useSessionStore: () => ({ user: { tenantId: 'school-a', userId: 'student-a', userType: 'STUDENT' } }) },
    '../../services/portalApi': { portalApi: {
      academicStatus: async () => ({ studentStatus: 'REGISTERED', changes: [
        { changeId: '9007199254740993', changeType: 'SUSPEND', status: 'APPROVED_PENDING_EFFECTIVE', effectiveDate: '2099-09-01T08:30:00' }
      ] }),
      academicTransferOptions: async () => ({}), profileEnrollment: async () => ({})
    } }
  }
  const script = compileScript(descriptor, { id: 'status-route-contract' }).content
    .replace(/^import (.+?) from ['"](.+?)['"];?$/gm, (_, binding, path) => binding.startsWith('{')
      ? `const ${binding.replace(/\bas\b/g, ':')} = modules[${JSON.stringify(path)}]`
      : `const ${binding} = { render: () => null }`)
    .replace('export default', 'return')
  const component = new Function('modules', script)(modules)
  const page = component.setup({}, { expose() {} })
  await page.load()
  const html = await renderToString(vue.createSSRApp({
    template: descriptor.template.content,
    setup: () => ({ ...page }),
    components: Object.fromEntries(['AcademicPrototypeHeader', 'StateBlock', 'AcademicBusinessReceipt',
      'AcademicPrototypeSteps', 'AcademicPrototypeIcon', 'RouterLink'].map(name => [name, { render: () => null }]))
  }))
  assert.match(html, /2099-09-01 08:30/)
  assert.match(page.changeStatusText('IN_REVIEW'), /审批中|审核中/)
  assert.match(page.changeStatusText('APPROVED_PENDING_EFFECTIVE'), /已通过.*待生效/)
  assert.match(html, /已通过.*待生效/)
  assert.doesNotMatch(html, /APPROVED_PENDING_EFFECTIVE|已正式生效/)
  assert.equal(page.status.value.studentStatus, 'REGISTERED')
  assert.match(page.changeStatusText('EFFECTIVE'), /已(?:正式)?生效/)
  assert.equal(page.studentStatusText('SUSPENDED'), '休学')
  assert.equal(page.studentStatusText('PRESERVED'), '保留学籍')
  assert.equal(page.studentStatusText('WITHDRAWN'), '退学')
})

test('D3-U student portal keeps WITHDRAW business meaning scoped to academic status-change columns', async () => {
  const [enums, table] = await Promise.all([
    readFile(portalEnumsUrl, 'utf8'),
    readFile(portalTableUrl, 'utf8')
  ])

  // Global internship meaning must remain untouched.
  assert.match(enums, /WITHDRAW: '退岗'/)
  // Only the explicit academic status-change column overrides the same canonical code.
  assert.match(enums, /'changeType:异动类型': Object\.freeze\(\{[\s\S]*WITHDRAW: '退学'/)
  assert.match(table, /const contextKey = `\$\{column\.key \|\| ''\}:\$\{column\.label \|\| ''\}`/)
  assert.match(table, /safeVisibleEnumLabel\(text, '状态待确认', contextKey\)/)
})

test('D3-U miniapp localizes pending-effective and shows planned time', async () => {
  const source = await readFile(miniappUrl, 'utf8')

  assert.match(source, /APPROVED_PENDING_EFFECTIVE: '已通过·待生效'/)
  assert.match(source, /c\.status === 'APPROVED_PENDING_EFFECTIVE'/)
  assert.match(source, /c\.effectiveDate/)
})
