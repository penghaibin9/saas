// 只执行两个目录中的守卫函数；路由、对话框和页面事件均为内存替身，不打开浏览器或修改业务文件。
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'

const roots = process.argv.slice(2)
assert.equal(roots.length, 2, '需要当前工程和候选工程的绝对路径')

function guard(root) {
  const source = readFileSync(root + '/frontend/src/router/dirtyFormGuard.js', 'utf8')
    .replace(/^import .*$/m, '')
    .replace('export function installDirtyFormGuard', 'function installDirtyFormGuard')
    .replace(/export \{ DEFAULT_GUARDED_ROUTES \}/, '')
  const window = { addEventListener() {}, removeEventListener() {} }
  const document = { addEventListener() {}, removeEventListener() {} }
  const from = { name: 'internship-batch-edit', path: '/form', fullPath: '/form', query: {} }
  const to = { name: 'target', path: '/target', fullPath: '/target', query: {} }
  const hooks = {}
  const router = {
    currentRoute: { value: from },
    beforeEach(fn) { hooks.before = fn }, beforeResolve(fn) { hooks.resolve = fn },
    afterEach(fn) { hooks.after = fn }
  }
  const context = { window, document, systemConfirm: async () => true }
  vm.runInNewContext(source + '\nthis.install = installDirtyFormGuard', context)
  const dispose = context.install(router)
  return { api: window.__SAAS_DIRTY_FORM_GUARD__, hooks, from, to, dispose }
}

async function probe(root, kind) {
  const g = guard(root)
  try {
    if (kind !== 'clean_then_edit') g.api.markDirty()
    let approve
    g.api.registerConfirmation(() => kind === 'edit_during_dialog'
      ? new Promise(resolve => { approve = resolve }) : true)
    const navigation = g.hooks.before(g.to, g.from)
    if (kind === 'edit_during_dialog') { g.api.markDirty(); approve(true) }
    const before = await navigation
    if (kind === 'edit_after_confirm' || kind === 'clean_then_edit') g.api.markDirty()
    const resolved = before && (g.hooks.resolve ? g.hooks.resolve(g.to, g.from) : true)
    return resolved
  } finally { g.dispose() }
}

const results = []
for (const kind of ['edit_during_dialog', 'edit_after_confirm', 'clean_then_edit', 'normal_discard']) {
  const current = await probe(roots[0], kind)
  const candidate = await probe(roots[1], kind)
  assert.equal(current, true)
  assert.equal(candidate, kind === 'normal_discard')
  results.push({ scenario: kind, currentAllowsLeaving: current, candidateAllowsLeaving: candidate })
}
console.log(JSON.stringify({ evidence: 'isolated function behavior, not browser acceptance', results }, null, 2))
