import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8')

test('归档与教务主层不输出 evidence JSON、规则码或批次数据库 ID', async () => {
  const [archive, dashboard, term, scheduling] = await Promise.all([
    read('src/modules/academicAffairs/views/ArchivePrecheckView.vue'),
    read('src/modules/academicAffairs/views/AaDashboardView.vue'),
    read('src/modules/academicAffairs/views/AaTermDetailView.vue'),
    read('src/modules/academicAffairs/views/AaSchedulingConsoleView.vue')
  ])
  assert.doesNotMatch(archive, /JSON\.stringify\(\(evidence/)
  assert.match(archive, /<summary>技术依据<\/summary>/)
  assert.doesNotMatch(dashboard, /<code>\{\{ item\.ruleCode \}\}<\/code>/)
  assert.doesNotMatch(term, /<code>\{\{ row\.code \}\}<\/code>/)
  assert.doesNotMatch(scheduling, /`批次 \$\{row\.batchId\}`/)
})

test('系统治理页面使用业务选择器和结构化摘要', async () => {
  const [jobs, access, masterData, security] = await Promise.all([
    read('src/modules/system/views/SystemJobCenterView.vue'),
    read('src/modules/system/views/SystemAccessGovernanceView.vue'),
    read('src/modules/system/views/SystemMasterDataView.vue'),
    read('src/modules/system/views/SystemSecurityChangeView.vue')
  ])
  assert.doesNotMatch(jobs, /JSON\.stringify\(evidence\.scopeSnapshot/)
  assert.match(jobs, /授权依据摘要/)
  assert.match(access, /AppRemoteSelect/)
  assert.match(access, /AppOrgCascader/)
  assert.doesNotMatch(access, /placeholder="如 SYS_ADMIN"/)
  assert.doesNotMatch(masterData, /填写账号 userId/)
  assert.doesNotMatch(masterData, /'userId ' \+ row\.ownerUserId/)
  assert.doesNotMatch(security, /JSON\.stringify\(im\.change/)
  assert.doesNotMatch(security, /<td class="is-who">\{\{ i\.targetId \}\}<\/td>/)
})

test('平台学生门户配置由租户上下文驱动且不输出 JSON 预览', async () => {
  const source = await read('src/modules/platform/components/StudentPortalConfigPanel.vue')
  assert.doesNotMatch(source, /真实租户ID|mock ID|JSON\.stringify\(this\.form/)
  assert.match(source, /最终配置预览/)
  assert.match(source, /未识别模块（请联系平台管理员）/)
  assert.match(source, /配置已保存并记录操作日志/)
})
