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
// 2026-09-12: reviewed e475bea2f localization adds only roleDisplayLabel/permissionDisplayLabel
// imports and method bindings in these two scripts; guards and action bindings stay unchanged.
// Their display behavior is covered by system-permission-labels.test.mjs.
// 2026-09-13: reviewed template-based local-role creation adds the initial-permission
// choice and reviewed version/digest. Existing busy/authority/context guards remain;
// system-role-template-creation.behavior.test.mjs covers the new write contract.
// 2026-09-13: reviewed explicit adoption keeps the existing edit guards; the new
// snapshot, conflict, protected-role and context-fence behavior is independently
// exercised by system-role-adoption.behavior.test.mjs.
// 2026-09-13: reviewed member validation now focuses invalid fields and moves the
// form beside submit. Authority guards and payload remain unchanged; behavioral
// coverage lives in system-role-members-validation.behavior.test.mjs.
const anchors = {
  "views/SystemRoleListView.vue": {
    "script": "f9e24ed3ed90bba5d35ade8ec79cadb4cdadbf3d3c6d74cfd85230ac83abeabc",
    "directives": "3626f13d743f5004215cf2a366ebdf40b9340a3093a8b33b135c9c941cfea8d3"
  },
  "views/SystemModuleFeatureView.vue": {
    "script": "c52bcc0c16bd80265d346f098a9886693f486d39eb175e09462747c55d923ed8",
    "directives": "3f141158e08d2f08c3353830dc4f7da1eb5236b893f180fce62baba613bd29b8"
  },
  "components/workspace/RolePermissionPanel.vue": {
    "script": "5e5c4318f4ac3fdff6714fae62db8a163965e8cdb78beabc4965c54521b4e5f9",
    "directives": "0c63c5c99399e30843ecb669f5cf694ca7f4bf128cc093f1867bf5ca4cc8e61b"
  },
  "components/workspace/RoleMembersPanel.vue": {
    "script": "89ef0eb69c08992b01da11b2c08ec0aedc59ad6e26a73ec1785bb014c7aa36c2",
    "directives": "35f4a171d4a3a72df04be5e55164e94990b59ce0ed1ea94c0377169f847b776e"
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
