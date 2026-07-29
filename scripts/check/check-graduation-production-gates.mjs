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

requireFile('docs/06-开发施工与质量验收/施工记录/毕业设计中心-全角色E2E业务验收报告-20260722.md', '全角色 E2E 验收报告')
requireFile('docs/06-开发施工与质量验收/施工记录/毕业设计中心-生产级就绪与试点验收差距-20260723.md', '生产级就绪与试点差距短文')
requireFile('docs/06-开发施工与质量验收/施工记录/毕业设计中心-试点服升级与UAT验收清单-20260723.md', '试点服 UAT 验收清单')
requireFile('backend/scripts/bootstrap_graduation_pilot.py', '试点编排脚本')
requireFile('backend/scripts/_seed_graduation.py', '毕设种子脚本')
requireFile('backend/scripts/e2e_bootstrap_graduation_accounts.py', '多角色账号导入脚本')
requireFile('backend/scripts/e2e_verify_graduation_accounts.py', '账号校验脚本')
requireFile('backend/scripts/e2e_graduation_live_flow.py', '活体主线脚本')

const closureFiles = [
  ['backend/alembic/versions/0141_merge_gd_intern_affairs_heads.py', 'Alembic 多头合并迁移'],
  ['backend/alembic/versions/0142_gd_excellent_delay_workflows.py', '优秀成果与延期答辩迁移'],
  ['backend/app/core/mobile_graduation_permissions.py', '教师小程序动作权限门'],
  ['backend/app/api/v1/mobile_graduation_guard.py', '学生小程序任务书与延期路由'],
  ['backend/app/api/v1/student_portal_graduation_guard.py', '学生门户任务书与延期路由'],
  ['backend/app/api/v1/mobile_graduation_extension_teacher.py', '教师移动端延期审核路由'],
  ['backend/app/modules/graduation/routers/graduation_p0_guard.py', '毕业设计高风险写入口保护'],
  ['backend/app/modules/graduation/routers/graduation_sensitive_router.py', '毕业设计批次敏感接口'],
  ['backend/app/modules/graduation/routers/graduation_archive_sensitive_router.py', '毕业设计归档批次接口'],
  ['backend/app/modules/graduation/routers/graduation_extension.py', '优秀成果与延期答辩接口'],
  ['backend/app/modules/graduation/services/graduation_record_resolver.py', '毕业设计当前批次解析器'],
  ['backend/app/modules/graduation/services/graduation_taskbook_confirmation_service.py', '跨端任务书原子确认服务'],
  ['backend/app/modules/graduation/services/graduation_batch_context.py', '批次上下文守卫'],
  ['backend/app/modules/graduation/services/graduation_command_service.py', '事务并发收口服务'],
  ['backend/app/modules/graduation/services/graduation_topic_change_consistency.py', '选题变更并发服务'],
  ['backend/app/modules/graduation/services/graduation_mobile_teacher_service.py', '教师移动稳定身份服务'],
  ['backend/app/modules/graduation/services/graduation_archive_consistency.py', '归档真实证据与预览令牌'],
  ['backend/app/modules/graduation/services/graduation_audit_consistency.py', '域审计上下文修复'],
  ['backend/app/modules/graduation/services/graduation_response_mapper.py', '四端 DTO 响应映射'],
  ['backend/app/modules/graduation/services/graduation_extension_action_service.py', '扩展流程输入门禁'],
  ['backend/app/modules/graduation/services/graduation_extension_safety_service.py', '扩展流程权限并发安全层'],
  ['backend/app/modules/graduation/services/graduation_extension_query_service.py', '优秀成果候选查询'],
  ['backend/tests/test_graduation_round5_contracts.py', '四端收口合同测试'],
  ['backend/tests/test_graduation_round8_cross_client_audit.py', '四端业务节点静态审计'],
  ['backend/tests/test_graduation_round9_extension_safety_contracts.py', '扩展流程安全与 UI 合同'],
]
closureFiles.forEach(([file, label]) => requireFile(file, label))

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
if (!miniEnv.includes('if (env && env.PROD) return false')) failures.push('小程序生产构建未强制 useMock=false')
if (!miniEnv.includes('allowMockFallback')) failures.push('小程序缺少开发/生产 mock 回退隔离开关')
if (!miniRequest.includes('ENV.allowMockFallback && mockFn')) failures.push('小程序 realFirst 未限制 mock 回退环境')
if (mobileStudent.includes('body.get("plagiarismRate")')) failures.push('学生端仍可伪造毕业设计查重率')
if (!graduationService.includes('/api/v1/graduation/materials') || !graduationService.includes('resolve_material_download')) {
  failures.push('毕业设计材料未使用业务关系鉴权下载地址')
}
if (!gradeService.includes('Review and confirmed defense scores must exist before calculation')) {
  failures.push('毕业设计成绩核算未强制使用权威评阅/答辩数据')
}
const getGrade = gradeService.slice(gradeService.indexOf('def get_grade('), gradeService.indexOf('\ndef calculate_grade('))
if (getGrade.includes('db.commit()') || getGrade.includes('db.add(')) failures.push('GET 成绩仍有数据库写入')

