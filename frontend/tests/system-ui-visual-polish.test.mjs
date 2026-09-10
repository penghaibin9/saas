import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createHash } from 'node:crypto'
import { parse } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'
import postcss from 'postcss'

const readSource = url => fs.readFileSync(url, 'utf8').replace(/\r\n/g, '\n')
// This pass intentionally changes presentation only. Update these anchors only after
// separately reviewing any subsequent business change, never to hide a failing check.
// 2026-09-10: reviewed system-dialog migration removes browser-native confirms and unload prompts.
const anchors = {
  "views/SystemRoleListView.vue": {
    "script": "02328932e02bfd022447e03a062451c51d0593f1e61a231c657a80fa38ebe4e8",
    "directives": "7f928e376dd575762c46e9ac5cdde32d48c3cb9c46ea52759c207475050daaa2"
  },
  "views/SystemModuleFeatureView.vue": {
    "script": "c52bcc0c16bd80265d346f098a9886693f486d39eb175e09462747c55d923ed8",
    "directives": "3f141158e08d2f08c3353830dc4f7da1eb5236b893f180fce62baba613bd29b8"
  },
  "components/workspace/RolePermissionPanel.vue": {
    "script": "9ac36c4e4c6a5ab80a1b6f6c2ec73ac920b48700a3e0812002f32cf3db429d28",
    "directives": "7b7dc58d4587eb0c443271eaa5fe3dd08745934f5de6db2a7b9a60a59455158e"
  },
  "components/workspace/RoleMembersPanel.vue": {
    "script": "68c29686ed63b9a2526e1c0fb7f3e5bfc8f608d3d7f1a3b84d2c1c8c02b6dcee",
    "directives": "6cd2d740ab637ff7072cadf9d57e3e26e027445fa177a5ec4085271bd0402118"
  }
}
const root = new URL('../src/modules/system/', import.meta.url)
const digest = value => createHash('sha256').update(value).digest('hex')
function businessScript(source) {
  return parse(source).descriptor.script.content
    .replace(/^import AppIcon from '@\/components\/ui\/AppIcon.vue'\r?\n/m, '')
    .replace(/components: \{ AppIcon, /, 'components: { ')
    .replace(/\s+/g, ' ').trim()
}
function behaviorDirectives(source) {
  const result = []
  const bindings = new Set(['disabled', 'checked', 'readonly', 'submitting', 'confirm-disabled',
    'require-reason', 'initial-reason', 'visible', 'role-id', 'locked', 'ctx', 'tab', 'key'])
  function visit(node) {
    for (const prop of node.props || []) {
      if (prop.type !== 7) continue
      if (['if', 'else-if', 'else', 'show', 'for', 'model', 'on'].includes(prop.name)
        || (prop.name === 'bind' && bindings.has(prop.arg?.content))) {
        result.push([prop.name, prop.arg?.content || '', prop.exp?.content || '',
          (prop.modifiers || []).map(item => item.content || item).join('.')].join('|'))
      }
    }
    for (const child of node.children || []) visit(child)
  }
  visit(baseParse(parse(source).descriptor.template.content))
  return JSON.stringify(result.sort())
}
for (const [path, expected] of Object.entries(anchors)) {
  const source = readSource(new URL(path, root))
  test(`visual refinement preserves business script: ${path}`, () => {
    assert.equal(digest(businessScript(source)), expected.script)
  })
  test(`visual refinement preserves guarded actions and field bindings: ${path}`, () => {
    assert.equal(digest(behaviorDirectives(source)), expected.directives)
  })
}
const css = readSource(new URL('components/workspace/workspace.css', root))
test('all visual rules stay inside the system workspace, never the shared portal', () => {
  postcss.parse(css).walkRules(rule => {
    for (const selector of rule.selectors) assert.ok(selector.startsWith('.system-workspace'), selector)
  })
  assert.doesNotMatch(css, /backdrop-filter|transition:\s*all|@import|url\(https?:/)
})
test('responsive matrix uses available content width and keeps the menu preview accessible', () => {
  assert.match(css, /container: role-content \/ inline-size/)
  assert.match(css, /@container role-content \(max-width: 580px\)/)
  assert.doesNotMatch(css, /\.sw-preview\s*\{[^}]*display:\s*none/)
  assert.match(css, /prefers-reduced-motion/)
  assert.match(css, /forced-colors/)
})
test('role creation has explicit native labels, including the previously ambiguous template select', () => {
  const source = readSource(new URL('views/SystemRoleListView.vue', root))
  for (const [id, label, tag] of [
    ['system-role-name', '角色名称', 'input'],
    ['system-role-code', '角色编码', 'input'],
    ['system-role-source-template', '已发布来源模板', 'select'],
    ['system-role-default-scope', '默认数据范围', 'select']
  ]) {
    assert.ok(source.includes(`<label for="${id}">${label}</label>`))
    assert.ok(source.includes(`<${tag} id="${id}"`))
  }
})
