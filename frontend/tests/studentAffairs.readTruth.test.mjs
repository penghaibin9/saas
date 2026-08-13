/**
 * V5 学工读侧真实性前端合同。
 *
 * 锁住的不是"页面长什么样"，而是四类会让页面结果与数据库不一致的写法：
 *   1. 有搜索框但只搜当前页（后端没参数 / 前端本地过滤）；
 *   2. 固定 page=1&pageSize=N，超出部分永远翻不到；
 *   3. 概览数字与列表 total 不同口径；
 *   4. 行级按钮只看全局权限，不看后端下发的 allowedActions。
 *
 * 以及一类上下文缺口：列表消费了 studentId，动作表单却把它清空。
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

const LEAVE_APPROVAL = 'frontend/src/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue'
const MATERIAL_OPS = 'frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue'
const RISK_LIST = 'frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue'
const DORM_TRANSFER = 'frontend/src/modules/studentAffairs/views/dorm/DormTransferView.vue'

test('C1 leave approval searches on the server instead of filtering the current page', () => {
  const source = read(LEAVE_APPROVAL)
  // 关键词必须发给后端
  assert.match(source, /leaveApi\.pending\(\{[\s\S]*keyword:/)
  // 不得再按姓名/学号做本地过滤
  assert.doesNotMatch(source, /filteredRows/)
  assert.doesNotMatch(source, /rows\.filter\([\s\S]{0,120}studentName/)
  // 不得固定拉一大页冒充全量
  assert.doesNotMatch(source, /pageSize:\s*100/)
})

test('C1 leave approval paginates the pending queue from the server', () => {
  const source = read(LEAVE_APPROVAL)
  assert.match(source, /pagination:\s*\{\s*page:\s*1/)
  assert.match(source, /leaveApi\.pending\(\{[\s\S]*page:\s*this\.pagination\.page/)
  assert.match(source, /AppPagination/)
  // 搜索/清除筛选必须回到第一页
  assert.match(source, /reload\(\)\s*\{\s*this\.pagination\.page = 1/)
})

test('C4 material centre uses real server pagination, not a fixed first page', () => {
  const source = read(MATERIAL_OPS)
  assert.doesNotMatch(source, /page:\s*1,\s*pageSize:\s*100/)
  assert.match(source, /listCenter\(\{[\s\S]*page:\s*this\.pagination\.page/)
  assert.match(source, /AppPagination/)
  // 筛选条件变化必须回第一页，否则会停在新条件下不存在的页码
  assert.match(source, /applyFilters\(\)\s*\{\s*this\.pagination\.page = 1/)
  assert.match(source, /@change="applyFilters"/)
})

test('C5 risk list rows gate actions on server allowedActions, not global permissions', () => {
  const source = read(RISK_LIST)
  // 行级动作一律经 canAction 判定，而 canAction 只认服务端下发的 allowedActions
  assert.match(source, /row\.allowedActions\.includes\(action\)/)
  assert.match(source, /this\.canAction\(row, key\)/)
  // fail-closed：后端没下发就不显示，不得回落成全开
  assert.match(source, /Array\.isArray\(row && row\.allowedActions\)/)
  // 行级按钮不得只看全局权限：canBtn 只用于粗粒度 allowed，不得单独决定是否渲染
  assert.doesNotMatch(source, /v-if="canBtn\('studentAffairs\.risk\.(assign|handle)'\)"/)
  // Vue 不得**定义**一份后端状态机（注释里提及后端注册表是允许且有益的）
  assert.doesNotMatch(source, /RISK_TRANSITIONS\s*=/)
})

test('C7 all four ends read material business context instead of raw ids', () => {
  const surfaces = [
    ['frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue', /studentLine\(row\)/],
    ['student-portal/src/views/affairs/MaterialSupplementView.vue', /bizLine\(item\)/],
    ['miniapp/src/pages/teacher/affairs/index.vue', /materialStudentLine\(item\)/],
    ['miniapp/src/pages/student/affairs/index.vue', /bizLine\(item\)/]
  ]
  for (const [path, marker] of surfaces) {
    const source = read(path)
    assert.match(source, marker, `${path} 未消费 businessContext`)
    assert.match(source, /businessContext/, `${path} 未读取 businessContext`)
    // 后端没下发时必须退回原有可读文案，不能留空
    assert.match(source, /bizLabel\(/, `${path} 缺少 businessContext 缺失时的回退`)
  }
  // 主业务文案不得再直接把 bizId / studentId 当标题
  const teacherMini = read('miniapp/src/pages/teacher/affairs/index.vue')
  assert.doesNotMatch(teacherMini, /\{\{ bizLabel\(item\.bizType\) \}\} #\{\{ item\.bizId \}\} · 学生 #\{\{ item\.studentId \}\}/)
  const studentPortal = read('student-portal/src/views/affairs/MaterialSupplementView.vue')
  assert.doesNotMatch(studentPortal, /业务记录 #\{\{ item\.bizId \}\}/)
})

test('C8 material registration takes business context instead of hand-typed ids', () => {
  const view = read('frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue')
  // 深链带 bizType+bizId 时由服务端解析业务与学生，表单不再要求手抄主键
  assert.match(view, /applyRouteBizContext/)
  assert.match(view, /resolveBizContext/)
  assert.match(view, /v-if="!bizContext"/, '有业务上下文时应隐藏手填业务记录 ID')
  // 材料项编码提供本校已用过的建议，而不是让老师猜
  assert.match(view, /listItemSuggestions/)
  assert.match(view, /material-item-codes/)
  // 仍保留手工指定的退路，且技术 ID 仍可追踪
  assert.match(view, /clearBizContext/)

  const api = read('frontend/src/modules/studentAffairs/api/operations.api.js')
  assert.match(api, /material-center\/biz-context/)
  assert.match(api, /material-center\/item-suggestions/)

  // 业务详情侧提供正式入口，自动携带 bizType/bizId
  const aid = read('frontend/src/modules/studentAffairs/views/AidWorkbenchView.vue')
  assert.match(aid, /requireMaterial\(\)/)
  assert.match(aid, /bizType: 'AID'/)
  assert.match(aid, /material-operations/)
})

test('U2 risk quick queues filter on the server, not the current page', () => {
  const view = read('frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue')
  assert.match(view, /quickQueues/)
  assert.match(view, /queueParams\(\)/)
  assert.match(view, /priority: 'HIGH_CRITICAL'/)
  assert.match(view, /overdueOnly: true/)
  assert.match(view, /unassignedOnly: true/)
  // 切队列必须回第一页，否则会停在新条件下不存在的页码
  assert.match(view, /selectQueue\(key\)\s*\{[\s\S]{0,200}this\.pagination\.page = 1/)
  // 「我负责的」由服务端解析身份，前端不自己拼用户 id
  assert.match(view, /ownerId: 'me'/)

  // 适配器必须真的把这些参数发出去——白名单式解构漏掉会让按钮点了没反应
  const api = read('frontend/src/modules/studentAffairs/api/studentAffairs.api.js')
  assert.match(api, /params\.priority = priority/)
  assert.match(api, /params\.overdueOnly = true/)
  assert.match(api, /params\.unassignedOnly = true/)
  assert.match(api, /params\.ownerId = ownerId/)
})

test('U3/U4 risk row actions recommend a primary action and never widen allowedActions', () => {
  const view = read('frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue')
  // 推荐主动作按状态机顺序取，且候选必须在 allowedActions 里
  assert.match(view, /primaryAction\(row\)/)
  assert.match(view, /\['ASSIGN', 'PROCESS', 'FOLLOW', 'TAKEOVER'\]/)
  assert.match(view, /if \(this\.canAction\(row, key\)\) return catalog\[key\]/)
  assert.match(view, /secondaryActions\(row\)/)
  // 我来处理只看服务端下发的 canClaim，且复用 ASSIGN 命令传 me
  assert.match(view, /v-if="row\.canClaim"/)
  assert.match(view, /assignRisk\(row\.riskId, 'me', row\.version\)/)
  assert.match(view, /class="sa-actions__recommended"/)
  assert.match(view, /推荐下一步/)
  assert.match(view, /native-title="跳过责任人选择，直接分派给我"/)
  // 推荐 FOLLOW / TAKEOVER 必须接到各自写链，不能都误走 PROCESS
  assert.match(view, /FOLLOW:[\s\S]{0,160}this\.process\(r, 'FOLLOW'\)/)
  assert.match(view, /TAKEOVER:[\s\S]{0,160}this\.process\(r, 'TAKEOVER'\)/)
  assert.match(view, /FOLLOW:\s*\(\)\s*=>\s*studentAffairsApi\.followRisk/)
  assert.match(view, /TAKEOVER:\s*\(\)\s*=>\s*studentAffairsApi\.takeoverRisk/)
  // 行级快捷操作只给当前行反馈，不能让整张表的按钮一起转圈
  assert.match(view, /runRowAction\(row, 'CLAIM'/)
  assert.match(view, /rowActioning:\s*\{\s*riskId:\s*'',\s*action:\s*''\s*\}/)
  assert.match(view, /this\.load\(\{ background: true \}\)/)
  // 绝不能把 TAKEOVER 当成 self-assign 的实现
  assert.doesNotMatch(view, /claim[\s\S]{0,120}TAKEOVER/)
  // Vue 仍不得**定义**一份后端状态机（注释里引用后端注册表名是允许的）
  assert.doesNotMatch(view, /RISK_TRANSITIONS\s*=/)
  assert.doesNotMatch(view, /from:\s*\[?['"]NEW['"]/, 'Vue 不得复制状态迁移的 from 集合')
})

test('C6 dorm transfer keeps the student carried in from the profile page', () => {
  const source = read(DORM_TRANSFER)
  // 打开"发起调宿"时必须沿用当前学生筛选，而不是清空
  assert.match(source, /openTransfer\(\)\s*\{[\s\S]*studentFilter[\s\S]*studentId/)
  assert.doesNotMatch(source, /openTransfer\(\)\s*\{\s*this\.dlg = \{\s*visible:\s*true,\s*studentId:\s*''/)
  // 老师要能看见带进来的是谁，并且仍可换人
  assert.match(source, /prefilledStudentHint/)
  assert.match(source, /AppStudentPicker v-model="dlg\.studentId"/)
})
