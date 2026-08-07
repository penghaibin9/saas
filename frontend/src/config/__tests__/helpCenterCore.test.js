import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildHelpSearchText,
  isHelpVisibleForRole,
  normalizeHelpRole,
  resolveHelpRole,
  uniqueHelpEntries
} from '../helpCenterCore.js'

test('maps runtime role codes and Chinese labels', () => {
  assert.equal(resolveHelpRole('SCHOOL_ADMIN'), 'school-admin')
  assert.equal(resolveHelpRole('COUNSELOR'), 'student-affairs')
  assert.equal(resolveHelpRole('GRADUATION_TEACHER'), 'teacher')
  assert.equal(resolveHelpRole('', '教务管理员'), 'academic')
  assert.equal(normalizeHelpRole('学生'), 'student')
  assert.equal(normalizeHelpRole('STUDENT_AFFAIRS_ADMIN'), 'student-affairs')
  assert.equal(normalizeHelpRole('学生处管理员'), 'student-affairs')
})

test('role filtering is permissive for unknown legacy metadata', () => {
  assert.equal(isHelpVisibleForRole({ roles: ['未登记的新角色'] }, 'teacher'), true)
  assert.equal(isHelpVisibleForRole({ roles: ['学生'] }, 'student'), true)
  assert.equal(isHelpVisibleForRole({ roles: ['学生'] }, 'teacher'), false)
  assert.equal(isHelpVisibleForRole({ roles: ['学生'] }, 'school-admin'), true)
})

test('search text includes nested steps, faq and warnings', () => {
  const text = buildHelpSearchText({
    title: '中期检查',
    steps: [{ name: '整改复查', detail: '限期整改后重新提交' }],
    faq: [{ q: '为什么不能提交', a: '检查业务状态' }],
    warnings: ['正式发布后不可随意修改']
  })
  assert.match(text, /限期整改/)
  assert.match(text, /业务状态/)
  assert.match(text, /正式发布/)
})

test('search text indexes task prerequisites outcomes troubleshooting platforms and related entries', () => {
  const text = buildHelpSearchText({
    title: '移动请假',
    platforms: ['微信小程序'],
    mobilePath: 'pages/student/affairs/leave',
    prerequisites: ['先完成学生身份绑定'],
    successCriteria: ['重新进入审批队列'],
    troubleshooting: ['修改已保存但重提失败时继续原申请'],
    related: [{ label: '账号异常排查', route: '/admin/system/account-exceptions' }]
  })

  assert.match(text, /微信小程序/)
  assert.match(text, /pages\/student\/affairs\/leave/)
  assert.match(text, /学生身份绑定/)
  assert.match(text, /重新进入审批队列/)
  assert.match(text, /重提失败/)
  assert.match(text, /账号异常排查/)
  assert.match(text, /\/admin\/system\/account-exceptions/)
})

test('deduplicates entries by stable item id', () => {
  const first = { item: { id: 'a' }, type: 'card' }
  const second = { item: { id: 'a' }, type: 'doc' }
  const third = { item: { id: 'b' }, type: 'flow' }
  assert.deepEqual(uniqueHelpEntries([first, second, third]), [first, third])
})
