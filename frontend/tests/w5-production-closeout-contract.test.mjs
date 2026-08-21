import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const read = (relative) => fs.readFileSync(path.resolve(here, relative), 'utf8')

const academicLayout = read('../src/modules/academicAffairs/views/AdminAcademicAffairsLayout.vue')
const semesterApi = read('../src/modules/academicAffairs/api/academic-semester-pilot.api.js')
const semesterView = read('../src/modules/academicAffairs/views/AaSemesterPilotView.vue')
const studentLayout = read('../src/modules/studentAffairs/views/AdminStudentAffairsLayout.vue')
const slaStrip = read('../src/modules/studentAffairs/components/StudentAffairsSlaStrip.vue')
const tempPanel = read('../src/modules/studentAffairs/components/CounselorTempExpiryPanel.vue')
const classApi = read('../src/modules/studentAffairs/api/class.api.js')
const semesterService = read('../../backend/app/modules/academic_affairs/services/academic_affairs_semester_pilot_service.py')
const scheduledJobs = read('../../backend/scripts/run_scheduled_jobs.py')

test('W5 real-semester acceptance stays a hidden archive-manage workspace', () => {
  assert.match(academicLayout, /AaSemesterPilotView/)
  assert.match(academicLayout, /ops === 'semester-pilot'/)
  assert.match(academicLayout, /academicAffairs\.archive\.manage/)
  assert.match(academicLayout, /\/admin\/academic-affairs\/archive/)
  assert.doesNotMatch(academicLayout, /navPlan[^\n]*semester-pilot/i)
})

test('W5 semester pilot is server-authoritative, real-data-only and six-stage', () => {
  assert.match(semesterApi, /\/academic-affairs\/semester-pilots/)
  assert.match(semesterApi, /\$\{BASE\}\/\$\{pilotId\}\/check/)
  assert.match(semesterApi, /\$\{BASE\}\/\$\{pilotId\}\/complete/)
  assert.match(semesterView, /CONFIRM_REAL_SEMESTER_COMPLETED/)
  for (const stage of ['BASELINE', 'PRE_TERM', 'IN_TERM', 'EXAM', 'GRADE', 'ARCHIVE']) {
    assert.match(semesterService, new RegExp(`\\("${stage}"`))
  }
  assert.match(semesterService, /eligibleForRealCompletion/)
  assert.match(semesterService, /real_data_confirmed/)
  assert.match(semesterService, /latest_evidence_hash/)
  assert.doesNotMatch(semesterService, /create_fake|seed_mock|generate_demo/i)
})

test('W5 SLA transparency reads one backend truth and does not invent browser due logic', () => {
  assert.match(studentLayout, /StudentAffairsSlaStrip kind="both"/)
  assert.match(slaStrip, /request\('\/student-affairs\/sla-config'\)/)
  assert.match(slaStrip, /dueAt \/ overdue \/ 升级等状态以后端事实为准/)
  assert.doesNotMatch(slaStrip, /Date\.now\(|new Date\([^)]*due|setTimeout\(/)
})

test('W5 temporary counselor expiry keeps scheduler primary and an idempotent permission-gated manual fallback', () => {
  assert.match(studentLayout, /CounselorTempExpiryPanel/)
  assert.match(studentLayout, /student-affairs-counselor-assignments/)
  assert.match(tempPanel, /studentAffairs\.class\.create/)
  assert.match(tempPanel, /\/student-affairs\/counselor-assignments\/scan-expired/)
  assert.match(tempPanel, /可安全重复执行/)
  assert.match(scheduledJobs, /scan_expired_temps/)
})

test('W5 legacy counselor assessment publish always carries optimistic version', () => {
  assert.match(classApi, /publish\(pid, version\)/)
  assert.match(classApi, /counselor-assessment\/periods\/\$\{pid\}\/publish/)
  assert.match(classApi, /body:\s*\{\s*version\s*\}/)
})
