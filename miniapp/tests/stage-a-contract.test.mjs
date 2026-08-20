import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

// 统一规范化换行：本仓库在 Windows 检出为 CRLF、Linux CI 为 LF，而下方多处断言按
// 源码缩进结构匹配多行片段并硬编码 \n。不归一化会导致同一份代码在 Linux 全绿、在
// Windows 开发机上假失败（2026-08-04 复审定位：这正是此前"1 项失败"的真实原因，
// 属测试可移植性缺陷，不是被测代码的问题）。
const read = (relative) =>
  fs.readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n')

test('student home uses one aggregate request and lightweight message summary', () => {
  const page = read('src/pages/student/home/index.vue')
  const api = read('src/services/studentApi.js')
  const adapter = read('src/services/realApi.js')
  assert.doesNotMatch(page, /loadEmergency|getMessages\(\)/)
  assert.match(page, /messageSummary\?\.latestEmergency/)
  assert.match(page, /HOME_TTL_MS = 20_000/)
  assert.match(page, /_loadEpoch/)
  assert.match(api, /real\.studentHomeReal\(\)/)
  // 这两个字段原来在适配层里被硬编码成空数组，页面因此永远渲染“暂无常用服务/暂无今日课程”。
  // V3 §0.1 要求首页只消费 canonical server truth：它们现在原样透传服务端 HomeProjection，
  // 适配层依然不许自己编造内容（下面的 mock 断言保持不变）。
  const homeAdapter = adapter.match(/export async function studentHomeReal\(\)[\s\S]*?\n\}/)[0]
  assert.match(homeAdapter, /quickServices: Array\.isArray\(ov && ov\.quickServices\) \? ov\.quickServices : \[\]/)
  assert.match(homeAdapter, /today: Array\.isArray\(ov && ov\.today\) \? ov\.today : \[\]/)
  assert.doesNotMatch(homeAdapter, /quickServices: \[\]\s*,/)
  assert.doesNotMatch(homeAdapter, /\.\.\.mock|mockHome/)
})

