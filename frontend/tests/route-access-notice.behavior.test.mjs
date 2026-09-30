import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { clearPermissionPatterns, setPermissionPatterns, setModuleEntitlements, setRbacLoadFailed, routeAccessNotice, canEnterRoute, GUARDED_MODULES } from '../src/security/permissionGate.js'

const meta = { moduleCode: 'STUDENT', permissionAny: ['student.profile.view', 'studentAffairs.student.view'] }
test('school module denial is distinguished from an account permission denial', () => {
  clearPermissionPatterns(); setPermissionPatterns(['student.profile.view']); setModuleEntitlements(['systemAdmin'])
  assert.equal(canEnterRoute(meta), false)
  assert.match(routeAccessNotice(meta).title, /学校尚未开通/)
  setModuleEntitlements(['studentProfile']); setPermissionPatterns([])
  assert.match(routeAccessNotice(meta).title, /当前身份/)
  setRbacLoadFailed(true)
  assert.match(routeAccessNotice(meta).title, /暂时无法确认/)
  clearPermissionPatterns(); setPermissionPatterns(['student.profile.view']); setModuleEntitlements(['studentProfile'])
  assert.equal(routeAccessNotice(meta), null)
})

const routerSource = fs.readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const guardBody = routerSource.slice(routerSource.indexOf('router.beforeEach(async (to, from, next) => {') + 'router.beforeEach(async (to, from, next) => {'.length, routerSource.lastIndexOf('\n})'))
const guard = new Function('getToken', 'isPlatformPrincipal', 'GUARDED_MODULES', 'getPermissionPatterns', 'canEnterRoute', 'routeAccessNotice', `return async (to, from, next) => {${guardBody.replace('import.meta.env.PROD', 'false')}}`)(
  () => 'test', () => false, GUARDED_MODULES, () => [], canEnterRoute, routeAccessNotice)
test('denied school deep link stays at the requested URL with a blocking workspace', async () => {
  clearPermissionPatterns(); setPermissionPatterns([]); setModuleEntitlements(['studentProfile'])
  const to = { path: '/admin/student/list', fullPath: '/admin/student/list?page=2', meta: { ...meta } }
  let destination = 'unset'
  await guard(to, {}, value => { destination = value })
  assert.equal(destination, undefined)
  assert.equal(to.fullPath, '/admin/student/list?page=2')
  assert.match(to.meta.accessNotice.title, /当前身份/)
  setPermissionPatterns(['student.profile.view'])
  await guard(to, {}, value => { destination = value })
  assert.equal(to.meta.accessNotice, undefined)
})

test('application outlet never mounts a denied business component or its data loaders', async () => {
  const appSource = fs.readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
  const template = appSource.match(/<template>([\s\S]*?)<\/template>/)[1]
  const render = new Function('Vue', compile(template, { mode: 'function' }).code)(Vue)
  let businessMounts = 0
  const business = { setup() { businessMounts++; return () => Vue.h('div', '业务资料') } }
  const route = { fullPath: '/admin/student/list', meta: { accessNotice: { title: '学校尚未开通此模块' } } }
  const createApp = () => Vue.createSSRApp({ render, components: {
    RouterView: { setup(_, { slots }) { return () => slots.default({ Component: business, route }) } },
    RouteAccessNotice: { props: ['notice'], setup(props) { return () => Vue.h('section', props.notice.title) } },
    SystemDialogHost: { render: () => null }, AppToast: { render: () => null }
  } })
  const html = await renderToString(createApp())
  assert.equal(businessMounts, 0)
  assert.match(html, /学校尚未开通此模块/)
  delete route.meta.accessNotice
  assert.match(await renderToString(createApp()), /业务资料/)
  assert.equal(businessMounts, 1)
})
