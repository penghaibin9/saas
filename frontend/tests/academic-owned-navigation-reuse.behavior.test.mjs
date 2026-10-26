import test from 'node:test'
import assert from 'node:assert/strict'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createOwnedHistoryAdapter, registerOwnedHistoryAdapter, issueFrameOwnedNavigation, OWNED_HISTORY_STATE_KEY } from '../src/router/ownedAcademicNavigation.js'

async function fixture() {
  let router
  const adapter = createOwnedHistoryAdapter(createMemoryHistory(), {
    shouldEnforce: () => true, resolveLocation: location => router.resolve(location)
  })
  router = createRouter({ history: adapter.history, routes: [
    { path: '/source', component: { render() {} } },
    { path: '/target', component: { render() {} } }
  ] })
  router.onError(() => {})
  registerOwnedHistoryAdapter(router, adapter)
  await router.push('/source')
  return { router, adapter }
}

test('当前请求正常进入并保留查询条件，内部导航凭据不留在浏览器历史', async () => {
  const { router, adapter } = await fixture()
  const owned = issueFrameOwnedNavigation(router, '/target?termId=52', { isCurrent: () => true })
  await router.push(owned.location)
  assert.equal(router.currentRoute.value.fullPath, '/target?termId=52')
  assert.equal(Object.hasOwn(adapter.history.state, OWNED_HISTORY_STATE_KEY), false)
  owned.finish()
})

test('路由等待期间原身份失效，旧请求不能提交历史或覆盖当前页面', async () => {
  const { router } = await fixture()
  let current = true, release, entered
  const waiting = new Promise(resolve => { entered = resolve })
  router.beforeResolve(() => { entered(); return new Promise(resolve => { release = resolve }) })
  const owned = issueFrameOwnedNavigation(router, '/target?termId=52', { isCurrent: () => current })
  const result = router.push(owned.location).catch(error => error)
  await waiting
  current = false; release()
  assert.equal(owned.isOwnStale(await result), true)
  assert.equal(router.currentRoute.value.path, '/source')
  owned.finish()
})

test('普通导航仍能使用原路由；未注册实例不能借用其他实例凭据', async () => {
  const { router } = await fixture()
  await router.push('/target')
  assert.equal(router.currentRoute.value.path, '/target')
  assert.throws(() => issueFrameOwnedNavigation({}, '/target', { isCurrent: () => true }), /registered/)
})