const routeRegistration = read('backend/app/api/v1/route_registration.py')
const mobilePermissions = read('backend/app/core/mobile_graduation_permissions.py')
const p0Guard = read('backend/app/modules/graduation/routers/graduation_p0_guard.py')
const sensitive = read('backend/app/modules/graduation/routers/graduation_sensitive_router.py')
const archiveSensitive = read('backend/app/modules/graduation/routers/graduation_archive_sensitive_router.py')
const archiveConsistency = read('backend/app/modules/graduation/services/graduation_archive_consistency.py')
const mobileBridge = read('backend/app/modules/graduation/services/graduation_mobile_teacher_service.py')
const auditConsistency = read('backend/app/modules/graduation/services/graduation_audit_consistency.py')
const taskbookEvidence = read('backend/app/modules/graduation/services/graduation_taskbook_confirmation_service.py')
const defenseSchema = read('backend/app/modules/graduation/schemas/graduation_defense_score.py')
const gradeApi = read('frontend/src/modules/graduation/api/graduation-defense-grade.api.js')
const archiveApi = read('frontend/src/modules/graduation/api/graduation-risk-archive.api.js')
const topicMiniPage = read('miniapp/src/pages/teacher/graduation-topics/index.vue')

if (!mobilePermissions.includes('MOBILE_GRADUATION_ENDPOINT_PERMISSIONS') || !mobilePermissions.includes('require_mobile_graduation_request_permission')) {
  failures.push('教师小程序毕业设计未接动作级权限闸门')
}
if (mobilePermissions.includes('same_name_count')) failures.push('教师小程序仍使用同名临时封禁而非稳定身份')
if (!mobileBridge.includes('GraduationStudent.mentor_id == mentor.id')
    || !mobileBridge.includes('GraduationReview.reviewer_mentor_id == mentor.id')
    || mobileBridge.includes('advisor_name ==')) {
  failures.push('教师小程序仍未完成稳定导师/评阅身份收口')
}

const guardPos = routeRegistration.indexOf('api_router.include_router(graduation_p0_guard.router')
const sensitivePos = routeRegistration.indexOf('api_router.include_router(graduation_sensitive_router.router')
const archivePos = routeRegistration.indexOf('api_router.include_router(graduation_archive_sensitive_router.router')
const legacyPos = routeRegistration.indexOf('graduation, graduation_batch, graduation_student')
if (guardPos < 0 || sensitivePos < 0 || archivePos < 0 || !(guardPos < legacyPos && sensitivePos < legacyPos && archivePos < legacyPos)) {
  failures.push('毕业设计敏感精确路由未优先于旧路由注册')
}
if (!routeRegistration.includes('api_router.include_router(mobile_graduation_guard.router)')
    || routeRegistration.indexOf('api_router.include_router(mobile_graduation_guard.router)') > routeRegistration.indexOf('mobile.router,')) {
  failures.push('学生小程序任务书证据路由未优先注册')
}
if (!routeRegistration.includes('api_router.include_router(student_portal_graduation_guard.router)')
    || routeRegistration.indexOf('api_router.include_router(student_portal_graduation_guard.router)') > routeRegistration.indexOf('api_router.include_router(student_portal_router)')) {
  failures.push('学生门户任务书证据路由未优先注册')
}
if (!taskbookEvidence.includes('sign_biz_id = f"{gd_student.id}:v{version}"')
    || !taskbookEvidence.includes('PortalSignRecord.content_hash == content_hash')) {
  failures.push('任务书确认未按版本与正文哈希绑定证据')
}
if (!p0Guard.includes('毕业设计中心不再直接裁决最终毕业资格')) {
  failures.push('毕业设计中心仍缺少最终毕业资格写入口保护')
}

