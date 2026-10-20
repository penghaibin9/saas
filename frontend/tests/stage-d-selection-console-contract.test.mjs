import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/AaSelectionConsoleView.vue', import.meta.url)

test('Stage D 选课控制台首屏必须优先展示真实运行态、时间窗和下一动作', async () => {
  const source = await readFile(viewUrl, 'utf8')

  for (const token of [
    '当前批次运行态',
    '当前结论',
    '建议下一动作',
    'selectStartAt',
    'selectEndAt',
    'lowEnrollCount',
    'batchWindowText',
    'nextActionFor'
  ]) {
    assert.match(source, new RegExp(token))
  }

  assert.doesNotMatch(source, /healthScore|健康分|模拟请求量|mock chart/i)
})

test('Stage D 选课控制台保留既有真实生命周期和业务动作', async () => {
  const source = await readFile(viewUrl, 'utf8')

  for (const action of [
    "lifecycle('publishBatch', '发布')",
    "lifecycle('openBatch', '开选')",
    "lifecycle('closeBatch', '截止')",
    "lifecycle('lockBatch', '锁定名单')",
    "lifecycle('archiveBatch', '归档')",
    'api.batchStats',
    'api.listRounds',
    'api.listCourses',
    'api.courseRoster'
  ]) {
    assert.ok(source.includes(action), `missing existing selection action: ${action}`)
  }
})

test('Stage D 选课控制台使用真实容量进度且具备响应式收口', async () => {
  const source = await readFile(viewUrl, 'utf8')

  assert.match(source, /courseFillPct\(row\)/)
  assert.match(source, /row\.selectedCount/)
  assert.match(source, /row\.capacity/)
  assert.match(source, /row\.remain/)
  assert.match(source, /@media \(max-width: 1080px\)/)
  assert.match(source, /@media \(max-width: 760px\)/)
})


test('选课动作按正式权限展示，特殊工作区复用当前权限上下文', async () => {
  const source = await readFile(viewUrl, 'utf8')
  const special = await readFile(new URL('../src/modules/academicAffairs/components/parallel-a/AaSelectionSpecialWorkspace.vue', import.meta.url), 'utf8')
  for (const code of ['academicAffairs.selection.manage', 'academicAffairs.selection.lock', 'academicAffairs.selection.rule.manage', 'academicAffairs.selection.rosterView']) assert.ok(source.includes(code))
  assert.match(source, /matchPermission\(this\.ctx\.permissionPatterns/)
  assert.match(source, /:ctx="ctx"/)
  assert.match(source, /canManageSelection && current.status === 'LOCKED'/)
  assert.match(source, /canLockSelection && current.status === 'CLOSED'/)
  assert.match(source, /v-if="canReadRoster" @click="openRoster\(row\)"/)
  assert.match(special, /ruleWritable\(\) \{ return this\.canManageRule &&/)
  assert.match(special, /v-if="canManageRule" variant="primary"/)
  assert.match(special, /当前账号只可查阅正式规则/)
})
