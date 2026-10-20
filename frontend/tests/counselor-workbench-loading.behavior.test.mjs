import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { compileTemplate, parse } from '@vue/compiler-sfc'

const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/CounselorWorkbenchView.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const script = descriptor.script.content
  .replace(/^import[^\n]+\r?\n/gm, '')
  .replace(/components: \{[^\n]+\},/, 'components: {},')
  .replace('export default', 'return')

function mount(api) {
  const definition = new Function('studentAffairsApi', script)(api)
  const vm = { ...definition.data() }
  for (const [key, method] of Object.entries(definition.methods)) vm[key] = method.bind(vm)
  for (const [key, computed] of Object.entries(definition.computed)) {
    Object.defineProperty(vm, key, { get: () => computed.call(vm) })
  }
  return vm
}

test('counselor workbench asks each queue for a bounded exact preview and uses server totals', async () => {
  let riskQuery
  let talkQuery
  const vm = mount({
    getRisks: async query => {
      riskQuery = query
      return { code: 0, data: { items: [{ status: 'NEW', riskLevel: 'HIGH' }], total: 37, stats: { highCritical: 5 } } }
    },
    getTalks: async query => {
      talkQuery = query
      return { code: 0, data: { items: [{ status: 'PLANNED' }], total: 12 } }
    }
  })

  await vm.load()

  assert.deepEqual(riskQuery, { status: 'ACTIVE', pageSize: 10 })
  assert.deepEqual(talkQuery, { status: 'PLANNED,FOLLOW_UP', pageSize: 10 })
  assert.deepEqual(vm.metricCards.map(card => card.value), [37, 5, 12])
  assert.equal(vm.activeRisks.length, 1)
  assert.equal(vm.actionTalks.length, 1)
})

test('counselor workbench template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'CounselorWorkbenchView.vue', id: 'workbench' }).errors, [])
})
