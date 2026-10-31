import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('../src/modules/academicAffairs/views/AaStatsOverviewView.vue', import.meta.url),
  'utf8'
)

test('AA-242 through AA-259 keep their design identities in the statistics workspace', () => {
  for (let id = 242; id <= 259; id++) assert.match(source, new RegExp(`AA-${id}`))
  for (const label of [
    '统计总览', '学籍统计', '学籍与注册', '开课与教学运行', '教学任务统计',
    '课表统计', '选课统计', '考试与成绩', '成绩统计', '学业与毕业',
    '毕业资格统计', '师资与资源', '教学资源统计', '报表与快照', '统计快照'
  ]) assert.match(source, new RegExp(label))
})

test('analytics workspace separates business metrics, distributions and missing trends', () => {
  for (const token of ['stats-kpi-grid', 'stats-analysis-grid', '业务指标', 'analyticsDistributionSpec', 'stats-attention']) assert.ok(source.includes(token))
  assert.doesNotMatch(source, /Number\.parseFloat|analyticsMetricSpec|当前指标构成/)
  assert.match(source, /暂无连续统计数据，可查看历史快照/)
  assert.match(source, /不同学期或范围的快照不能直接比较/)
  assert.match(source, /不及格成绩记录/)
  assert.match(source, /课程名称（仅筛选明细）/)
})

test('report export records scope, purpose and an honest blob receipt', () => {
  for (const token of ['导出用途（至少5个字）', '按当前权限与所选范围导出全部结果', '已收到系统生成的表格文件']) {
    assert.match(source, new RegExp(token))
  }
  assert.match(source, /exportStats\(/)
  assert.match(source, /exp\.receipt = \{ fileName, completedAt:/)
})