test('teacher workbench has TTL checks and one final aggregate HTTP endpoint', () => {
  const page = read('src/pages/teacher/workbench/index.vue')
  // V3 S1.5：全局安装器已按端拆分，教师高频接口适配只在教师分包页面显式安装。
  const installer = read('src/services/mobilePerformanceInstaller.teacher.js')
  assert.doesNotMatch(page, /onShow\(\) \{ this\.load\(\) \}/)
  assert.match(page, /WORKBENCH_TTL_MS = 20_000/)
  assert.match(page, /getTeacherWorkbenchVersion/)
  assert.match(page, /loadInternshipContext/)
  const loadBlock = page.match(/load\(\{ force = false[\s\S]*?\n    \},\n    quick\(q\)/)[0]
  assert.equal((loadBlock.match(/teacherApi\.getWorkbench/g) || []).length, 1)
  assert.match(installer, /\/mobile\/performance\/teacher\/workbench\?pageSize=8/)
  assert.equal((installer.match(/teacherApi\.getWorkbench\s*=/g) || []).length, 1)
  assert.doesNotMatch(
    installer.match(/teacherApi\.getWorkbench[\s\S]*?teacherApi\.getTodosPage/)[0],
    /Promise\.allSettled/
  )
})

test('ordinary GETs are single-flight and writes are rejected rather than deduplicated', () => {
  const request = read('src/services/request.js')
  assert.match(request, /const _getInflight = new Map\(\)/)
  assert.match(request, /if \(normalizedMethod === 'GET'\)/)
  assert.match(request, /return _getInflight\.get\(key\)/)
  assert.match(request, /const _mutationInflight = new Set\(\)/)
  assert.match(request, /正在提交，请勿重复点击/)
  assert.match(request, /markMobileViewsDirty\(path\)/)
  assert.match(request, /body\.code === 401001[\s\S]*?_retried: true/)
  for (const code of ['403001', '409001', '422001', '429001']) assert.match(request, new RegExp(code))
  assert.doesNotMatch(request, /while \(current\.hasMore/)
  assert.match(request, /export function realUpload/)
  assert.match(request, /export function realDownload/)
})

test('production session skeleton contains no fixed student or teacher identity', () => {
  const session = read('src/stores/session.js')
  assert.match(session, /import\.meta\.env && import\.meta\.env\.PROD/)
  assert.match(session, /neutralUser/)
  assert.match(session, /name: '', studentNo: '', className: ''/)
})

test('teacher login accepts the backend academic role codes', () => {
  const login = read('src/components/login/MiniLoginAuthPanel.vue')
  const roles = read('src/config/roles.config.js')
  assert.match(login, /roleKeyFromBackendRole\(roleCode\)/)
  assert.match(roles, /ACADEMIC_TEACHER: ROLE\.ACADEMIC/)
  assert.match(roles, /ACADEMIC_ADMIN: ROLE\.ACADEMIC/)
})

test('real teacher contexts drive identity switching with canonical role keys', () => {
  const roles = read('src/config/roles.config.js')
  const session = read('src/stores/session.js')
  assert.match(roles, /INTERN_MENTOR: ROLE\.INTERN_MENTOR/)
  assert.match(roles, /roleKeyFromBackendRole\(roleCode\)/)
  assert.match(session, /this\.availableRoles = \[\.\.\.new Set\(this\.availableContexts/)
  assert.match(session, /roleKeyFromBackendRole\(item\.roleCode \|\| item\.contextType\) === roleKey/)
  assert.doesNotMatch(session, /item\.roleCode === roleKey/)
})

test('high-frequency message, todo and risk pages use final database pagination endpoints', () => {
  const messages = read('src/pages/student/messages/index.vue')
  const todos = read('src/pages/teacher/todos/index.vue')
  const risks = read('src/pages/teacher/risk-students/index.vue')
  const todoApi = read('src/services/teacherTodoT8Api.js')
  const installer = [
    read('src/services/mobilePerformanceInstaller.student.js'),
    read('src/services/mobilePerformanceInstaller.teacher.js')
  ].join('\n')

  assert.match(messages, /getMessagesPage/)
  assert.match(risks, /getRiskStudentsPage/)
  for (const source of [messages, risks]) {
    assert.match(source, /hasMore/)
    assert.match(source, /_loadEpoch/)
    assert.doesNotMatch(source, /pagedSlice/)
  }

  // T8 Todo 已迁移到 shared NetworkPager + server signed cursor；禁止为了兼容旧合同退回 getTodosPage。
  assert.match(todos, /createNetworkPager/)
  assert.match(todos, /teacherTodoT8Api\.list/)
  assert.match(todos, /pagerState\.hasMore/)
  assert.match(todos, /this\._pager\.loadMore\(\)/)
  assert.doesNotMatch(todos, /pagedSlice|getTodosPage/)
  assert.match(todoApi, /\/teacher-mobile\/todos\/grouped-continuous/)
  assert.match(todoApi, /cursor=/)
  assert.match(todoApi, /pageSize=/)

  for (const endpoint of [
    '/mobile/performance/student/messages-page',
    '/mobile/performance/teacher/risk-students-page'
  ]) assert.match(installer, new RegExp(endpoint.replaceAll('/', '\\/')))
})

test('mark-all-read collapses synchronous row updates into batched requests capped at the backend limit', () => {
  const installer = read('src/services/mobilePerformanceInstaller.student.js')
  assert.match(installer, /let queuedIds = new Set\(\)/)
  assert.match(installer, /Promise\.resolve\(\)\.then\(flushReadBatch\)/)
  assert.match(installer, /\/mobile\/performance\/student\/messages\/read-batch/)
  assert.match(installer, /data: \{ messageIds: chunk \}/)
  // 后端 read_messages_batch() 单批硬上限 100 条，前端排队去重后必须按同样上限切片，
  // 否则未读超过 100 条时一次性发送会被后端整批拒绝（2026-08-04 复审修复）。
  assert.match(installer, /READ_BATCH_LIMIT = 100/)
  assert.match(installer, /messageIds\.slice\(i, i \+ READ_BATCH_LIMIT\)/)
})

test('read state is only ever set locally for messages that can actually persist it', () => {
  // 「待办/服务进度」「学生动态/风险预警」的已读态由后端派生自真实业务记录，客户端标记
  // 无法持久化，刷新即回弹。因此每个页面的所有标已读入口（点开/去处理/全部已读）都必须
  // 统一走 _markRead()，由 _canPersistRead() 把关，不允许任何入口直接写 read = true。
  // （2026-08-04 复审二次收口：此前只有 markAllRead 做了过滤，open/handle 仍无条件置 true。）
  for (const page of [
    'src/pages/student/messages/index.vue',
    'src/pages/teacher/messages/index.vue'
  ]) {
    const source = read(page)
    assert.match(source, /_canPersistRead\(/, `${page} 必须定义可持久化判定`)
    assert.match(source, /_markRead\(/, `${page} 必须统一经 _markRead 标已读`)
    const assignments = source.match(/^\s*(message|m)\.read = true$/gm) || []
    assert.equal(assignments.length, 1,
      `${page} 只允许 _markRead() 内部一处写 read = true，实际 ${assignments.length} 处`)
    // 失败必须回滚乐观状态，否则界面显示已读但服务端仍未读
    assert.match(source, /_synced = false; (message|m)\.read = false/,
      `${page} 已读同步失败必须回滚 read`)
  }
})

test('release script never writes an empty appid and can resolve it from .env.production', () => {
  const release = read('scripts/finalize-mp-weixin-release.mjs')
  // 曾经的真实缺陷：未配置 WECHAT_APPID 时直接 projectConfig.appid = ''，
  // 空 appid 会让微信开发者工具导入即报错，比保留 touristappid 更糟。
  assert.doesNotMatch(release, /projectConfig\.appid = appid\s*$/m)
  assert.match(release, /appid \|\| String\(projectConfig\.appid \|\| ''\)\.trim\(\) \|\| TOURIST_APPID/)
  // 非技术使用者只改 .env.production 一个文件就能打出可上传的包
  assert.match(release, /VITE_WECHAT_APPID/)
  assert.match(release, /uploadReady/)
  // AppID 必须校验格式，避免把错值写进产物后到工具里才发现
  assert.match(release, /APPID_PATTERN = \/\^wx\[0-9a-fA-F\]\{16\}\$\//)
})

test('release build fails at the proactive 1.80 MiB split threshold', () => {
  const release = read('scripts/finalize-mp-weixin-release.mjs')
  // V3 S1.5：main.js 不再全局安装高频适配（那会把两端 API 与 mock 图重新提升进主包），
  // 改由各自分包页面显式安装；主包体积门禁本身不变。
  assert.doesNotMatch(read('src/main.js'), /mobilePerformanceInstaller/)
  assert.match(read('src/pages/student/messages/index.vue'), /ensureStudentPerformanceApi\(\)/)
  assert.match(read('src/pages/teacher/workbench/index.vue'), /ensureTeacherPerformanceApi\(\)/)
  assert.match(release, /MAIN_PACKAGE_SPLIT_TRIGGER/)
  assert.match(release, /1\.8 \* 1024 \* 1024/)
  assert.match(release, /达到 1\.80 MiB 主动分包线/)
})

test('teacher weekly review carries the CAS version from list to mutation', () => {
  const adapter = read('src/services/realApi.js')
  const api = read('src/services/teacherApi.js')
  const page = read('src/pages/teacher/internship-review/index.vue')
  assert.match(adapter, /expectedVersion: Number\(r\.version\)/)
  assert.match(adapter, /reportVersion/)
  assert.match(adapter, /data: \{ action, comment: comment \|\| '', expectedVersion \}/)
  assert.match(api, /reviewWeekly: \(id, action, comment, expectedVersion\)/)
  assert.match(page, /w\.expectedVersion/)
  assert.match(page, /reviewWeekly\([\s\S]*w\.expectedVersion\)/)
})
