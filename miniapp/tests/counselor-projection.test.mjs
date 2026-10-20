import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const api = fs.readFileSync(new URL('../src/services/realApi.js', import.meta.url), 'utf8')
const profile = fs.readFileSync(new URL('../src/pages/student/profile/index.vue', import.meta.url), 'utf8')
const classes = fs.readFileSync(new URL('../src/pages/teacher/my-classes/index.vue', import.meta.url), 'utf8')
const students = fs.readFileSync(new URL('../src/pages/teacher/my-students/index.vue', import.meta.url), 'utf8')
const statusTag = fs.readFileSync(new URL('../src/components/MobileStatusTag.vue', import.meta.url), 'utf8')
const notice = fs.readFileSync(new URL('../src/pages/teacher/notify-publish/index.vue', import.meta.url), 'utf8')

test('学生小程序档案展示同一班级主辅导员', () => {
  assert.match(api, /counselorName: d\.counselorName \|\| ''/)
  assert.match(profile, /班级 \/ 辅导员/)
  assert.match(profile, /p\.org\.counselorName \|\| '待分配'/)
})

test('教师小程序从本人班级下钻权威学生范围', () => {
  assert.match(classes, /teacherApi\.getMyClasses\(/)
  assert.match(students, /teacherStudentV3Api\.list/)
  assert.match(students, /classId: this\.classId/)
  assert.match(students, /decodeQueryText\(decodeQueryText\(q && q\.className\)\)/)
  assert.match(statusTag, /NORMAL: \{ label: '在读'/)
  assert.match(statusTag, /REGISTERED: \{ label: '已注册'/)
})

test('教师班级选择和通知发布均使用服务端搜索分页', () => {
  for (const source of [classes, notice]) {
    assert.match(source, /teacherApi\.getMyClasses\(\{ page: requestedPage, pageSize: CLASS_PAGE_SIZE/)
    assert.match(source, /keyword: this\.(keyword|classKeyword) \|\| undefined/)
    assert.match(source, /hasMore/)
    assert.doesNotMatch(source, /items\.slice\(/)
  }
})
