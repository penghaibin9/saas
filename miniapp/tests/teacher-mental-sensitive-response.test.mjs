import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const Vue = require('vue')
const { compile } = require('@vue/compiler-dom')
const { renderToString } = require('@vue/server-renderer')
const source = readFileSync(new URL('../src/pages/teacher/affairs/mental/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .+$/gm, '').replace('export default', 'return')
const template = source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
const render = new Function('Vue', compile(template, {
  mode: 'function', prefixIdentifiers: true,
  isCustomElement: name => ['view', 'text', 'picker', 'input', 'textarea', 'button'].includes(name)
}).code)(Vue)

function fixture(api = {}) {
  const component = new Function('teacherApi', 'affairsContractApi', 'normalizeError', 'toast', script)(
    {}, api, error => ({ text: error.message }), () => {}
  )
  const vm = { ...component.data(), ...component.methods, loaded: true, state: 'content' }
  vm.active = { referralId: '41', realName: '授权测试学生', studentNo: 'TEST', level: 'FOCUS',
    status: 'REFERRED', statusLabel: '已转介', noteMasked: true, note: '敏感记录已隐藏',
    version: 3, canReveal: false, allowedActions: ['FOLLOW', 'CLOSE'] }
  async function html() {
    const app = Vue.createSSRApp({ ...component,
      data: () => Object.fromEntries(Object.entries(vm).filter(([key]) => !(key in component.methods))), render })
    app.component('MobileGlobalState', { setup: (_, { slots }) => () => Vue.h('section', slots.default?.()) })
    app.component('MobileStatusTag', { props: ['label'], setup: props => () => Vue.h('span', props.label) })
    app.component('MobileNavBar', { setup: () => () => Vue.h('header') })
    app.component('MobileInlineAlert', { setup: () => () => Vue.h('aside') })
    return renderToString(app)
  }
  return { vm, html }
}

test('authorized actions remain usable while psychological raw notes are concealed', async () => {
  const { vm, html } = fixture()
  const concealed = await html()
  assert.ok(concealed.includes('查看原始记录需单独授权'))
  assert.ok(concealed.includes('回访（≥5字）'))
  vm.active.canReveal = true
  assert.ok((await html()).includes('查看明细需填写原因'))
  vm.active.allowedActions = []
  const unavailable = await html()
  assert.ok(!unavailable.includes('回访（≥5字）'))
})

test('a masked successful follow-up preserves the next action and the returned version', async () => {
  const calls = []
  const { vm, html } = fixture({ followMental: async (...args) => {
    calls.push(args)
    return { ...vm.active, status: 'FOLLOWING', statusLabel: '跟进中', version: 4, noteMasked: true }
  } })
  vm.actionContent = '已经完成本次回访记录'
  vm.doFollow()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(calls, [['41', '已经完成本次回访记录', 3]])
  assert.equal(vm.active.version, 4)
  assert.equal(vm.active.noteMasked, true)
  assert.equal(vm.acting, false)
  assert.ok((await html()).includes('关闭（结论≥5字）'))
})
