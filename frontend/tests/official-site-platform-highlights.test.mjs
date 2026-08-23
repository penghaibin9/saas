import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const pageSource = fs.readFileSync(path.join(root, 'src/views/official-site/OfficialPlatformCapabilityView.vue'), 'utf8')
const styleSource = fs.readFileSync(path.join(root, 'src/styles/official-platform-highlights.css'), 'utf8')

test('platform page promotes current foundation capabilities without reducing the product to module count', () => {
  for (const marker of [
    '学生 360° 成长工作台',
    '统一安全文件与版本中心',
    '跨业务统一审批中心',
    '业务待办一键直达',
    '可信 Excel 数据交换中心',
    '内置业务知识与操作帮助中心',
    '统一后台任务与批处理中心',
    '多租户、权限、数据范围与审计底座'
  ]) {
    assert.ok(pageSource.includes(marker), `missing current foundation capability: ${marker}`)
  }
})

test('platform eight highlights keep live and evolving states explicit', () => {
  for (const marker of [
    '跃科平台八大特色',
    '四端在线文档预览与批阅',
    '材料合规智能检查',
    '可信电子证据链',
    '全局业务搜索',
    '协同工作台',
    "status: '当前具备'",
    "status: '持续演进'",
    '尚未完成生产封板的能力统一标记为“持续演进”'
  ]) {
    assert.ok(pageSource.includes(marker), `missing truthful highlight marker: ${marker}`)
  }
  assert.ok(!pageSource.includes('已全面支持'))
  assert.ok(!pageSource.includes('全部已上线'))
})

test('ABCD evolution remains visible as the next platform layer', () => {
  for (const marker of [
    'ABCD · 下一阶段平台演进',
    '可信电子证据链 · 跨业务一致性巡检',
    '材料合规检查 · 动态业务表单',
    '文档版本比对 · 学生生命周期事实流',
    '全局业务搜索 · 任务池 / 认领 / 转办 / 代理 / SLA'
  ]) {
    assert.ok(pageSource.includes(marker), `missing ABCD marker: ${marker}`)
  }
})

test('platform eight-highlight page ships responsive dedicated styling', () => {
  for (const marker of [
    '.yk-highlight-hero',
    '.yk-highlight-foundation-grid',
    '.yk-highlight-feature-grid',
    '.yk-highlight-proof-grid',
    '.yk-highlight-evolution-grid',
    '@media (max-width: 720px)'
  ]) {
    assert.ok(styleSource.includes(marker), `missing eight-highlight style: ${marker}`)
  }
})
