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

test('analytics pages expose the design hierarchy without fabricating a time series', () => {
  for (const token of ['stats-kpi-grid', 'stats-analysis-grid', '同口径明细下钻', 'analyticsDistributionSpec', 'analyticsMetricSpec']) {
    assert.match(source, new RegExp(token))
  }
  assert.match(source, /当前接口未提供连续同口径快照/)
  assert.match(source, /不冒充周期趋势/)
  assert.match(source, /不及格人数[^\n]*不是学业预警条数/)
})

test('report export records scope, purpose and an honest blob receipt', () => {
  for (const token of ['统计导出流程', '三种范围不要混淆', '导出用途（至少5个字）', '收到服务端 Excel 文件']) {
    assert.match(source, new RegExp(token))
  }
  assert.match(source, /exportStats\(/)
  assert.match(source, /exp\.receipt = \{ fileName, completedAt:/)
})