if ((sensitive.match(/batchId: int = Query\(\.\.\., ge=1\)/g) || []).length < 15) {
  failures.push('答辩/评阅/成绩敏感接口未全面强制 batchId')
}
if (!gradeApi.includes('function batchParams') || gradeApi.includes('gdFinalId: null')) {
  failures.push('PC 答辩成绩 API 未完整携带批次或仍发送空定稿 ID')
}
if (!archiveConsistency.includes('"sha256": row.sha256')
    || !archiveConsistency.includes('"confirmationHash": sign.content_hash')
    || !archiveConsistency.includes('hmac.compare_digest')
    || !archiveSensitive.includes('batchId: int = Query(..., ge=1)')) {
  failures.push('归档未同时具备真实文件哈希、任务书确认哈希、签名预览和批次守卫')
}
if (!archiveApi.includes('previewToken') || !archiveApi.includes('batch-generate/preview') || !archiveApi.includes('batch-file/preview')) {
  failures.push('PC 归档执行未绑定预览令牌')
}
if (!auditConsistency.includes('db-123') || !auditConsistency.includes('target.batch_id = _infer_batch_id')) {
  failures.push('毕业设计域审计未修复稳定 actor 或批次归属')
}
if (!defenseSchema.includes('class DefenseScoreEntryRequest')
    || !defenseSchema.includes('score: Optional[int]')
    || defenseSchema.split('class DefenseAbsenceRequest')[0].includes('class DefenseAbsenceRequest')) {
  failures.push('答辩评分 DTO 未正确登记评分/缺席字段')
}
if (!topicMiniPage.includes('Promise.allSettled') || topicMiniPage.includes('catch(() => [])')) {
  failures.push('教师小程序仍把权限/接口错误伪装为空待办')
}

const extensionRouter = read('backend/app/modules/graduation/routers/graduation_extension.py')
const extensionAction = read('backend/app/modules/graduation/services/graduation_extension_action_service.py')
const extensionSafety = read('backend/app/modules/graduation/services/graduation_extension_safety_service.py')
const extensionQuery = read('backend/app/modules/graduation/services/graduation_extension_query_service.py')
const extensionUi = read('frontend/src/modules/graduation/views/GraduationExtensionAdminPanel.vue')
const studentApi = read('frontend/src/modules/graduation/api/graduation-student.api.js')
const portalApp = read('student-portal/src/App.vue')
const mobileShell = read('miniapp/src/components/MobileGlobalState.vue')
const teacherDelayUi = read('miniapp/src/components/MobileGraduationDelayQueue.vue')

if (!extensionSafety.includes('def _assert_bound_advisor')
    || !extensionSafety.includes('IntegrityError')
    || !extensionSafety.includes('active_key == f"active:{student.id}"')
    || !extensionSafety.includes('def list_advisor_delays')
    || !extensionSafety.includes('_recompute_defense(db, old_group)')
    || !extensionSafety.includes('MAX_DEFENSE_STUDENTS')) {
  failures.push('优秀成果/延期答辩稳定导师、并发、再次申请或重新排期安全层不完整')
}
if (!extensionAction.includes('maximum: int = 1000')
    || !extensionAction.includes('附件证据最多 20 项')
    || !extensionAction.includes('date.fromisoformat')
    || !extensionRouter.includes('graduation_extension_action_service as action_svc')) {
  failures.push('优秀成果/延期答辩写入口未统一限制可审计文本、证据 DTO 与日期')
}
if (!extensionQuery.includes('"canNominate"')
    || !extensionUi.includes("can(row, 'majorReview')")
    || !extensionUi.includes("can(row, 'collegeReview')")
    || !extensionUi.includes("can(row, 'advisorReview')")
    || !extensionUi.includes("can(row, 'schedule')")) {
  failures.push('优秀成果/延期答辩学校端仍可能展示当前角色不可执行按钮')
}
if (!extensionUi.includes('supportError')
    || !extensionUi.includes('候选加载失败')
    || !extensionUi.includes('答辩组加载失败')) {
  failures.push('优秀成果/延期答辩辅助接口失败仍可能伪装为空数据')
}
if (!studentApi.includes('params: withBatch({ page: 1, pageSize: 200, ...params })')
    || !studentApi.includes('defenseDate: g.date || g.defenseDate')) {
  failures.push('答辩组选择器未绑定当前批次或未兼容 canonical date DTO')
}
if (!(portalApp.indexOf('<router-view />') < portalApp.indexOf('<GraduationExtensionPanel'))
    || !(mobileShell.indexOf('<slot v-if="state === \'ready\'"') < mobileShell.indexOf('<MobileGraduationExtensionPanel'))
    || !teacherDelayUi.includes('这不是“暂无待办”')) {
  failures.push('学生主流程、扩展事项或教师待办首屏层级仍不清晰')
}

if (failures.length) {
  console.error('毕业设计生产闸门失败：')
  failures.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log('毕业设计生产闸门通过：批次隔离、并发幂等、稳定身份、真实审计、归档证据、四端 DTO、扩展流程权限与错误态均已登记。')
console.log('提示：仍须 MySQL 迁移/并发测试、三端构建和学校 UAT 全绿后，才能由负责人决定合并。')
