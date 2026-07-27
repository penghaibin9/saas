import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const exists = (file) => fs.existsSync(path.join(root, file))
const failures = []

const requireFile = (rel, label) => {
  if (!exists(rel)) failures.push(`缺少${label}：${rel}`)
}

// —— 证据与编排脚本指向（2026-07-23）——
requireFile(
  'docs/06-开发施工与质量验收/施工记录/毕业设计中心-全角色E2E业务验收报告-20260722.md',
  '全角色 E2E 验收报告',
)
requireFile(
  'docs/06-开发施工与质量验收/施工记录/毕业设计中心-生产级就绪与试点验收差距-20260723.md',
  '生产级就绪与试点差距短文',
)
requireFile(
  'docs/06-开发施工与质量验收/施工记录/毕业设计中心-试点服升级与UAT验收清单-20260723.md',
  '试点服 UAT 验收清单',
)
requireFile('backend/scripts/bootstrap_graduation_pilot.py', '试点编排脚本')
requireFile('backend/scripts/_seed_graduation.py', '毕设种子脚本')
requireFile('backend/scripts/e2e_bootstrap_graduation_accounts.py', '多角色账号导入脚本')
requireFile('backend/scripts/e2e_verify_graduation_accounts.py', '账号校验脚本')
requireFile('backend/scripts/e2e_graduation_live_flow.py', '活体主线脚本')

// —— 生产 Mock / 安全闸门 ——
// 2026-07-27 收口：PC 毕设 API 已重构为 callStrict/listStrict 生产路径——
// 失败统一走 toErr() 透出业务码/503001，不存在 mock 业务数据回退，比旧版
// canUseMockFallback() 守卫更严格。直接校验这条不回退的真实代码不变量。
const pcApi = read('frontend/src/modules/graduation/api/graduation.api.js')
if (!/function\s+toErr\s*\([^)]*\)\s*\{/.test(pcApi) || !pcApi.includes('code: 503001')) {
  failures.push('PC 毕设 API 缺少生产失败透出业务码/503001 的 toErr 实现')
}
if (/catch\s*\([^)]*\)\s*\{[^}]*return\s+mockFn\(\)/s.test(pcApi)) {
  failures.push('PC 毕设 API 存在无条件 mock 回退')
}

const miniEnv = read('miniapp/src/config/env.js')
const miniRequest = read('miniapp/src/services/request.js')
const mobileStudent = read('backend/app/services/mobile_student_service.py')
const graduationService = read('backend/app/modules/graduation/services/graduation_service.py')
const gradeService = read('backend/app/modules/graduation/services/graduation_grade_service.py')
if (!miniEnv.includes('if (env && env.PROD) return false')) {
  failures.push('小程序生产构建未强制 useMock=false')
}
if (!miniEnv.includes('allowMockFallback')) {
  failures.push('小程序缺少开发/生产 mock 回退隔离开关')
}
if (!miniRequest.includes('ENV.allowMockFallback && mockFn')) {
  failures.push('小程序 realFirst 未限制 mock 回退环境')
}
if (mobileStudent.includes('body.get("plagiarismRate")')) {
  failures.push('学生端仍可伪造毕业设计查重率')
}
if (!graduationService.includes('/api/v1/graduation/materials') || !graduationService.includes('resolve_material_download')) {
  failures.push('毕业设计材料未使用业务关系鉴权下载地址')
}
if (!gradeService.includes('Review and confirmed defense scores must exist before calculation')) {
  failures.push('毕业设计成绩核算未强制使用权威评阅/答辩数据')
}

if (failures.length) {
  console.error('毕业设计生产闸门失败：')
  failures.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log('毕业设计生产闸门通过：生产构建不回退 Mock；证据报告与试点编排脚本齐全。')
console.log('提示：试点 UAT 签字前不称「已可验收上线」。清单见 毕业设计中心-试点服升级与UAT验收清单-20260723.md')
