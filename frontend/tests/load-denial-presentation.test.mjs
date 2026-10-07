import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

function component(path, imports = {}) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'return')
  const options = new Function(...Object.keys(imports), script)(...Object.values(imports))
  const template = source.slice(source.indexOf('<template>') + 10, source.lastIndexOf('</template>'))
  options.render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  return options
}
const GlobalState = component('../src/components/common/AppGlobalState.vue', { normalizeUiError })
const ErrorState = component('../src/components/business/ErrorState.vue', { AppGlobalState: GlobalState, normalizeUiError })

for (const [error, state, title] of [
  [{ code: 403001, message: '权限不足', bizCode: 'NO_PERMISSION' }, 'forbidden', '暂无访问权限'],
  [{ httpStatus: 403, message: '禁止访问' }, 'forbidden', '暂无访问权限'],
  [{ response: { status: 403 }, message: 'Forbidden' }, 'forbidden', '暂无访问权限'],
  [{ code: 403001, bizCode: 'NO_PERMISSION', message: '模块未购买或未授权：academicAffairs' }, 'noLicense', '本校未开通该模块'],
  [{ code: 401001 }, 'unauthorized', '登录已失效'],
  [{ code: 'NETWORK' }, 'offline', '网络异常'],
  ['当前账号没有执行此操作的权限', 'forbidden', '暂无访问权限']
]) {
  test(`PC error renders ${state} with correct actions, even under legacy failure title`, async () => {
    const normalized = normalizeUiError(error)
    assert.equal(normalized.pageState, state)
    const html = await renderToString(Vue.createSSRApp(ErrorState, { error, title: '教务中心加载失败' }))
    assert.ok(html.includes(title), html)
    assert.doesNotMatch(html, /教务中心加载失败|academicAffairs|联系管理员<\/button>/)
    if (['forbidden', 'noLicense', 'unauthorized'].includes(state)) assert.doesNotMatch(html, />\s*重试\s*</)
    if (state === 'offline') assert.match(html, />\s*重试\s*</)
  })
}
test('server/network failures cannot become permission denials from misleading text', () => {
  for (const error of [
    { httpStatus: 503, code: 403001, message: '模块未购买或未授权：academicAffairs' },
    { code: 'NETWORK', message: '没有权限' },
    { status: 500, message: '没有权限' }
  ]) assert.ok(['error', 'offline'].includes(normalizeUiError(error).pageState))
})
test('PC legacy description-only consumers also render denial and never show technical module keys', async () => {
  const description = normalizeUiError({ code: 403001, message: '模块未购买或未授权：academicAffairs' }).userMessage
  const html = await renderToString(Vue.createSSRApp(ErrorState, { description }))
  assert.match(html, /本校未开通该模块/)
  assert.doesNotMatch(html, /加载失败|academicAffairs|>\s*重试\s*</)
})

test('PC shared state rejects a stale failure title/retry slot on permission refusal', async () => {
  const html = await renderToString(Vue.createSSRApp({
    render: () => Vue.h(GlobalState, { state: 'forbidden', title: '加载失败', description: '权限不足' },
      { actions: () => Vue.h('button', '重试') })
  }))
  assert.match(html, /暂无访问权限/)
  assert.doesNotMatch(html, /加载失败|>重试</)
})

test('resolved backend denial clears stale ready content before subsequent reload', () => {
  const vm = { hasReadyContent: true }
  GlobalState.watch.resolvedState.call(vm, 'forbidden')
  assert.equal(vm.hasReadyContent, false)
})

const MobileState = component('../../miniapp/src/components/MobileGlobalState.vue', { back() {}, relaunch() {} })
for (const state of ['forbidden', 'noLicense', 'unauthorized']) {
  test(`mobile ${state} cannot inherit a retry slot or failure title`, async () => {
    const app = Vue.createSSRApp({ render: () => Vue.h(MobileState, { state, title: '加载失败', description: 'internalKey' },
      { actions: () => Vue.h('button', '重试') }) })
    app.config.warnHandler = () => {} // unrelated globally registered graduation widgets
    const html = await renderToString(app)
    assert.doesNotMatch(html, /加载失败|internalKey|>重试</)
    assert.match(html, state === 'forbidden' ? /暂无访问权限/ : state === 'noLicense' ? /本校未开通该模块/ : /重新登录/)
  })
}
