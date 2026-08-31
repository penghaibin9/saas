import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = (p) => fs.readFileSync(path.join(frontendRoot, p), 'utf8')
const readWorkspace = (p) => fs.readFileSync(path.join(workspaceRoot, p), 'utf8')

test('20K surfaces keep exact server paging and student PC lazy source loading', () => {
  const student = readWorkspace('student-portal/src/views/internship/InternshipView.vue')
  const applicant = readWorkspace('enterprise-portal/src/views/ApplicantListView.vue')
  const position = readWorkspace('enterprise-portal/src/views/PositionListView.vue')
  assert.match(student, /initialSources = \[\.\.\.new Set\(\['agreement', 'insurance', 'plan', tab\.value\]\)\]/)
  assert.match(student, /initialSources\.map\(\(key\) => loadTab\(key, true\)\)/)
  assert.doesNotMatch(student, /Promise\.all\(Object\.keys\(sources\)/)
  assert.match(applicant, /pageSize=50/)
  assert.match(applicant, /page\.value\*pageSize<total\.value/)
  assert.match(position, /pageSize=20,total=ref\(0\)/)
  assert.doesNotMatch(position, /items\.value\.filter\(/)
})

test('critical Staff and Student PC navigation exposes semantic state', () => {
  const archive = readFrontend('src/modules/internship/views/ArchiveView.vue')
  const dashboard = readFrontend('src/modules/internship/views/InternshipDashboardView.vue')
  const student = readWorkspace('student-portal/src/views/internship/InternshipView.vue')
  assert.match(archive, /role="tablist" aria-label="归档视图"/)
  assert.match(archive, /role="tab"/)
  assert.match(archive, /:aria-selected="tab === t\.key"/)
  assert.match(archive, /role="region" aria-labelledby="archive-workspace-title" aria-live="polite"/)
  assert.match(dashboard, /role="progressbar"/)
  assert.match(dashboard, /:aria-valuenow="batchProgress"/)
  assert.match(student, /:aria-current="tab === item\.key \? 'page' : undefined"/)
})

test('409 keeps the entered decision and 422 leaves all unrelated fields intact', () => {
  const attendance = readFrontend('src/modules/internship/views/AttendanceExceptionDetailView.vue')
  const leave = readFrontend('src/modules/internship/views/LeaveReviewView.vue')
  const score = readFrontend('src/modules/internship/views/ScoreView.vue')
  const attendanceSubmit = attendance.slice(attendance.indexOf('async submit()'), attendance.indexOf('</script>'))
  assert.match(attendanceSubmit, /isConflict\(res\)[\s\S]*?kept: this\.comment/)
  assert.ok(attendanceSubmit.indexOf("this.comment = ''") < attendanceSubmit.indexOf('else if (isConflict(res))'))
  assert.match(attendanceSubmit, /else \{[\s\S]*?this\.formError = res\.message/)
  assert.match(leave, /isConflict\(res\)[\s\S]*?kept: reason \|\| ''/)
  assert.match(leave, /if \(res\.code !== 0\) return toast\.error[\s\S]*?this\.cd\.visible = false/)
  assert.match(score, /if \(res\.code !== 0\) return toast\.error\(res\.message \|\| '核算失败'\)[\s\S]*?this\.closePanel\(\)/)
})

test('unknown command results are reconciled by a read and are never blindly replayed', () => {
  const archive = readFrontend('src/modules/internship/views/ArchiveView.vue')
  const api = readFrontend('src/modules/internship/api/archive.api.js')
  assert.match(archive, /status: 'UNKNOWN'/)
  assert.match(archive, /请勿盲目重复提交/)
  assert.match(archive, /await this\.openDetailById\(p\.id\)/)
  assert.doesNotMatch(api, /retry|replay/i)
})
