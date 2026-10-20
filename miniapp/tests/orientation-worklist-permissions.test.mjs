import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/pages/teacher/orientation/worklist/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '').replace('export default', 'return')

test('checked-in students see remaining enrollment work rather than a second reporting requirement', () => {
  const {vm} = setup({})
  assert.equal(vm.qualificationLabel({reportStatus:'CHECKED_IN',canFinalize:false}), '仍有入学手续待补办')
  assert.equal(vm.qualificationLabel({reportStatus:'CHECKED_IN',canFinalize:true}), '手续已齐备，待学院确认入学')
  assert.equal(vm.qualificationLabel({reportStatus:'COLLEGE_CONFIRMED'}), '入学手续已完成')
})

function setup(context) {
  const requests = []
  const calls = []
  const notices = []
  const modals = []
  const page = new Function('realRequest', 'toast', 'FilePreviewer', 'uni', script)(async (url, options) => {
    requests.push(url)
    calls.push({ url, options })
    if (typeof context === 'function') return context(url, options)
    if (context instanceof Error) throw context
    return context
  }, message => notices.push(message), {}, { showModal: options => modals.push(options) })
  const vm = { ...page.data(), ...page.methods }
  return { vm, requests, calls, notices, modals }
}

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function selectStudent(vm) {
  vm.canManage = true
  vm.selected = { id: '9007199254740993', name: '迎新联调同学', canFinalize: false }
  vm.detail = { student: { version: 12, steps: { INFO: 'PENDING' } } }
  vm.materials = [{ id: '6000000000000000001', version: 7, status: 'UPLOADED' }]
  vm.requestId = 'orientation-finalize-test'
}

test('orientation writes require current management permission and a writable healthy tenant', async () => {
  for (const context of [
    { permissionPatterns: ['studentAffairs.orientation.view'] },
    { permissionPatterns: ['*'], readonlyTenant: true },
    { permissionPatterns: ['*'], moduleAccessHealthy: false },
    new Error('offline'),
  ]) {
    const { vm, requests } = setup(context)
    vm.canManage = true
    await vm.loadPermissions()
    assert.equal(vm.canManage, false)
    vm.detail = { student: { version: 1 } }
    await vm.perform('verify')
    assert.deepEqual(requests, ['/rbac/current-context'])
  }
})

test('orientation manager and matching wildcard permissions enable the same worklist', async () => {
  for (const pattern of ['studentAffairs.orientation.manage', 'studentAffairs.orientation.*', 'studentAffairs.*', '*']) {
    const { vm } = setup({ permissionPatterns: [pattern] })
    await vm.loadPermissions()
    assert.equal(vm.canManage, true)
  }
})

test('material approval sends its observed version and reloads the same student qualification', async () => {
  const studentId = '9007199254740993'
  const approved = { id: '6000000000000000001', version: 8, status: 'APPROVED' }
  const detail = { student: { version: 13, steps: { MATERIAL: 'DONE' } } }
  const { vm, calls, notices } = setup((url, options) => {
    if (options?.method === 'POST') return { success: true }
    if (url === '/orientation/materials') return { items: [approved] }
    if (url === `/orientation/students/${studentId}`) return detail
    if (url === '/orientation/qualifications') return { items: [{ id: studentId, canFinalize: true }] }
    throw new Error(`Unexpected request: ${url}`)
  })
  selectStudent(vm)
  await vm.reviewMaterial(vm.materials[0], 'approve')
  assert.deepEqual(calls[0], {
    url: '/orientation/materials/6000000000000000001/approve',
    options: { method: 'POST', data: { expectedVersion: 7, comment: '移动端核验通过' } },
  })
  assert.equal(calls.length, 4)
  assert.deepEqual(calls[1].options.data, { orientationStudentId: studentId, page: 1, pageSize: 50 })
  assert.equal(calls[2].url, `/orientation/students/${studentId}`)
  assert.deepEqual(calls[3].options.data, { orientationStudentId: studentId, page: 1, pageSize: 1 })
  assert.deepEqual(vm.materials, [approved])
  assert.equal(vm.detail, detail)
  assert.equal(vm.selected.id, studentId)
  assert.equal(vm.selected.canFinalize, true)
  assert.equal(vm.materialBusy, '')
  assert.deepEqual(notices, ['材料已通过'])
})

test('material return conflict preserves the reason and original version without retrying', async () => {
  const { vm, calls, notices } = setup(() => { throw Object.assign(new Error('材料已更新，请刷新核对'), { status: 409 }) })
  selectStudent(vm)
  const material = vm.materials[0]
  vm.materialReasons[material.id] = '  请补充清晰的证件正面  '
  await vm.reviewMaterial(material, 'return')
  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0].options.data, { expectedVersion: 7, reason: '请补充清晰的证件正面' })
  assert.equal(vm.materialReasons[material.id], '  请补充清晰的证件正面  ')
  assert.equal(vm.materials[0].version, 7)
  assert.equal(vm.error, '材料已更新，请刷新核对')
  assert.equal(vm.materialBusy, '')
  assert.deepEqual(notices, [])
})

