import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const api = read('../src/modules/studentAffairs/api/studentAffairs.api.js')
const checkin = read('../src/modules/studentAffairs/views/dorm/DormCheckinView.vue')
const transfer = read('../src/modules/studentAffairs/views/dorm/DormTransferView.vue')
const studentApi = read('../../student-portal/src/services/affairsFourEndApi.js')
const studentView = read('../../student-portal/src/views/affairs/AffairsFourEndView.vue')
const miniApi = read('../../miniapp/src/services/affairsContractApi.js')
const miniView = read('../../miniapp/src/pages/student/affairs/dorm.vue')

test('D4 teacher PC separates checkout request from dorm-manager confirmation', () => {
  assert.match(api, /createDormCheckout\(body\)/)
  assert.match(api, /confirmDormCheckout\(requestId, version\)/)
  assert.match(api, /listDormStays/)
  assert.match(checkin, /宿管确认前床位和住宿关系保持不变/)
  assert.match(transfer, /退宿待确认/)
  assert.match(transfer, /confirmDormCheckout/)
  assert.match(transfer, /住宿历史/)
  assert.match(transfer, /确认退宿并释放床位/)
  assert.doesNotMatch(transfer, /window\.confirm/)
})

test('D4 student PC and miniapp expose canonical stay history', () => {
  assert.match(studentApi, /myDormStays/)
  assert.match(studentView, /DORM_STAY_COLS/)
  assert.match(studentView, /住宿历史/)
  assert.match(studentView, /DORM_STAY_STATUS/)
  assert.match(studentView, /已退宿/)
  assert.match(miniApi, /getMyDormStays/)
  assert.match(miniView, /住宿历史/)
  assert.match(miniView, /checkoutAt/)
  assert.match(miniView, /stayStatusLabel/)
})
