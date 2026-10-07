import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import * as localization from '../src/services/visibleEnumLocalization.js'
import * as registry from '../src/platform/moduleRegistry.js'

function page(name) {
  const source = readFileSync(new URL(`../src/views/${name}.vue`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'orientation-journey' })
  const modules = {
    vue: { ...vue, onMounted() {} },
    'vue-router': { useRoute: () => ({ path: '/orientation', query: {} }), useRouter: () => ({ push() {} }) },
    '../../services/portalApi': { portalApi: {} },
    '../../services/visibleEnumLocalization': localization,
    '../../platform/moduleRegistry': registry,
    '../../stores/session': { useSessionStore: () => ({ user: { realName: '虚构学生' } }) },
    '../../stores/ui': { useUiStore: () => ({ notify() {} }) }
  }
  const stateBlock = { props: ['text'], setup: props => () => vue.h('p', props.text) }
  const statusTag = { props: ['text'], setup: props => () => vue.h('span', props.text) }
  const components = { StateBlock: stateBlock, StatusTag: statusTag }
  const rewriteImports = code => code.replace(/^import (.+?) from ['"](.+?)['"];?$/gm, (_, binding, path) => {
    if (binding.startsWith('{')) return `const ${binding.replace(/\bas\b/g, ':')} = modules[${JSON.stringify(path)}]`
    return `const ${binding} = components[${JSON.stringify(binding)}] || { render: () => null }`
  })
  const component = new Function('modules', 'components', rewriteImports(compiled.content).replace('export default', 'return'))(modules, components)
  const state = component.setup({}, { expose() {} })
  const template = compileTemplate({ source: descriptor.template.content, filename: name + '.vue', id: 'orientation-journey', compilerOptions: { bindingMetadata: compiled.bindings } })
  assert.deepEqual(template.errors, [])
  const render = new Function('modules', rewriteImports(template.code).replace('export function render', 'return function render'))(modules)
  return { state, render: () => renderToString(vue.createSSRApp({ ...component, setup: () => state, render })) }
}

test('现场报到完成但缺材料时，学生电脑端继续展示入学手续待办', async () => {
  const { state, render } = page('orientation/OrientationView')
  state.loading.value = false
  state.my.value = {
    hasData: true, reportStatus: 'CHECKED_IN', checkinCredential: { status: 'CHECKED_IN', canIssue: false },
    steps: [{ key: 'CHECKIN', status: 'DONE' }, { key: 'MATERIAL', status: 'TODO' }],
    qualification: { verdict: 'NOT_QUALIFIED', verdictLabel: '暂不具备报到资格', blockers: [
      { code: 'MATERIAL_MISSING', step: 'MATERIAL', message: '身份证明尚未提交' },
      { code: 'MATERIAL_MISSING', step: 'MATERIAL', message: '录取通知书尚未提交' }
    ] }, selfService: { available: false, canSubmitMaterials: true }
  }
  assert.equal(state.allDone.value, false)
  const html = await render()
  assert.match(html, /已完成现场报到/)
  assert.match(html, /仍需补办/)
  assert.match(html, /查看与补交材料/)
  assert.match(html, /身份证明尚未提交/)
  assert.match(html, /录取通知书尚未提交/)
  assert.doesNotMatch(html, /暂不具备报到资格|入学手续已完成/)
})

test('学院确认才显示迎新办结，步骤优先消费服务器中文名称', async () => {
  const { state, render } = page('orientation/OrientationView')
  state.loading.value = false
  state.my.value = { hasData: true, checkinCredential: { status: 'FINALIZED' }, steps: [
    { key: 'CUSTOM_STEP', label: '领取生活用品', status: 'DONE' }
  ] }
  assert.equal(state.stepLabel('CUSTOM_STEP'), '领取生活用品')
  assert.equal(state.stepLabel('IDENTITY'), '身份核验')
  assert.equal(state.stepLabel('FINANCE'), '缴费核验')
  assert.equal(state.stepLabel('UNKNOWN_INTERNAL'), '待确认环节')
  const html = await render()
  assert.match(html, /入学手续已完成/)
  assert.doesNotMatch(html, /入学手续核对|查看与补交材料/)
})

test('首页零待办不宣称手续完成，并展示服务端迎新继续办理动作', async () => {
  const { state, render } = page('home/HomeView')
  state.loading.value = false
  state.home.value = {
    sections: { core: { state: 'DATA' }, todo: { state: 'EMPTY' } }, todos: [],
    lifecycle: [{ key: 'orientation', status: 'IN_PROGRESS' }],
    domains: [{ key: 'orientation', label: '数字迎新', status: 'CHECKED_IN', hasData: true }],
    alerts: [{ title: '迎新手续仍需补办', domain: 'orientation' }],
    nextAction: { label: '继续迎新办理', target: { path: '/orientation', query: {} } }
  }
  assert.equal(state.journey.value.find(item => item.key === 'orientation').done, false)
  assert.equal(state.statusLabel('COLLEGE_CONFIRMED'), '入学手续已完成')
  const html = await render()
  assert.match(html, /暂未收到待办，请结合下方办理进度核对各项手续/)
  assert.match(html, /继续迎新办理/)
  assert.match(html, /已现场报到/)
  assert.doesNotMatch(html, /一切就绪/)
  state.home.value.lifecycle = [{ key: 'orientation', status: 'COMPLETED' }]
  assert.equal(state.journey.value.find(item => item.key === 'orientation').done, true)
})
