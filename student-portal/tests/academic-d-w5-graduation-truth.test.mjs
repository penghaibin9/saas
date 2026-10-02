import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import * as uiHelpers from '../src/components/academic/studentAcademicUi.js'
import * as commandGuard from '../src/components/academic/studentAcademicCommandGuard.js'
import * as localization from '../src/services/visibleEnumLocalization.js'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const view = fs.readFileSync(path.join(root, 'src/views/academic/StudentGraduationAuditView.vue'), 'utf8')
const routes = fs.readFileSync(path.join(root, 'src/router/academicRoutes.js'), 'utf8')
const api = fs.readFileSync(path.join(root, 'src/services/portalApi.js'), 'utf8')

test('D-W5 student graduation route remains a dedicated academic truth surface', () => {
  assert.match(routes, /path:\s*['"]graduation['"]/)
  assert.match(routes, /StudentGraduationAuditView\.vue/)
  assert.match(api, /academicGraduationAudit:\s*\(\)\s*=>\s*request\(['"]\/portal\/academic\/graduation-audit['"]\)/)
})

test('SYSTEM_ABNORMAL is explicit and can never inherit a green or generic formal label', () => {
  assert.match(view, /SYSTEM_ABNORMAL:\s*['"]正式预审存在阻断项['"]/)
  assert.match(view, /overallPassed\s*=\s*computed\(\(\)\s*=>\s*String\(progress\.value\.overall\s*\|\|\s*['"]['"]\)\.toUpperCase\(\)\s*===\s*['"]SYSTEM_PASSED['"]\)/)
  assert.doesNotMatch(view, /SYSTEM_ABNORMAL:\s*['"][^'"]*通过/)
})

test('non-PASS graduation items remain warning tone and UNKNOWN never becomes green', () => {
  assert.match(view, /itemResult\(item\)\s*===\s*['"]PASS['"]\s*\?\s*['"]success['"]\s*:\s*['"]warn['"]/)
  assert.match(view, /value\s*===\s*['"]PASS['"]\s*\?\s*['"]已通过['"]\s*:\s*value\s*===\s*['"]FAIL['"]\s*\?\s*['"]未达标['"]\s*:\s*['"]待核验['"]/)
  assert.match(view, /itemTone\(item\)[\s\S]*?itemResult\(item\)\s*===\s*['"]PASS['"]\s*\?\s*['"]is-pass['"]\s*:\s*['"]is-pending['"]/)
})

test('student graduation surface exposes all eleven items without leaking raw FEE or wrong archive semantics', () => {
  assert.match(view, /ARCHIVE:\s*['"]学工归档['"]/)
  assert.match(view, /FEE:\s*['"]费用结清['"]/)
  assert.doesNotMatch(view, /ARCHIVE:\s*['"]档案归档['"]/)
})

test('advisory UNKNOWN items are shown as hints but never inflate blocking pending count', () => {
  assert.match(view, /ADVISORY_UNKNOWN_ITEMS\s*=\s*new Set\(\[['"]EMPLOYMENT['"],\s*['"]FEE['"]\]\)/)
  assert.match(view, /advisoryPendingCount\s*=\s*computed/)
  assert.match(view, /blockingPendingCount\s*=\s*computed/)
  assert.match(view, /result !== ['"]PASS['"] && !\(result === ['"]UNKNOWN['"] && ADVISORY_UNKNOWN_ITEMS\.has\(code\)\)/)
  assert.match(view, /blockingPendingCount \? ['"]请优先处理阻断项['"] : ['"]当前没有阻断项['"]/)
})

test('manual recheck is wired through an explicit handler to the canonical server-truth loader', () => {
  assert.match(view, /@click=['"]refreshAudit['"]/)
  assert.match(view, /async function refreshAudit\(\)\s*\{\s*await load\(\)\s*\}/)
  assert.match(view, /async function load\(\)[\s\S]*?portalApi\.academicGraduationAudit\(\)/)
})

function graduationPage(progress) {
  const { descriptor } = parse(view)
  const compiled = compileScript(descriptor, { id: 'graduation-formal-conclusion' })
  const modules = {
    vue: { ...vue, onMounted() {}, onBeforeUnmount() {} },
    '../../services/portalApi': { portalApi: {} },
    '../../services/visibleEnumLocalization': localization,
    '../../stores/session': { useSessionStore: () => ({ user: { userId: 'student-A' } }) },
    '../../components/academic/studentAcademicUi': uiHelpers,
    '../../components/academic/studentAcademicCommandGuard': commandGuard
  }
  const components = {
    StatusTag: { props: ['text'], setup: props => () => vue.h('span', props.text) },
    StateBlock: { props: ['text'], setup: props => () => vue.h('p', props.text) }
  }
  const rewrite = code => code.replace(/^import (.+?) from ['"](.+?)['"];?$/gm, (_, binding, module) => {
    if (binding.startsWith('{')) return `const ${binding.replace(/\bas\b/g, ':')} = modules[${JSON.stringify(module)}]`
    return `const ${binding} = components[${JSON.stringify(binding)}] || { render: () => null }`
  })
  const component = new Function('modules', 'components', rewrite(compiled.content).replace('export default', 'return'))(modules, components)
  const state = component.setup({}, { expose() {} })
  state.loading.value = false
  state.audit.value = { progress, credits: {}, warnings: {} }
  const template = compileTemplate({ source: descriptor.template.content, filename: 'StudentGraduationAuditView.vue', id: 'graduation-formal-conclusion', compilerOptions: { bindingMetadata: compiled.bindings } })
  assert.deepEqual(template.errors, [])
  const render = new Function('modules', 'components', rewrite(template.code).replace('export function render', 'return function render'))(modules, components)
  return { state, render: () => {
    const app = vue.createSSRApp({ ...component, setup: () => state, render })
    app.component('RouterLink', { props: ['to'], setup: (props, { slots }) => () => vue.h('a', { href: props.to }, slots.default?.()) })
    return renderToString(app)
  } }
}

for (const [conclusion, label] of [['GRADUATED', '已正式毕业'], ['COMPLETED', '已正式结业']]) {
  test(`formal ${conclusion} leads the page while failed current checks remain available without urging reapplication`, async () => {
    const { state, render } = graduationPage({ hasAudit: true, conclusion, overall: 'SYSTEM_ABNORMAL', items: [
      { item: 'STATUS', result: 'FAIL', evidence: '当前学籍不符合实时在籍规则' },
      { item: 'CREDIT', result: 'UNKNOWN', evidence: '学分证据需要核对' }
    ] })
    const collapsed = await render()
    assert.match(collapsed, new RegExp(label))
    assert.match(collapsed, /查看实时自查补充说明/)
    assert.doesNotMatch(collapsed, /尚有条件需要补齐|未达标|查看课程补救/)
    assert.equal(state.overallPassed.value, false)
    assert.equal(state.blockingPendingCount.value, 2)
    state.showEvidence.value = true
    const expanded = await render()
    assert.match(expanded, /未达标/)
    assert.match(expanded, /待核验/)
    assert.match(expanded, /不代表学校撤销正式结论/)
    assert.doesNotMatch(expanded, /请优先处理阻断项|查看课程补救|查看相关事项|处理后重新核验/)
  })
}

test('absence of a real formal conclusion keeps the current graduation checklist and remedies', async () => {
  for (const progress of [{ hasAudit: false, conclusion: 'GRADUATED' }, { hasAudit: true, conclusion: 'DELAYED' }, { hasAudit: true, conclusion: null }]) {
    const { state, render } = graduationPage({ ...progress, overall: 'SYSTEM_ABNORMAL', items: [{ item: 'STATUS', result: 'FAIL' }] })
    state.showEvidence.value = true
    const html = await render()
    assert.equal(state.hasFormalConclusion.value, false)
    assert.match(html, /尚有条件需要补齐/)
    assert.match(html, /请优先处理阻断项/)
    assert.match(html, /查看课程补救/)
    assert.doesNotMatch(html, /学校正式审核结论/)
  }
})
