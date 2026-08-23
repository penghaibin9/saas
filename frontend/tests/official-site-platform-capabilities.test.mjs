import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SEO_ROUTES } from '../src/config/officialSalesPages.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const mainSource = fs.readFileSync(path.join(root, 'src/main.js'), 'utf8')
const pageSource = fs.readFileSync(path.join(root, 'src/views/official-site/OfficialPlatformCapabilityView.vue'), 'utf8')
const styleSource = fs.readFileSync(path.join(root, 'src/styles/official-platform-highlights.css'), 'utf8')

test('platform route keeps official sales SEO truth but renders the dedicated capability narrative', () => {
  assert.ok(OFFICIAL_SALES_PAGE_MAP['/platform'])
  assert.ok(OFFICIAL_SEO_ROUTES.some((item) => item.path === '/platform'))
  assert.ok(mainSource.includes("page.path === '/platform'"))
  assert.ok(mainSource.includes('OfficialPlatformCapabilityView.vue'))
  assert.ok(pageSource.includes("syncOfficialSeo('/platform')"))
})

test('platform capability page preserves truthful build-status language', () => {
  for (const marker of [
    '平台八大特色 · 已具备能力与持续演进清晰区分',
    '只把已经进入当前产品代码与真实业务入口的能力标记为“当前具备”',
    '尚未完成生产封板的能力统一标记为“持续演进”',
    '具体交付范围以项目合同、正式版本与上线验收为准',
    '持续演进能力不会借这些截图伪装成“已全面上线”'
  ]) {
    assert.ok(pageSource.includes(marker), `missing truthfulness marker: ${marker}`)
  }
  assert.ok(!pageSource.includes('全部已支持'))
  assert.ok(!pageSource.includes('全部已上线'))
})

test('platform capability page promotes current foundation and eight flagship capabilities', () => {
  for (const marker of [
    '学生 360° 成长工作台',
    '统一安全文件与版本中心',
    '跨业务统一审批中心',
    '业务待办一键直达',
    '可信 Excel 数据交换中心',
    '内置业务知识与操作帮助中心',
    '统一后台任务与批处理中心',
    '四端在线文档预览与批阅',
    '材料合规智能检查',
    '可信电子证据链',
    '全局业务搜索',
    '协同工作台'
  ]) {
    assert.ok(pageSource.includes(marker), `missing platform capability copy: ${marker}`)
  }
})

test('platform capability page keeps ABCD as a clearly labeled evolution layer', () => {
  for (const marker of [
    'ABCD · 下一阶段平台演进',
    '可信电子证据链 · 跨业务一致性巡检',
    '材料合规检查 · 动态业务表单',
    '文档版本比对 · 学生生命周期事实流',
    '全局业务搜索 · 任务池 / 认领 / 转办 / 代理 / SLA'
  ]) {
    assert.ok(pageSource.includes(marker), `missing ABCD evolution copy: ${marker}`)
  }
})

test('platform capability page ships responsive dedicated styling', () => {
  for (const marker of [
    '.yk-highlight-hero',
    '.yk-highlight-foundation-grid',
    '.yk-highlight-feature-grid',
    '.yk-highlight-proof-grid',
    '.yk-highlight-evolution-grid',
    '@media (max-width: 720px)'
  ]) {
    assert.ok(styleSource.includes(marker), `missing platform capability style: ${marker}`)
  }
})
