import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { teacherServiceRoute } from '../src/services/teacherServiceCatalog.mjs'

const source = readFileSync(new URL('../src/pages/teacher/affairs/counselor-eval/index.vue', import.meta.url), 'utf8')
function mount(api, state = { generation: 1 }) {
  const script = source.split('<script>')[1].split('</script>')[0].replace(/^import .*$/gm, '').replace('export default', 'options =')
  const context = { options: null, api, currentSessionGeneration: () => state.generation,
    normalizeError: error => ({ text: error.message, pageState: 'error' }), toast() {}, uni: {} }
  vm.runInNewContext(script, context)
  const page = context.options.data()
  for (const [name, method] of Object.entries(context.options.methods)) page[name] = method.bind(page)
  return page
}

test('counselor evaluation uses its own registered entry instead of teaching evaluation', () => {
  assert.equal(teacherServiceRoute('counselorEval', 'org_personnel'), '/pages/teacher/affairs/counselor-eval/index')
  assert.notEqual(teacherServiceRoute('counselorEval', 'counselor'), teacherServiceRoute('evaluation', 'academic'))
})

test('rejected score submission retains the exact inspected version and input', async () => {
  let payload
  const page = mount({ saveCounselorEval: async body => { payload = body; throw new Error('记录已更新，请刷新核对') } })
  page.indicators = [{ indicatorId: '1', maxScore: 100 }]
  page.edit({ evalId: '9', periodCode: '2026-1', counselorKey: 'counselor_a', version: 4, scores: { 1: 70, old: 9 }, remark: '原评分备注' })
  page.form.scores[1] = '88'
  await page.submit()
  assert.equal(payload.version, 4)
  assert.equal(payload.scores[1], 88)
  assert.equal(payload.scores.old, 9)
  assert.equal(payload.remark, '原评分备注')
  assert.equal(page.form.scores[1], '88')
  assert.equal(page.busy, false)
  assert.match(page.actionError, /记录已更新/)
})

test('switching duty clears the old score draft and ignores its pending read', async () => {
  const state = { generation: 1 }
  const reads = []
  const page = mount({ getEvalIndicators: async () => ({ items: [] }), getCounselorEvals: () => new Promise(resolve => { reads.push(resolve) }) }, state)
  page.generation = 1
  page.form = { scores: { 1: 99 } }
  const oldRead = page.load()
  state.generation = 2
  const newRead = page.load()
  assert.equal(page.form, null)
  reads[1]({ items: [{ evalId: 'new' }], total: 1, capabilities: {} })
  await newRead
  reads[0]({ items: [{ evalId: 'old' }], total: 1, capabilities: { canScore: true } })
  await oldRead
  assert.equal(page.items[0].evalId, 'new')
  // 第一笔请求已因身份代次变化失效，不可回填旧职责数据。
  assert.equal(page.generation, 2)
  assert.equal(page.capabilities.canScore, undefined)
})

test('a failed next page keeps already loaded records usable', async () => {
  const page = mount({ getEvalIndicators: async () => ({ items: [] }), getCounselorEvals: async () => { throw new Error('下一页暂不可用') } })
  page.generation = 1; page.state = 'ready'; page.items = [{ evalId: '1' }]; page.page = 1; page.total = 2
  await page.load(true)
  assert.equal(page.state, 'ready')
  assert.equal(page.items.length, 1)
  assert.equal(page.page, 1)
  assert.match(page.listError, /下一页/)
})
