import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import {
  STUDENT_AFFAIRS_WORKSPACE_META,
  STUDENT_AFFAIRS_WORKSPACES,
  countFormalPages
} from '../src/modules/studentAffairs/config/studentAffairsWorkspaceNavigation.js'

const root = new URL('../', import.meta.url)
const read = (path) => fs.readFileSync(new URL(path, root), 'utf8')

const EXPECTED = [
  ['01', '今日工作', 3],
  ['02', '唯一学生360', 10],
  ['03', '风险与重点学生', 4],
  ['04', '谈心家校与回访', 6],
  ['05', '请假与返校', 4],
  ['06', '困难与资助', 18],
  ['07', '违纪处分与教育', 4],
  ['08', '宿舍与公寓', 8],
  ['09', '活动与成长', 8],
  ['10', '数字迎新', 18],
  ['11', '心理专项', 5],
  ['12', '统计与档案', 4]
]

test('V6 workspace projection is exactly 12 workspaces and 92 formal pages', () => {
  assert.equal(STUDENT_AFFAIRS_WORKSPACES.length, 12)
  assert.equal(countFormalPages(), 92)
  assert.deepEqual(STUDENT_AFFAIRS_WORKSPACE_META, {
    workspaceCount: 12,
    formalPageCount: 92,
    allNodeCount: 102
  })
  assert.deepEqual(
    STUDENT_AFFAIRS_WORKSPACES.map((workspace) => [
      workspace.no,
      workspace.title,
      workspace.groups.reduce((sum, group) => sum + group.leaves.length, 0)
    ]),
    EXPECTED
  )
})

test('V6 workspace leaf ids are unique and use existing internal admin routes', () => {
  const leaves = STUDENT_AFFAIRS_WORKSPACES.flatMap((workspace) =>
    workspace.groups.flatMap((group) => group.leaves)
  )
  assert.equal(new Set(leaves.map((leaf) => leaf.id)).size, leaves.length)
  for (const leaf of leaves) {
    assert.match(leaf.path, /^\/admin\//, leaf.id)
    assert.doesNotMatch(leaf.path, /https?:|^\/\//, leaf.id)
    assert.ok(Array.isArray(leaf.permissionAny), leaf.id)
    assert.ok(leaf.permissionAny.length > 0, leaf.id)
  }
})

test('all 92 formal destinations exist in the generated real route index', () => {
  const routeIndex = JSON.parse(read('../shared/generated/route-index.json'))
  const exact = new Set(routeIndex.exact || [])
  const leaves = STUDENT_AFFAIRS_WORKSPACES.flatMap((workspace) =>
    workspace.groups.flatMap((group) => group.leaves)
  )
  for (const leaf of leaves) {
    const pathname = leaf.path.split(/[?#]/)[0]
    assert.ok(exact.has(pathname), `${leaf.id}: ${pathname}`)
  }
})

test('V6 projection keeps real cross-layout routes rather than inventing parallel pages', () => {
  const paths = new Set(STUDENT_AFFAIRS_WORKSPACES.flatMap((workspace) =>
    workspace.groups.flatMap((group) => group.leaves.map((leaf) => leaf.path.split(/[?#]/)[0]))
  ))
  for (const path of [
    '/admin/student-affairs/dashboard',
    '/admin/student/list',
    '/admin/campus-service/classes',
    '/admin/orientation',
    '/admin/student-affairs/risk',
    '/admin/student-affairs/talk',
    '/admin/student-affairs/leave',
    '/admin/student-affairs/aid',
    '/admin/student-affairs/funding',
    '/admin/student-affairs/discipline',
    '/admin/student-affairs/dormitory',
    '/admin/student-affairs/activity',
    '/admin/student-affairs/mental/summary',
    '/admin/student-affairs/stats'
  ]) assert.ok(paths.has(path), path)
})

test('all three real layouts mount the same V6 workspace navigation slot', () => {
  for (const path of [
    'src/modules/studentAffairs/views/AdminStudentAffairsLayout.vue',
    'src/views/admin/student/AdminStudentLayout.vue',
    'src/views/admin/orientation/AdminOrientationLayout.vue'
  ]) {
    const source = read(path)
    assert.match(source, /<template #menu>/, path)
    assert.match(source, /<StudentAffairsWorkspaceNav/, path)
    assert.match(source, /import StudentAffairsWorkspaceNav/, path)
  }
})

test('workspace component renders numbered workspaces, group tabs, detail projection and locked leaves', () => {
  const source = read('src/modules/studentAffairs/components/StudentAffairsWorkspaceNav.vue')
  assert.match(source, /data-workspace=/)
  assert.match(source, /role="tablist"/)
  assert.match(source, /isLeafLocked/)
  assert.match(source, /aria-current/)
  assert.match(source, /scrollIntoView/)
  assert.match(source, /scrollToTargetHash/)
  assert.match(source, /当前对象下钻/)
  assert.match(source, /学工工作区/)
  assert.match(source, /matchPermission/)
  assert.doesNotMatch(source, /priorityStudents|recommendedAction|dormExceptionCount/)
})
