import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/student/affairs/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
function mount() {
  const dialogs = [], navigations = [], notices = [], native = []
  const uni = {
    showModal: options => dialogs.push(options),
    navigateBack: options => { navigations.push('back'); options.complete?.() },
    enableAlertBeforeUnload: options => native.push(options.message),
    disableAlertBeforeUnload: () => native.push('disabled')
  }
  const component = new Function('uni', 'go', 'toast', script)(uni, url => navigations.push(url), message => notices.push(message))
  const vm = { ...component.data(), ...component.methods }
  return { vm, component, dialogs, navigations, notices, native }
}

test('cancel keeps the selected file, uploaded ID and note; confirmed exit clears drafts only', async () => {
  const { vm, dialogs, navigations } = mount()
  vm.materials = [{ requirementId: '1', status: 'MISSING' }]
  vm.selectedFiles['1'] = { path: '/proof.pdf' }; vm.uploadedMaterials['1'] = { fileId: '77' }; vm.materialNotes['1'] = '保留'
  const cancel = vm.go('/pages/student/home/index')
  dialogs[0].success({ confirm: false }); await cancel
  assert.equal(navigations.length, 0); assert.equal(vm.uploadedMaterials['1'].fileId, '77'); assert.equal(vm.materialNotes['1'], '保留')
  const leave = vm.go('/pages/student/home/index')
  dialogs[1].success({ confirm: true }); await leave
  assert.deepEqual(navigations, ['/pages/student/home/index']); assert.equal(vm.hasMaterialDraft(), false)
  assert.deepEqual(vm.uploadedMaterials, {}); assert.equal(vm.materials[0].status, 'MISSING')
})

test('busy submissions block every navigation attempt and duplicate taps open one dialog', async () => {
  const { vm, dialogs, navigations, notices } = mount()
  vm.materialBusy = '1'
  vm.materialReturnContext = { bizType: 'FUNDING', bizId: '41' }
  await vm.go('/other'); await vm.back(); await vm.returnToApplication()
  assert.equal(navigations.length, 0); assert.equal(dialogs.length, 0); assert.equal(notices.length, 3)
  vm.materialBusy = ''; vm.materialNotes['1'] = '尚未提交'
  const first = vm.go('/first'); await vm.go('/second')
  assert.equal(dialogs.length, 1)
  dialogs[0].success({ confirm: true }); await first
  assert.deepEqual(navigations, ['/first'])
})

test('clean pages leave without prompts and the native alert is scoped to the visible dirty page', async () => {
  const { vm, component, dialogs, navigations, native } = mount()
  await vm.back()
  assert.deepEqual(navigations, ['back']); assert.equal(dialogs.length, 0)
  assert.equal(component.onBackPress.call(vm), false)
  vm.selectedFiles['1'] = { path: '/proof.pdf' }
  component.onShow.call(vm); assert.match(native.at(-1), /尚未提交/)
  component.onHide.call(vm); assert.equal(native.at(-1), 'disabled')
  component.onShow.call(vm); assert.match(native.at(-1), /尚未提交/)
  vm.selectedFiles = {}; vm.syncMaterialLeaveAlert(); assert.equal(native.at(-1), 'disabled')
})

test('the shared tab bar asks its page before relaunch and ordinary pages retain normal navigation', async () => {
  const tabSource = readFileSync(new URL('../src/components/MobileTabBar.vue', import.meta.url), 'utf8')
  const tabScript = tabSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
  const calls = []
  const component = new Function('relaunch', tabScript)(url => calls.push(url))
  const vm = { active: '', beforeNavigate: async () => false }
  await component.methods.onTap.call(vm, { key: 'home', route: '/home' }); assert.equal(calls.length, 0)
  vm.beforeNavigate = async () => true
  await component.methods.onTap.call(vm, { key: 'home', route: '/home' }); assert.deepEqual(calls, ['/home'])
  vm.beforeNavigate = null
  await component.methods.onTap.call(vm, { key: 'service', route: '/service' }); assert.deepEqual(calls, ['/home', '/service'])
})
