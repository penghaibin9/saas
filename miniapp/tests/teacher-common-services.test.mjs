import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as preferences from '../src/services/teacherCommonServices.mjs'

const services = Array.from({ length: 8 }, (_, i) => ({ key: 'service' + i, label: '服务' + i, path: '/real/' + i, group: '教学事务' }))
const session = { realUser: { tenantId: '1000000000000000007', activeContextId: 'context/1' }, identity: { userId: '9007199254740993' }, currentRole: 'academic', persistedIdentityVerified: true }
function setup(storage = new Map()) {
  const source = readFileSync(new URL('../src/components/MobileTeacherCommonServices.vue', import.meta.url),'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','module.exports =')
  const uni = { getStorageSync: key => storage.get(key) ?? '', setStorageSync: (key,value) => storage.set(key,value) }
  const context = { module: { exports: {} }, ...preferences, uni, teacherVisual() {}, go() {}, toast() {} }
  vm.runInNewContext(source,context)
  const options = context.module.exports
  const page = { ...options.data(), services, role: 'academic', storageKey: preferences.commonServiceStorageKey(session) }
  for (const [key,fn] of Object.entries(options.methods)) page[key] = fn.bind(page)
  for (const [key,fn] of Object.entries(options.computed)) Object.defineProperty(page,key,{ get: () => fn.call(page) })
  page.load()
  return { page, options, storage, uni }
}
const visible = page => Array.from(page.visibleServices, item => item.key)
test('preferences isolate school, account, role and active work context without losing large IDs', () => {
  const key = preferences.commonServiceStorageKey(session)
  assert.match(key, /9007199254740993/)
  const variants = [
    { ...session, realUser: { ...session.realUser, tenantId: '1000000000000000008' } },
    { ...session, identity: { userId: '9007199254740994' } },
    { ...session, currentRole: 'counselor' },
    { ...session, realUser: { ...session.realUser, activeContextId: 'context/2' } }
  ]
  assert.equal(new Set([key,...variants.map(preferences.commonServiceStorageKey)]).size,5)
  assert.equal(preferences.commonServiceStorageKey({ ...session, persistedIdentityVerified: false }), '')
})
test('add, remove, reorder and save survive remount; cancelling leaves saved settings intact', () => {
  const { page, storage } = setup()
  assert.deepEqual(visible(page), ['service0','service1','service2'])
  page.startEdit(); page.remove('service0'); page.toggle('service5'); page.move('service5',-1); page.save()
  assert.equal(page.editing,false)
  assert.deepEqual(visible(setup(storage).page), ['service1','service5','service2'])
  page.startEdit(); page.remove('service1'); page.restoreDefaults(); page.cancelEdit()
  assert.deepEqual(visible(page), ['service1','service5','service2'])
})
test('empty selection is deliberate; defaults are applied only on request and save', () => {
  const { page, storage } = setup()
  page.startEdit(); for (const item of [...page.draftKeys]) page.remove(item); page.save()
  assert.deepEqual(visible(setup(storage).page), [])
  page.startEdit(); page.restoreDefaults(); page.save()
  assert.deepEqual(visible(setup(storage).page), ['service0','service1','service2'])
})
test('six-item limit is explained; unavailable services are filtered again at save and read', () => {
  const { page, storage } = setup()
  page.startEdit(); for (let i=3;i<8;i++) page.toggle('service'+i)
  assert.equal(page.draftKeys.length,6); assert.match(page.editError,/最多显示6个/)
  page.services = services.filter(item => item.key !== 'service2')
  page.save()
  assert.equal(visible(page).includes('service2'),false)
  const remounted = setup(storage).page; remounted.services = services.filter(item => item.key !== 'service3')
  assert.equal(visible(remounted).includes('service3'),false)
  assert.deepEqual(preferences.allowedCommonServiceKeys(['fake','blocked','service0','service0'], [...services,{key:'blocked',path:'/bad',disabledReason:'无权'}]),['service0'])
})
test('storage errors keep drafts editable and retryable, without claiming saved success', () => {
  const { page, uni } = setup()
  page.startEdit(); page.toggle('service4')
  uni.setStorageSync = () => { throw new Error('quota') }; page.save()
  assert.equal(page.editing,true); assert.match(page.editError,/保存失败/); assert.equal(page.draftKeys.includes('service4'),true)
  assert.deepEqual(visible(page), ['service0','service1','service2'])
  uni.getStorageSync = () => '{invalid'; page.cancelEdit(); page.load(); page.startEdit()
  assert.match(page.readError,/读取失败/); assert.equal(page.editing,false)
})
test('switching work identity discards its draft and cannot write into the new identity', () => {
  const { page, options, storage } = setup()
  page.startEdit(); page.toggle('service5'); page.storageKey += ':new-context'; page.save()
  assert.equal(storage.size,0); assert.equal(page.editing,false)
  options.watch.storageKey.handler.call(page)
  assert.deepEqual(visible(page), ['service0','service1','service2'])
})
test('counselor default order retains leave, classes and conversations', () => {
  assert.deepEqual(preferences.defaultCommonServiceKeys(['myClasses','other','talk','affairsLeave'].map(key=>({key})), 'counselor'), ['affairsLeave','myClasses','talk'])
})
