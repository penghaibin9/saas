import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const api = read('../src/services/affairsFourEndApi.js')
const view = read('../src/views/affairs/AffairsFourEndView.vue')

test('D3 student PC uses batch-scoped initial selection endpoints', () => {
  assert.match(api, /\/mobile\/affairs\/dorm\/select-options/)
  assert.match(api, /\/mobile\/affairs\/dorm\/buildings\/\$\{enc\(buildingId\)\}\/rooms/)
  assert.match(api, /\/mobile\/affairs\/dorm\/rooms\/\$\{enc\(roomId\)\}\/beds/)
  assert.match(api, /\/mobile\/affairs\/dorm\/beds\/\$\{enc\(bedId\)\}\/self-select/)
})

test('D3 student PC distinguishes a reserved first bed from formal transfer', () => {
  assert.match(view, /确认后床位将为你预留，不能自行更换/)
  assert.match(view, /已有床位时只能提交正式调宿申请/)
  assert.match(view, /审批完成前原床保持不变/)
  assert.doesNotMatch(view, /入住成功|已正式入住/)
})
