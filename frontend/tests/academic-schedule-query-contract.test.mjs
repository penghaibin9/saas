import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

test('weekly schedule query covers all five operational dimensions with searchable pickers', () => {
  const source = read('src/modules/academicAffairs/views/AaWeekScheduleView.vue')
  for (const label of ['班级', '教师', '教室', '学生', '教学班']) {
    assert.match(source, new RegExp(`label: '${label}'`))
  }
  for (const picker of ['AppClassPicker', 'AppTeacherPicker', 'AppClassroomPicker', 'AppStudentPicker', 'AppTeachingClassPicker']) {
    assert.match(source, new RegExp(`<${picker}`))
  }
  assert.match(source, /teacher: this\.teacherName \|\| '本人课表'/)
  assert.doesNotMatch(source, /teacher: `教师 \$\{this\.teacherKey\}`/)
})

test('teacher schedule responses expose a display name instead of forcing internal keys into the UI', () => {
  const teacherView = read('src/modules/academicAffairs/views/AaTeacherScheduleView.vue')
  const backend = read('../backend/app/modules/academic_affairs/services/academic_affairs_schedule_teacher_relation_guard.py')
  assert.match(teacherView, /teacherName \|\| '本人'/)
  assert.match(teacherView, /res\.data\.teacherName/)
  assert.match(backend, /"teacherName": next/)
})

test('schedule routes remain available for class teacher room student and teaching class queries', () => {
  const routes = read('src/modules/academicAffairs/academic-affairs.routes.js')
  for (const segment of ['schedule/class/', 'schedule/teacher/', 'schedule/room/', 'schedule/student/', 'schedule/teaching-class/']) {
    assert.match(routes, new RegExp(segment.replaceAll('/', '\\/')))
  }
})
