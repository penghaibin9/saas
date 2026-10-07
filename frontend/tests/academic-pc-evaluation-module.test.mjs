import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/AaEvaluationConsoleView.vue', import.meta.url)

test('AA-234~AA-241 expose eight distinct evaluation workspaces', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    "{ key: 'batches', label: '评价批次' }",
    "{ key: 'appeals', label: '申诉审核' }",
    "{ key: 'studentEval', label: '学生评教' }",
    "{ key: 'selfEval', label: '教师自评' }",
    "{ key: 'peerEval', label: '同行评价' }",
    "{ key: 'supervisorEval', label: '督导评价' }",
    "{ key: 'evalStats', label: '评价统计' }",
    "{ key: 'archive', label: '评价归档' }"
  ]) assert.ok(source.includes(token), `missing evaluation entry: ${token}`)
})

test('role evaluation uses the current evaluator task feed and a locked submit command', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    'api.myRoleTasks(type)',
    'const taskId = this.selectedTask.taskId',
    'const response = await api.submit(payload)',
    '提交后不可重复提交，下一责任岗位为评价核算岗',
    "this.selectedTask.batchStatus === 'OPEN'",
    'taskId: task.taskId, batchId: task.batchId'
  ]) assert.ok(source.includes(token), `missing role task contract: ${token}`)
})

test('student monitoring stays anonymous and role task generation uses the formal endpoints', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.ok(source.includes("api.listTasks(id, { evaluatorType: 'STUDENT' })"))
  assert.ok(source.includes("api.genTasks(batchId, ids, 'STUDENT')"))
  assert.ok(source.includes('api.genRoleTasks(batchId, type'))
  assert.ok(source.includes('教师端不读取或暴露评价人身份'))
  assert.doesNotMatch(source, /api\.genTasks\(batchId, ids, type\)/)
})

test('appeal review binds the visible appeal and result before each high-risk action', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    '申诉 #${row.appealId}、结果 #${row.resultId}',
    "api.reviewAppeal(row.appealId, 'RESOLVE', note)",
    "api.reviewAppeal(id, 'REJECT', String(reason || '').trim())",
    '服务端将按当前账号数据范围复核本级权限',
    'syncObjectQuery({ appealId: row.appealId })'
  ]) assert.ok(source.includes(token), `missing appeal evidence/locking contract: ${token}`)
})

test('statistics, archive and failures use the server response honestly', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    'this.stats?.participation || {}',
    'this.results = res.data.list',
    "this.readError = res.message || '评价结果加载失败'",
    '当前接口未返回独立 Manifest 版本号',
    '未发布草稿不形成档案',
    '提交数取自正式答卷事实'
  ]) assert.ok(source.includes(token), `missing honest evaluation response contract: ${token}`)
})

test('large task batches render a bounded local page until the API supports server paging', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.ok(source.includes('taskPagination: freshPagination(20)'))
  assert.ok(source.includes('return this.tasks.slice(start, start + this.taskPagination.pageSize)'))
  assert.ok(source.includes(':rows="visibleTasks"'))
  assert.ok(source.includes('@page-change="onTaskPageChange"'))
})
