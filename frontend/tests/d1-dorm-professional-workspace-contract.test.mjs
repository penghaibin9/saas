import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const nav = read('../src/config/navPlan.js')
const routes = read('../src/modules/studentAffairs/studentAffairs.routes.js')
const overview = read('../src/modules/studentAffairs/views/StudentAffairsDormitoryView.vue')
const resource = read('../src/modules/studentAffairs/views/dorm/DormResourceView.vue')
const checkin = read('../src/modules/studentAffairs/views/dorm/DormCheckinView.vue')
const transfer = read('../src/modules/studentAffairs/views/dorm/DormTransferView.vue')
const inspection = read('../src/modules/studentAffairs/views/dorm/DormCheckView.vue')
const exception = read('../src/modules/studentAffairs/views/dorm/DormExceptionView.vue')
const stats = read('../src/modules/studentAffairs/views/dorm/DormStatsView.vue')

test('D1 publishes one professional dorm cockpit and six real workspaces', () => {
  for (const [label, path] of [
    ['宿舍驾驶舱', '/admin/student-affairs/dormitory'],
    ['房源管理', '/admin/student-affairs/dorm/resource'],
    ['入住管理', '/admin/student-affairs/dorm/checkin'],
    ['调宿与退宿', '/admin/student-affairs/dorm/transfer'],
    ['宿舍检查', '/admin/student-affairs/dorm/check'],
    ['宿舍异常（含夜不归宿）', '/admin/student-affairs/dorm/exception'],
    ['宿舍统计', '/admin/student-affairs/dorm/stats']
  ]) {
    assert.match(nav, new RegExp(`I\\('${label.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}', '${path.replaceAll('/', '\\/')}', 'studentAffairs\\.dorm\\.view'\\)`))
  }
  assert.match(routes, /path: 'dormitory'[\s\S]*permissionKey: 'studentAffairs\.dorm\.view'/)
})

test('D1 room state has an exact building-room-bed drill chain into current-bed operations', () => {
  assert.match(resource, /applyRouteSelection\(\)/)
  assert.match(resource, /name: 'student-affairs-dorm-checkin'/)
  assert.match(resource, /buildingId: String\(this\.curBuilding\)/)
  assert.match(resource, /roomId: String\(this\.curRoom\)/)
  assert.match(resource, /bedId: String\(bed\.bedId\)/)
  assert.match(checkin, /this\.routeBedId = bedId/)
  assert.match(checkin, /studentAffairsApi\.dormCheckin/)
  assert.match(checkin, /studentAffairsApi\.createDormCheckout/)
})

test('D1 statistics drill down to authoritative room state instead of browser aggregates', () => {
  assert.match(stats, /studentAffairsApi\.getDormOccupancy\(\)/)
  assert.match(stats, /studentAffairsApi\.listDormBuildings\(\)/)
  assert.match(stats, /name: 'student-affairs-dorm-resource'/)
  assert.match(stats, /buildingId: String\(building\.buildingId\)/)
})

test('D1 workspaces retain formal transfer inspection and exception commands', () => {
  assert.match(transfer, /studentAffairsApi\.listDormTransfers/)
  assert.match(transfer, /studentAffairsApi\.reviewDormTransfer/)
  assert.match(inspection, /studentAffairsApi\.listDormCheckTasks/)
  assert.match(inspection, /studentAffairsApi\.submitDormCheckRecord/)
  assert.match(exception, /studentAffairsApi\.listDormExceptions/)
  assert.match(exception, /studentAffairsApi\.handleDormException/)
  assert.match(overview, /聚合待办数：后端未配置/)
})

test('D1 dorm UI contains no local business fixture or fake count authority', () => {
  const combined = [overview, resource, checkin, transfer, inspection, exception, stats].join('\n')
  assert.doesNotMatch(combined, /\bmock\b|假数据|演示环境|Math\.random|setTimeout\s*\(/i)
})
