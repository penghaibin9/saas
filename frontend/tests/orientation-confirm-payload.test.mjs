import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

function view(name, api) {
  const source = readFileSync(new URL(`../src/views/admin/orientation/${name}.vue`, import.meta.url), 'utf8')
  const names = []
  const script = parse(source).descriptor.script.content
    .replace(/import (\w+) from [^\n]+/g, (_, name) => { names.push(name); return '' })
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, list) => {
      names.push(...list.split(',').map(s => s.trim())); return ''
    }).replace('export default', 'return')
  const errors = []
  const successes = []
  const component = new Function('api', ...names, script)(api, ...names.map(n => n === 'toast'
    ? { success(message) { successes.push(message) }, error(message) { errors.push(message) } } : {}))
  const vm = component.data()
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = fn.bind(vm)
  vm.load = async () => { vm.reloaded = true }
  vm.confirmRow = { id: '63055', version: 7 }
  vm.confirmVisible = true
  return { vm, errors, successes }
}

for (const [name, mode, method] of [
  ['OrientationVerifyView', 'pass', 'verifyOrientationStudent'],
  ['OrientationVerifyView', 'fail', 'verifyOrientationStudent'],
  ['OrientationGreenChannelView', 'return', 'returnGreenChannel'],
  ['OrientationGreenChannelView', 'reject', 'rejectGreenChannel'],
  ['OrientationBatchListView', 'void', 'voidOrientationBatch']
]) {
  test(`${name} ${mode}: dialog object sends a string reason and prevents duplicate writes`, async () => {
    let complete
    const calls = []
    const { vm, successes } = view(name, { [method]: (...args) => {
      calls.push(args); return new Promise(resolve => { complete = resolve })
    } })
    vm.confirmMode = mode
    const event = { reason: mode === 'pass' ? '' : '请核对填写的信息', notify: true }
    const first = vm.onConfirm(event)
    await vm.onConfirm(event)
    assert.equal(calls.length, 1)
    assert.equal(calls[0][0], '63055')
    assert.equal(mode === 'void' ? calls[0][1] : calls[0][1].reason, event.reason)
    if (name === 'OrientationVerifyView') {
      assert.equal(calls[0][1].passed, mode === 'pass')
      assert.equal(calls[0][1].expectedVersion, 7)
    }
    if (name === 'OrientationGreenChannelView') assert.equal(calls[0][1].expectedVersion, 7)
    assert.equal(vm.confirmSubmitting, true)
    complete({ code: 0 })
    await first
    assert.equal(vm.confirmSubmitting, false)
    assert.equal(vm.confirmVisible, false)
    assert.equal(vm.reloaded, true)
    if (name === 'OrientationVerifyView') {
      assert.deepEqual(successes, [mode === 'pass' ? '信息核验已通过' : '已退回学生补正，原因已记录'])
    }
  })

  test(`${name} ${mode}: failure retains dialog and permits deliberate retry`, async () => {
    let attempts = 0
    const { vm, errors } = view(name, { [method]: async () => {
      attempts++
      if (attempts === 1) throw new Error('网络连接失败')
      return { code: 0 }
    } })
    vm.confirmMode = mode
    const event = { reason: '请核对填写的信息', notify: true }
    await vm.onConfirm(event)
    assert.equal(vm.confirmVisible, true)
    assert.equal(vm.confirmSubmitting, false)
    assert.equal(vm.reloaded, undefined)
    assert.deepEqual(errors, ['网络连接失败'])
    assert.equal(event.reason, '请核对填写的信息')
    await vm.onConfirm(event)
    assert.equal(attempts, 2)
    assert.equal(vm.confirmVisible, false)
  })
}
