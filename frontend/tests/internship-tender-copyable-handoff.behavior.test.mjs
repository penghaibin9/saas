import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'

const source = fs.readFileSync(new URL('../src/components/common/AppCopyableText.vue', import.meta.url), 'utf8')
const component = new Function(source.match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default', 'return'))()
component.render = new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>/)[1], { prefixIdentifiers: true }).code)(Vue)

test('真实令牌投影遵循学生系统正式签发学校编码，不把学校编号当编码', () => {
  const client = fs.readFileSync(new URL('../src/services/http/client.js', import.meta.url), 'utf8')
  const body = client.slice(client.indexOf('export function currentUserFromToken()'), client.indexOf('export async function fetchMyAuthContexts()')).replace('export function', 'function')
  const payload = { userId: 'db-9', tenantId: '9007199254740993', tenantCode: 'UNTRUSTED-LEGACY', tid: 'PAGE-SYNTHETIC', realName: '虚构学校经办人' }
  const state = { token: 'header.' + Buffer.from(JSON.stringify(payload)).toString('base64url') + '.signature' }
  const current = new Function('state', body + '; return currentUserFromToken')(state)
  assert.equal(current().tenantCode, 'PAGE-SYNTHETIC'); assert.equal(current().tenantId, '9007199254740993'); assert.equal(current().realName, '虚构学校经办人')
})

for (const [filename, values, expected] of [
  ['RecruitmentCampaignDetailView.vue', { inviteResult: { acceptUrl: 'https://school.test/enterprise/invite/accept?token=synthetic-only', inviteToken: 'synthetic-only', tenantCode: 'PAGE-SYNTHETIC' } }, ['https://school.test/enterprise/invite/accept?token=synthetic-only', 'PAGE-SYNTHETIC']],
  ['components/EnterpriseMemberWorkspace.vue', { inviteUrl: 'https://school.test/enterprise/invite/accept?token=member-synthetic-only' }, ['https://school.test/enterprise/invite/accept?token=member-synthetic-only']]
]) {
  test(`${filename} 的实际复制控件渲染邀请值`, async () => {
    const parent = fs.readFileSync(new URL('../src/modules/internship/views/' + filename, import.meta.url), 'utf8')
    const tags = [...parent.matchAll(/<AppCopyableText\b[^>]*\/>/g)].map(match => match[0])
    const render = new Function('Vue', compile('<div>' + tags.join('') + '</div>', { prefixIdentifiers: true }).code)(Vue)
    const app = Vue.createSSRApp({ data: () => values, render }); app.component('AppCopyableText', component)
    const html = await renderToString(app)
    for (const value of expected) assert.ok(html.includes(value), '邀请值必须实际进入公共复制组件')
  })
}

test('复制动作向剪贴板写入展示值，不复制空串', async () => {
  const navigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator'), oldWindow = globalThis.window
  const copied = [], events = [], vm = { ...component.data(), value: 'synthetic-invite-address', $emit: (...args) => events.push(args) }
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: { writeText: async text => copied.push(text) } } })
  globalThis.window = { isSecureContext: true }
  try {
    await component.methods.copy.call(vm)
    assert.deepEqual(copied, ['synthetic-invite-address']); assert.deepEqual(events, [['copied', 'synthetic-invite-address']])
  } finally {
    clearTimeout(vm.timer)
    if (navigatorDescriptor) Object.defineProperty(globalThis, 'navigator', navigatorDescriptor); else delete globalThis.navigator
    if (oldWindow === undefined) delete globalThis.window; else globalThis.window = oldWindow
  }
})