test('material return requires a useful explanation before making a request', async () => {
  const { vm, calls, notices } = setup({})
  selectStudent(vm)
  vm.materialReasons[vm.materials[0].id] = '不清楚'
  await vm.reviewMaterial(vm.materials[0], 'return')
  assert.equal(calls.length, 0)
  assert.deepEqual(notices, ['请填写不少于5字的具体补充要求'])
})

test('successful review with failed or missing qualification reports partial completion and disables stale actions', async () => {
  for (const failure of ['network', 'missing']) {
    const { vm, calls } = setup((url, options) => {
      if (options?.method === 'POST') return {}
      if (url === '/orientation/qualifications') {
        if (failure === 'network') throw new Error('网络中断')
        return { items: [] }
      }
      if (url === '/orientation/materials') return { items: [] }
      return { student: { version: 13 } }
    })
    selectStudent(vm)
    vm.selected.canFinalize = true
    await vm.reviewMaterial(vm.materials[0], 'approve')
    assert.equal(vm.error, '材料已处理，最新办理结果读取失败，请关闭后重新进入核对')
    assert.equal(vm.detail, null)
    assert.equal(vm.selected.canFinalize, false)
    assert.equal(vm.materialBusy, '')
    await vm.perform('finalize')
    await vm.reviewMaterial(vm.materials[0], 'approve')
    assert.equal(calls.length, 4)
    vm.close()
    assert.equal(vm.selected, null)
  }
})

test('material submission blocks another review, verification, final confirmation and object changes', async () => {
  const write = deferred()
  const { vm, calls, modals } = setup((url, options) => {
    if (options?.method === 'POST') return write.promise
    if (url === '/orientation/qualifications') return { items: [{ id: '9007199254740993', canFinalize: true }] }
    if (url === '/orientation/materials') return { items: [] }
    return { student: { version: 13 } }
  })
  selectStudent(vm)
  vm.selected.canFinalize = true
  const submitted = vm.reviewMaterial(vm.materials[0], 'approve')
  assert.equal(vm.materialBusy, '6000000000000000001')
  await vm.reviewMaterial(vm.materials[0], 'approve')
  await vm.perform('verify')
  await vm.perform('finalize')
  vm.confirmVerify()
  vm.confirmFinalize()
  vm.close()
  await vm.open({ id: 'another-student' })
  assert.equal(vm.selected.id, '9007199254740993')
  assert.equal(calls.length, 1)
  assert.equal(modals.length, 0)
  write.resolve({})
  await submitted
  assert.equal(vm.materialBusy, '')
})

test('verification submits the observed student version and blocks material review while pending', async () => {
  const write = deferred()
  const { vm, calls } = setup((url, options) => options?.method === 'POST' ? write.promise : { items: [], total: 0 })
  selectStudent(vm)
  const submitted = vm.perform('verify')
  assert.deepEqual(calls[0], {
    url: '/orientation/students/9007199254740993/verify',
    options: { method: 'POST', data: { passed: true, expectedVersion: 12 } },
  })
  await vm.reviewMaterial(vm.materials[0], 'approve')
  await vm.perform('finalize')
  assert.equal(calls.length, 1)
  write.resolve({})
  await submitted
  assert.equal(vm.selected, null)
  assert.equal(vm.busy, false)
})

test('late reads and errors cannot overwrite a reopened student or a closed sheet', async () => {
  for (const outcome of ['success', 'error', 'closed']) {
    const old = deferred()
    let reads = 0
    const { vm } = setup(url => {
      reads++
      if (reads <= 2) return old.promise
      return url === '/orientation/materials' ? { items: [{ id: 'new-material' }] } : { student: { version: 20 } }
    })
    const first = vm.open({ id: 'same-student', name: '旧列表学生' })
    vm.close()
    if (outcome !== 'closed') await vm.open({ id: 'same-student', name: '重新进入的学生' })
    if (outcome === 'error') old.reject(new Error('旧请求失败'))
    else old.resolve({ student: { version: 1 }, items: [{ id: 'old-material' }] })
    await first
    assert.equal(vm.error, '')
    if (outcome === 'closed') {
      assert.equal(vm.selected, null)
      assert.equal(vm.detail, null)
      assert.deepEqual(vm.materials, [])
    } else {
      assert.equal(vm.selected.name, '重新进入的学生')
      assert.equal(vm.detail.student.version, 20)
      assert.deepEqual(vm.materials, [{ id: 'new-material' }])
    }
  }
})

test('confirmation opened for one object cannot later submit another object', async () => {
  for (const method of ['confirmVerify', 'confirmFinalize']) {
    const { vm, calls, modals } = setup(url => url === '/orientation/materials' ? { items: [] } : { student: { version: 20 } })
    selectStudent(vm)
    vm.selected.canFinalize = true
    vm[method]()
    assert.equal(modals.length, 1)
    vm.close()
    await vm.open({ id: 'another-student', canFinalize: true })
    modals[0].success({ confirm: true })
    assert.equal(calls.filter(call => call.options?.method === 'POST').length, 0)
  }
})
