import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const failures = []

const pcApi = read('frontend/src/modules/graduation/api/graduation.api.js')
if (!pcApi.includes('canUseMockFallback()')) {
  failures.push('PC 毕设 API 未经生产 mock fallback 闸门')
}
if (/catch\s*\([^)]*\)\s*\{[^}]*return\s+mockFn\(\)/s.test(pcApi) && !pcApi.includes('if (canUseMockFallback()) return mockFn()')) {
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
if (!graduationService.includes('/api/v1/graduation/materials/')) {
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

console.log('毕业设计生产闸门通过：生产构建不回退 Mock 业务数据。')
