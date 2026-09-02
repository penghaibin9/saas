import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { GRADUATION_WORKSPACES } from '../src/modules/graduation/config/graduationWorkspaces.js'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('V8 keeps eight workspaces and compresses the primary sidebar to 24 entries', () => {
  assert.equal(GRADUATION_WORKSPACES.length, 8)
  assert.equal(GRADUATION_WORKSPACES.reduce((sum, workspace) => sum + workspace.children.length, 0), 24)
  assert.deepEqual(GRADUATION_WORKSPACES.map((workspace) => workspace.label), [
    '我的工作台', '批次与实施', '题目与选题', '过程指导',
    '开题与成果', '答辩与成绩', '风险与归档', '模板与设置'
  ])
})

test('V8 legacy batch query routes land on the requested batch configuration view', async () => {
  const source = await read('../src/modules/graduation/views/GraduationBatchListView.vue')
  assert.match(source, /query\.batchId/)
  assert.match(source, /tab: panel/)
  assert.match(source, /`\/admin\/graduation\/batches\/\$\{batchId\}`/)
})

test('V8 student and topic pages expose five primary groups while preserving every legacy panel', async () => {
  const [students, topics] = await Promise.all([
    read('../src/modules/graduation/views/GraduationStudentListView.vue'),
    read('../src/modules/graduation/views/TopicLibListView.vue')
  ])
  for (const label of ['名单', '进度与风险', '关系与资格', '材料与答辩', '收口与归档']) {
    assert.match(students, new RegExp(`label: '${label}'`))
  }
  for (const panel of ['roster', 'progress', 'risk', 'mentor', 'topic', 'eligibility', 'grouping', 'materials', 'defense', 'grad-qual', 'archive']) {
    assert.ok(students.includes(`'${panel}'`), `student legacy panel ${panel} must remain`)
  }
  for (const label of ['题目库', '审核', '质量治理', '容量', '历史']) {
    assert.match(topics, new RegExp(`label: '${label}'`))
  }
  for (const panel of ['list', 'pending', 'teacher-apply', 'enterprise', 'student-proposed', 'category', 'capacity', 'requirements', 'attachments', 'history', 'archive']) {
    assert.ok(topics.includes(`'${panel}'`), `topic legacy panel ${panel} must remain`)
  }
})

test('V6 student ledger keeps the real master, read-only academic mirror and recoverable work context', async () => {
  const source = await read('../src/modules/graduation/views/GraduationStudentListView.vue')

  assert.match(source, /毕业资格是教务只读镜像/)
  assert.match(source, /教务只读镜像/)
  assert.ok(!source.includes('gdStudentApi.setGradQual'), 'graduation UI must not write the academic graduation qualification mirror')

  for (const queryKey of ['batchId', 'panel', 'page', 'keyword', 'returnTo']) {
    assert.ok(source.includes(queryKey), `student work context must preserve ${queryKey}`)
  }
  assert.match(source, /buildListQuery\(overrides = \{\}\)/)
  assert.match(source, /studentReturnQuery\(panel = this\.activePanel\)/)
  assert.match(source, /returnTo: this\.currentListPath\(panel\)/)

  assert.match(source, /loadToken/)
  assert.match(source, /statsToken/)
  assert.match(source, /token !== this\.loadToken/)
  assert.match(source, /token !== this\.statsToken/)
  assert.match(source, /String\(batchId\) !== String\(this\.batchStore\.selectedBatchId\)/)

  assert.match(source, /AppExcelImportDrawer/)
  assert.match(source, /downloadImportTemplate/)
  assert.match(source, /uploadImportXlsx/)
  assert.match(source, /importConfirm\(rows, previewToken\)/)
  assert.match(source, /downloadImportErrors/)
  for (const step of ['下载模板', '上传并预览', '下载错误行', '确认导入并留痕']) {
    assert.match(source, new RegExp(step))
  }
})
