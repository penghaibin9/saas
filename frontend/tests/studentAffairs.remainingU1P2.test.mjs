import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('U1 Student360 exposes six permission-scoped formal workbench actions with student context', () => {
  const page = read('src/views/admin/student/StudentDetailView.vue')
  for (const permission of [
    'studentAffairs.talk.create', 'studentAffairs.homeSchool.record.create',
    'studentAffairs.risk.create', 'studentAffairs.dorm.transfer.create',
    'studentAffairs.aid.create', 'studentAffairs.funding.create'
  ]) assert.match(page, new RegExp(permission.replaceAll('.', '\\.')))
  assert.match(page, /intent:\s*'create'/)
  assert.match(page, /studentId:\s*String\(this\.detail\.studentId\)/)
  assert.doesNotMatch(page, /source:\s*'student360'/)
})

test('B1 dorm candidates exhaust server pages without loading all beds', () => {
  const api = read('src/modules/studentAffairs/api/studentAffairsB.api.js')
  const page = read('src/modules/studentAffairs/views/dorm/DormTransferView.vue')
  assert.match(api, /async function collectPaged/)
  assert.match(api, /listAllDormBuildings/)
  assert.match(api, /listAllDormRooms/)
  assert.match(page, /listAllDormBuildings\(\)/)
  assert.match(page, /listAllDormRooms\(this\.dlg\.buildingId\)/)
  assert.doesNotMatch(page, /listDormBuildings\(\{ pageSize: 200 \}\)/)
})

test('P2 workbenches keep preview priority quick assignment and technical folding explicit', () => {
  const archive = read('src/modules/studentAffairs/views/ArchiveManageView.vue')
  const activity = read('src/modules/studentAffairs/views/activity/ActivityWorkbenchView.vue')
  const counselor = read('src/modules/studentAffairs/views/class/CounselorAssignmentView.vue')
  const discipline = read('src/modules/studentAffairs/views/DisciplineWorkbenchView.vue')
  assert.match(archive, /previewArchiveCollect/)
  assert.match(archive, /先预检范围/)
  assert.match(activity, /priority:\s*this\.activePriority/)
  assert.match(activity, /异常优先/)
  assert.match(counselor, /立即分配/)
  assert.match(counselor, /classId:\s*row\?\.classId/)
  assert.match(discipline, /<details class="dp-tech">/)
  assert.match(discipline, /技术与审计信息/)
})
