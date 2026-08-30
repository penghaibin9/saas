import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const here = dirname(fileURLToPath(import.meta.url))
const src = (path) => readFileSync(resolve(here, '..', path), 'utf8')

const routes = src('src/modules/graduation/routes.js')
const workspaces = src('src/modules/graduation/config/graduationWorkspaces.js')
const mentorList = src('src/modules/graduation/views/GraduationMentorListView.vue')
const mentorAssign = src('src/modules/graduation/views/GraduationMentorAssignView.vue')

test('mentor routes and workspaces do not use retired mentor.manage alias', () => {
  for (const source of [routes, workspaces, mentorList, mentorAssign]) {
    assert.doesNotMatch(source, /graduationDesign\.mentor\.manage/)
  }
  for (const routeName of [
    'graduation-mentor-create',
    'graduation-mentor-conflicts',
    'graduation-mentor-assign',
    'graduation-mentor-edit',
    'graduation-mentor-eval',
    'graduation-mentor-detail',
    'graduation-mentors'
  ]) {
    assert.match(routes, new RegExp(`name: '${routeName}'[^\n]*graduationDesign\\.student\\.manage`))
  }
})

test('compressed mentor workspace keeps student.manage as the readable management boundary', () => {
  for (const label of ['导师与分配', '分配冲突检测']) {
    assert.match(workspaces, new RegExp(`label: '${label}'[^\n]*graduationDesign\\.student\\.manage`))
  }
  assert.doesNotMatch(workspaces, /label: '导师名单'|label: '学生分配'/)
})

test('mentor list separates manage, import, export and assignment permissions', () => {
  for (const code of ['student.manage', 'student.import', 'student.export', 'topic.assign']) {
    assert.match(mentorList, new RegExp(`graduationDesign\\.${code.replace('.', '\\.')}`))
  }
  assert.match(mentorList, /canMentorManage\(\)[^{]*\{[^}]*student\.manage/)
  assert.match(mentorList, /canMentorImport\(\)[^{]*\{[^}]*student\.import/)
  assert.match(mentorList, /canMentorExport\(\)[^{]*\{[^}]*student\.export/)
  assert.match(mentorList, /canTopicAssign\(\)[^{]*\{[^}]*topic\.assign/)
})

test('mentor assignment form fails closed unless manage and assign are both granted', () => {
  assert.match(mentorAssign, /canAssignMentor\(\)\s*\{\s*return this\.canMentorManage && this\.canTopicAssign\s*\}/)
  assert.match(mentorAssign, /async created\(\)\s*\{\s*if \(!this\.canAssignMentor\) return/)
  assert.match(mentorAssign, /async submit\(\)\s*\{\s*if \(!this\.canAssignMentor\) return/)
  assert.match(mentorAssign, /<template v-if="canAssignMentor" #footer>/)
})
