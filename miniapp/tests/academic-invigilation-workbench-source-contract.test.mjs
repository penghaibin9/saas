import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/pages/teacher/academic-affairs/index.vue', import.meta.url), 'utf8')
const publicService = readFileSync(
  new URL('../../backend/app/modules/academic_affairs/services/mobile_academic_affairs_public_service.py', import.meta.url),
  'utf8'
)

test('teacher academic home consumes canonical full invigilation workbench', () => {
  assert.match(page, /我的监考/)
  assert.match(page, /invigilationWorkbench/)
  assert.match(page, /visibleInvigilations/)
  assert.match(page, /upcomingCount/)
  assert.match(page, /confirmStatus/)
  assert.match(page, /workStatus/)
  assert.match(page, /主监考/)
  assert.match(page, /副监考/)
  assert.match(page, /查看全部/)

  // The workbench is read-only. Reassignment/assignment stays in the canonical exam facade.
  assert.doesNotMatch(page, /assignInvigilator|changeInvigilator|assign_invigilator|change_invigilator/)
})

test('mobile teacher schedule exposes workbench from same server-side today boundary', () => {
  assert.match(publicService, /academic_affairs_invigilation_workbench_service as invigilation_workbench/)
  assert.match(publicService, /enriched\["invigilationWorkbench"\]/)
  assert.match(publicService, /project_my_invigilations\(/)
  assert.match(publicService, /from_date=str\(result\.get\("todayDate"\) or ""\) or None/)
  assert.doesNotMatch(publicService, /AaExamInvigilator\(|change_invigilator\(|assign_invigilator\(/)
})
