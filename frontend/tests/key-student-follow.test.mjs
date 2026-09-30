import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

function view(api) {
  const source = readFileSync(new URL('../src/modules/studentAffairs/views/talk/KeyStudentFollowView.vue', import.meta.url), 'utf8')
  const imports = []
  const script = parse(source).descriptor.script.content.replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, names) => {
    imports.push(...names.split(',').map(x => x.trim())); return ''
  }).replace('export default', 'return')
  const component = new Function(...imports, script)(...imports.map(name => name === 'studentAffairsApi' ? api : {}))
  const vm = component.data()
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  return vm
}

test('talk queue uses server pagination and includes scheduled appointments', async () => {
  let params
  const vm = view({ getTalks: async p => { params = p; return { code: 0, data: { items: [{ talkId: '91' }], total: 221 } } } })
  vm.pagination.page = 11
  await vm.load()
  assert.deepEqual(params, { page: 11, pageSize: 20, status: 'PLANNED,SCHEDULED,FOLLOW_UP' })
  assert.equal(vm.pagination.total, 221)
  assert.equal(vm.items[0].talkId, '91')
})

test('risk queue filters at the server instead of losing matches beyond the first page', async () => {
  let params
  const vm = view({ getRisks: async p => { params = p; return { code: 0, data: { items: [], total: 0 } } } })
  vm.activeQueue = 'risk'
  await vm.load()
  assert.deepEqual(params, { page: 1, pageSize: 20, status: 'OPEN', priority: 'HIGH_CRITICAL' })
})

test('permission and network errors remain errors and release the spinner', async () => {
  const vm = view({ getTalks: async () => ({ code: 403, message: '无权查看' }) })
  await vm.load()
  assert.equal(vm.errorMessage, '无权查看')
  assert.equal(vm.loading, false)
  const offline = view({ getTalks: async () => { throw new Error('网络断开') } })
  await offline.load()
  assert.equal(offline.errorMessage, '网络断开')
  assert.equal(offline.loading, false)
})

test('late talk response cannot overwrite the selected risk queue', async () => {
  let finish
  const vm = view({ getTalks: () => new Promise(resolve => { finish = resolve }), getRisks: async () => ({ code: 0, data: { items: [{ riskId: '2' }], total: 1 } }) })
  const pending = vm.load()
  vm.activeQueue = 'risk'
  await vm.load()
  finish({ code: 0, data: { items: [{ talkId: '1' }], total: 30 } })
  await pending
  assert.deepEqual(vm.items, [{ riskId: '2' }])
  assert.equal(vm.pagination.total, 1)
})

test('talk handoff preserves the precise record and lossless student ID', () => {
  const vm = view({})
  let location
  vm.$router = { push: target => { location = target } }
  vm.openTalk({ studentId: '9007199254740993', talkId: '9007199254740995' })
  assert.deepEqual(location.query, { studentId: '9007199254740993', talkId: '9007199254740995' })
})

test('talk follow-up actions collect the backend-required business explanation', () => {
  assert.match(talkSource, /:phrase-scene-key="dialog\.phraseSceneKey"/)
  for (const action of ['follow', 'close', 'toRisk', 'toHomeSchool']) {
    assert.match(talkSource, new RegExp(`${action}: \\{[^\\n]+requireReason: true`))
  }
})

const talkSource = readFileSync(new URL('../src/modules/studentAffairs/views/TalkWorkbenchView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const loadTalks = new AsyncFunction('studentAffairsApi', talkSource.split('async loadList() {')[1].split('\n    },')[0])
function talkView() {
  return { $route: { query: { talkId: '9007199254740995' } }, studentFilter: { studentId: '9007199254740993' }, pagination: { page: 1, pageSize: 20 }, selected: { talkId: 'old' }, select(row) { this.selected = row } }
}
test('precise talk deep link loads its detail even when it is outside the first list page', async () => {
  const vm = talkView()
  let requested
  await loadTalks.call(vm, {
    getTalks: async () => ({ code: 0, data: { items: [], total: 25 } }),
    getTalkDetail: async id => { requested = id; return { code: 0, data: { talkId: id } } }
  })
  assert.equal(requested, '9007199254740995')
  assert.equal(vm.selected.talkId, requested)
})
test('denied talk deep link clears the previously selected student record', async () => {
  const vm = talkView()
  await loadTalks.call(vm, {
    getTalks: async () => ({ code: 0, data: { items: [], total: 0 } }),
    getTalkDetail: async () => ({ code: 403, message: '无权查看指定谈话' })
  })
  assert.equal(vm.selected, null)
  assert.equal(vm.listError, '无权查看指定谈话')
})
