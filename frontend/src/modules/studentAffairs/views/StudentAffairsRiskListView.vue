<template>
  <AppPageShell
    title="风险预警"
    subtitle="聚合学业、请假、宿舍、心理等来源的风险记录，PC 端负责分派、处置、升级和闭环入口。"
    role-name="学工角色"
    data-scope-name="学工数据范围"
    watermark-purpose="学工风险预警查看"
  >
    <template #actions>
      <AppPermissionButton
        v-if="canScanTimeout"
        :allowed="canScanTimeout"
        code="studentAffairs.risk.handle"
        variant="secondary"
        :loading="actioning"
        @click="scanTimeout"
      >
        扫描超时
      </AppPermissionButton>
      <AppPermissionButton :allowed="canBtn('studentAffairs.risk.create')" code="studentAffairs.risk.create" :loading="actioning" @click="createRisk">
        新建风险
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学工风险预警数据..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <TaskContextBar
        :role-name="roleName"
        :scope-name="scopeName"
        :pending="pendingCount"
        :overdue="stats && stats.overdue"
        :filter-summary="taskFilterSummary"
        next-hint="优先分派或处置超时、高危风险记录。"
        :degraded="!!errorMessage"
        @clear-filter="clearTaskFilters"
      />
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard v-if="isRulePanel" title="风险规则摘要">
        <div class="sa-rules">
          <div v-for="rule in ruleItems" :key="rule.title" class="sa-rule">
            <strong>{{ rule.title }}</strong>
            <span>{{ rule.desc }}</span>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard v-else title="风险学生与处置">
        <nav class="sa-queues" aria-label="风险快捷队列">
          <button
            v-for="q in quickQueues"
            :key="q.key"
            type="button"
            class="sa-queue"
            :class="[`is-${q.tone}`, { 'is-on': activeQueue === q.key, 'is-empty': q.count === 0 }]"
            :aria-pressed="activeQueue === q.key ? 'true' : 'false'"
            @click="selectQueue(q.key)"
          >
            <span class="sa-queue__dot" aria-hidden="true"></span>
            <span class="sa-queue__label">{{ q.label }}</span>
            <span v-if="q.count !== null" class="sa-queue__count">{{ q.count }}</span>
          </button>
        </nav>

        <div v-if="studentFilterLabel" class="sa-student-filter">
          <span>{{ studentFilterLabel }}</span>
          <button type="button" class="mp-link" @click="clearStudentFilter">清除筛选</button>
        </div>
        <div class="sa-toolbar">
          <AppSelect v-model="filters.source" class="sa-filter" :options="SOURCE_OPTIONS" placeholder="" @change="reload" />
          <AppSelect v-model="filters.riskLevel" class="sa-filter" :options="LEVEL_FILTER_OPTIONS" placeholder="" @change="reload" />
          <AppSelect v-model="filters.status" class="sa-filter" :options="STATUS_FILTER_OPTIONS" placeholder="" @change="onStatusSelect" />
          <span v-if="scanResult" class="sa-scan">{{ scanResult }}</span>
        </div>

        <DataTable
          v-if="risks.length || pagination.total > 0"
          :columns="riskColumns"
          :rows="risks"
          row-key="riskId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.realName || '未命名学生' }}</div>
            <div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div>
          </template>
          <template #cell-source="{ row }">{{ sourceLabel(row.source) }}</template>
          <template #cell-riskLevel="{ row }"><AppRiskTag :level="row.riskLevel" /></template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></template>
          <template #cell-owner="{ row }">{{ ownerLabel(row) }}</template>
          <template #cell-summary="{ row }">
            <div class="mp-cell-main">{{ row.title || '风险记录' }}</div>
            <div v-if="row.mentalMasked" class="mp-cell-sub">心理来源明细已按角色脱敏</div>
          </template>
          <template #cell-actions="{ row }">
            <div class="sa-actions" :aria-label="`${row.realName || '该学生'}的可用操作`">
              <!-- 推荐主动作：按状态机推出「这条现在最该做的一件事」，只是视觉层级，
                   动作本身仍来自 row.allowedActions，不比它更宽。 -->
              <div v-if="primaryAction(row)" class="sa-actions__recommended">
                <span class="sa-actions__hint">推荐下一步</span>
                <AppPermissionButton
                  class="sa-actions__primary"
                  :allowed="canBtn(primaryAction(row).code)"
                  :code="primaryAction(row).code"
                  size="sm"
                  variant="primary"
                  :loading="isRowActioning(row, primaryAction(row).key)"
                  :disabled="isOtherRowActioning(row, primaryAction(row).key)"
                  :native-title="`推荐下一步：${primaryAction(row).label}`"
                  @click="primaryAction(row).run(row)"
                >
                  <span>{{ primaryAction(row).label }}</span>
                  <span class="sa-actions__arrow" aria-hidden="true">→</span>
                </AppPermissionButton>
              </div>

              <!-- 我来处理：仅当服务端下发 canClaim（本人有处置资格且该行可 ASSIGN）。 -->
              <AppPermissionButton
                v-if="row.canClaim"
                class="sa-actions__claim"
                :allowed="canBtn('studentAffairs.risk.assign')"
                code="studentAffairs.risk.assign"
                size="sm"
                variant="secondary"
                :loading="isRowActioning(row, 'CLAIM')"
                :disabled="isOtherRowActioning(row, 'CLAIM')"
                native-title="跳过责任人选择，直接分派给我"
                @click="claim(row)"
              ><span class="sa-actions__claim-dot" aria-hidden="true"></span>我来处理</AppPermissionButton>

              <div class="sa-actions__secondary">
                <AppPermissionButton
                  v-for="a in secondaryActions(row)"
                  :key="a.key"
                  :allowed="canBtn(a.code)"
                  :code="a.code"
                  size="sm"
                  variant="secondary"
                  :loading="isRowActioning(row, a.key)"
                  :disabled="isOtherRowActioning(row, a.key)"
                  @click="a.run(row)"
                >{{ a.label }}</AppPermissionButton>

                <AppPermissionButton class="sa-actions__detail" :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" size="sm" variant="ghost" @click="$router.push(`/admin/student-affairs/risk/${row.riskId}`)">
                  查看详情
                </AppPermissionButton>
              </div>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前范围内暂无风险记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer :visible="createDlg.visible" title="新建风险记录" mode="modal" size="medium" @close="createDlg.visible = false">
      <div class="sa-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="createDlg.studentId"
                            placeholder="按姓名 / 学号搜索" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险等级" required>
          <AppSelect v-model="createDlg.riskLevel" :options="RISK_LEVELS" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险标题" required>
          <AppTextInput v-model="createDlg.title" placeholder="一句话概括，如：连续两周未到课" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险详情" required hint="写清时间、表现、已了解到的情况，供责任人接手">
          <AppTextarea v-model="createDlg.detail" :rows="4" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="createDlg.error" type="danger" :description="createDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="createDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitCreate">建单</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="assignDlg.visible" title="分派责任人" type="primary" confirm-text="确认分派"
      :submitting="actioning" @confirm="submitAssign"
    >
      <AppFormItem label="责任人" required>
        <AppRiskOwnerPicker v-model="assignDlg.ownerId"
                          placeholder="按姓名 / 工号搜索"
                          data-scope-hint="仅可选持学工风险处置角色的在职账号" />
      </AppFormItem>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="processDlg.visible" :title="processDialog.title" type="primary" :confirm-text="processDialog.confirmText"
      require-reason :reason-label="processDialog.reasonLabel" phrase-scene-key="sa.risk.handle"
      :submitting="actioning" @confirm="submitProcess"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppSelect,
  AppStatusTag,
  AppStudentPicker,
  AppRiskOwnerPicker,
  AppTextInput,
  AppTextarea
} from '@/components/common'
import TaskContextBar from '@/modules/studentAffairs/components/TaskContextBar.vue'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { resolveTodoStatus, readStudentFilter } from '@/modules/studentAffairs/utils/todoFilterSemantics'

const RISK_COLUMNS = [
  { key: 'student', title: '学生', width: '160px' },
  { key: 'source', title: '来源' },
  { key: 'riskLevel', title: '等级' },
  { key: 'status', title: '状态' },
  { key: 'owner', title: '责任人' },
  { key: 'summary', title: '摘要' },
  { key: 'actions', title: '操作', align: 'right', width: '270px' }
]

const RISK_LEVELS = [
  { value: 'LOW', label: '低风险' },
  { value: 'MEDIUM', label: '中风险' },
  { value: 'HIGH', label: '高风险' },
  { value: 'CRITICAL', label: '危急' }
]
const SOURCE_OPTIONS = [
  { value: '', label: '全部来源' },
  { value: 'ACADEMIC_WARNING', label: '学业预警' },
  { value: 'LEAVE_OVERDUE', label: '请假异常' },
  { value: 'DORM', label: '宿舍异常' },
  { value: 'MENTAL', label: '心理关注' }
]
const LEVEL_FILTER_OPTIONS = [
  { value: '', label: '全部等级' },
  { value: 'LOW', label: '低' },
  { value: 'MEDIUM', label: '中' },
  { value: 'HIGH', label: '高' },
  { value: 'CRITICAL', label: '重大' }
]
const STATUS_FILTER_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'PENDING', label: '待处置' },
  { value: 'OPEN', label: '未关闭' },
  { value: 'NEW', label: '新建' },
  { value: 'ASSIGNED', label: '已分派' },
  { value: 'PROCESSING', label: '处置中' },
  { value: 'FOLLOWING', label: '持续跟进' },
  { value: 'ESCALATED', label: '已升级' },
  { value: 'CLOSED', label: '已关闭' }
]

const SCAN_ROLES = new Set([
  'SCHOOL_ADMIN', 'SCHOOL_LEADER', 'STUDENT_AFFAIRS_ADMIN', 'SA_ADMIN', 'PLATFORM_SUPER_ADMIN'
])

export default {
  name: 'StudentAffairsRiskListView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton,
    AppConfirmDialog,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSelect,
    AppStudentPicker,
    AppRiskOwnerPicker,
    AppTextInput,
    AppTextarea,
    AppSectionCard,
    AppStatusTag,
    DataTable,
    TaskContextBar
  },
  data() {
    return {
      riskColumns: RISK_COLUMNS,
      RISK_LEVELS,
      SOURCE_OPTIONS,
      LEVEL_FILTER_OPTIONS,
      STATUS_FILTER_OPTIONS,
      loading: true,
      actioning: false,
      rowActioning: { riskId: '', action: '' },
      errorMessage: '',
      risks: [],
      total: 0,
      stats: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
      scanResult: '',
      createDlg: { visible: false, studentId: '', riskLevel: 'MEDIUM', title: '', detail: '', error: '' },
      assignDlg: { visible: false, riskId: '', ownerId: '', version: null },
      processDlg: { visible: false, riskId: '', version: null, action: 'PROCESS' },
      filters: {
        source: '',
        riskLevel: '',
        status: '',
        studentId: ''
      },
      studentFilter: { studentId: '', studentNo: '', studentName: '' },
      activeQueue: 'ALL',
      routeIntentConsumed: false
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '学工角色'
    },
    scopeName() {
      return (this.ctx && this.ctx.dataScope && (this.ctx.dataScope.scopeName || this.ctx.dataScope.name)) || '学工数据范围'
    },
    pendingCount() {
      return this.stats ? Number(this.stats.unassigned || 0) : null
    },
    taskFilterSummary() {
      if (this.studentFilterLabel) return this.studentFilterLabel
      const parts = []
      if (this.filters.source) parts.push(`来源：${this.filters.source}`)
      if (this.filters.riskLevel) parts.push(`等级：${this.filters.riskLevel}`)
      if (this.filters.status) parts.push(`状态：${this.filters.status}`)
      return parts.join('；')
    },
    isRulePanel() {
      return this.$route.name === 'student-affairs-risk-rules'
    },
    studentFilterLabel() {
      const f = this.studentFilter || {}
      if (!f.studentId && !f.studentNo) return ''
      let name = f.studentName || ''
      let no = f.studentNo || ''
      const id = f.studentId || ''
      if ((!name || !no) && id && this.risks && this.risks.length) {
        const hit = this.risks.find((x) => String(x.studentId) === String(id))
        if (hit) {
          if (!name) name = hit.realName || ''
          if (!no) no = hit.studentNo || ''
        }
      }
      if (name || no) return `当前学生筛选：${name || '学生'}${no ? ` / ${no}` : ''}`
      return `当前学生筛选：#${id}`
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    canScanTimeout() {
      const role = (this.ctx?.currentRoleCode || this.ctx?.currentRole?.roleCode || '').toUpperCase()
      return SCAN_ROLES.has(role) && this.canBtn('studentAffairs.risk.handle')
    },
    processDialog() {
      return ({
        PROCESS: { title: '记录本次处置', confirmText: '确认记录', reasonLabel: '处置内容（≥5字）' },
        FOLLOW: { title: '转为持续跟进', confirmText: '开始跟进', reasonLabel: '本次跟进安排（≥5字）' },
        TAKEOVER: { title: '接管升级风险', confirmText: '确认接管', reasonLabel: '接管说明（≥5字）' }
      })[this.processDlg.action] || { title: '记录风险动作', confirmText: '确认', reasonLabel: '办理说明（≥5字）' }
    },
    /**
     * 快捷队列。数字直接取服务端 stats——后端用同一份谓词算卡片和过滤，
     * 所以「点进去看到的条数」必然等于这里显示的数字（有合同用例锁住）。
     * 「我负责的」传 ownerId=me 由服务端认自己是谁：/rbac/current-context 不返回
     * userId，前端拿不到自己的数字 id，也不该把身份解析规则复制到浏览器里。
     */
    quickQueues() {
      const s = this.stats || {}
      const list = [
        { key: 'ALL', label: '全部', tone: 'neutral', count: Number(s.total ?? this.total) },
        { key: 'HIGH', label: '高危 / 危急', tone: 'risk', count: Number(s.highCritical || 0) },
        { key: 'OVERDUE', label: '已超时', tone: 'risk', count: Number(s.overdue || 0) },
        { key: 'UNASSIGNED', label: '待分派', tone: 'warning', count: Number(s.unassigned || 0) },
        { key: 'FOLLOWING', label: '持续跟进', tone: 'neutral', count: null }
      ]
      list.splice(4, 0, { key: 'MINE', label: '我负责的', tone: 'primary', count: null })
      return list
    },
    metricCards() {
      const s = this.stats || {}
      const high = Number(s.highCritical || 0)
      const open = Number(s.open || 0)
      const unassigned = Number(s.unassigned || 0)
      const overdue = Number(s.overdue || 0)
      return [
        { key: 'total', label: '风险记录', value: Number(s.total ?? this.total), accent: 'primary' },
        { key: 'high', label: '高危/危急', value: high, accent: high ? 'risk' : 'success' },
        { key: 'open', label: '未闭环', value: open, accent: open ? 'warning' : 'success' },
        { key: 'unassigned', label: '待分派', value: unassigned, accent: unassigned ? 'warning' : 'success' },
        { key: 'overdue', label: '超时', value: overdue, accent: overdue ? 'risk' : 'success' }
      ]
    },
    ruleItems() {
      return [
        { title: '来源去重', desc: '同一学生、同一来源、同一来源单据重复建单由后端拦截。' },
        { title: '心理明细脱敏', desc: '心理来源明细只对授权角色展示，普通辅导员只看到脱敏摘要。' },
        { title: '处置后关闭', desc: '风险关闭前必须存在处置记录，关闭后写入学生成长时间线。' },
        { title: '超时扫描', desc: '可由学工管理员手动触发自动分派与升级；接口幂等。' }
      ]
    }
  },
  watch: {
    '$route.fullPath'() {
      this.applyRouteFilters()
      this.load()
    }
  },
  mounted() {
    this.applyRouteFilters()
    this.load()
    this.consumeRouteIntent()
  },
  methods: {
    clearTaskFilters() {
      this.filters.source = ''
      this.filters.riskLevel = ''
      this.filters.status = ''
      this.clearStudentFilter()
      this.reload()
    },
    canBtn(code) { return canCode(this.ctx, code) },
    consumeRouteIntent() {
      if (this.routeIntentConsumed || this.$route.query?.intent !== 'create') return
      const sid = this.studentFilter?.studentId
      if (!sid || !this.canBtn('studentAffairs.risk.create')) return
      this.routeIntentConsumed = true
      this.createRisk()
    },
    /**
     * 行级动作以服务端下发的 allowedActions 为准（fail-closed）。
     * canBtn 只表示"这个角色有没有这类权限"，无法表达"这条记录当前状态下、
     * 以当前责任关系能不能做"——只看它会显示出后端必然拒绝的按钮。
     * 后端未下发时一律不显示，不得回落成全开。
     */
    canAction(row, action) {
      return Array.isArray(row && row.allowedActions) && row.allowedActions.includes(action)
    },
    isRowActioning(row, action) {
      return String(this.rowActioning.riskId) === String(row && row.riskId) && this.rowActioning.action === action
    },
    isOtherRowActioning(row, action) {
      return !!this.rowActioning.riskId && !this.isRowActioning(row, action)
    },
    /**
     * 行级动作目录。key 与后端 RISK_TRANSITIONS 的动作名一一对应，
     * 前端只负责「怎么排版」，不负责「能不能做」——能不能做只看 row.allowedActions。
     */
    actionCatalog() {
      return {
        ASSIGN: { key: 'ASSIGN', label: '分派', code: 'studentAffairs.risk.assign', run: (r) => this.assign(r) },
        PROCESS: { key: 'PROCESS', label: '记录处置', code: 'studentAffairs.risk.handle', run: (r) => this.process(r, 'PROCESS') },
        FOLLOW: { key: 'FOLLOW', label: '继续跟进', code: 'studentAffairs.risk.handle', run: (r) => this.process(r, 'FOLLOW') },
        TAKEOVER: { key: 'TAKEOVER', label: '上级接管', code: 'studentAffairs.risk.handle', run: (r) => this.process(r, 'TAKEOVER') }
      }
    },
    /**
     * 推荐主动作：NEW→分派、已分派→记录处置、处置中→继续跟进、已升级→上级接管。
     * 纯视觉层级，不新增状态机；候选动作必须同时出现在 row.allowedActions 里，
     * 否则不推荐（宁可没有主按钮，也不给一个后端会拒的按钮）。
     */
    primaryAction(row) {
      const catalog = this.actionCatalog()
      for (const key of ['ASSIGN', 'PROCESS', 'FOLLOW', 'TAKEOVER']) {
        if (this.canAction(row, key)) return catalog[key]
      }
      return null
    },
    /** 主动作之外仍可执行的动作，放次级区域，避免一行堆满按钮。 */
    secondaryActions(row) {
      const primary = this.primaryAction(row)
      const catalog = this.actionCatalog()
      return ['ASSIGN', 'PROCESS', 'FOLLOW', 'TAKEOVER']
        .filter((k) => this.canAction(row, k) && (!primary || primary.key !== k))
        .map((k) => catalog[k])
    },
    /**
     * 我来处理：复用既有 ASSIGN 命令，ownerId 传 me 由服务端解析成本人，
     * 服务端仍走 _validate_owner / 状态机 / 乐观锁 / 待办 / 通知 / 审计。
     */
    async claim(row) {
      await this.runRowAction(row, 'CLAIM', () => studentAffairsApi.assignRisk(row.riskId, 'me', row.version))
    },
    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      this.filters.studentId = this.studentFilter.studentId || ''
      this.filters.source = q.source ? String(q.source) : this.filters.source
      this.filters.riskLevel = q.riskLevel ? String(q.riskLevel) : this.filters.riskLevel
      if (q.status != null && q.status !== '') {
        const resolved = resolveTodoStatus('risk', q.status)
        // PENDING/OPEN/DONE/OVERDUE 等公共语义：下拉用 activeKey；后端 OPEN/PENDING 已识别
        this.filters.status = resolved.activeKey === 'CLOSED' ? 'CLOSED'
          : (resolved.activeKey === 'ESCALATED' ? 'ESCALATED'
            : (['PENDING', 'OPEN'].includes(resolved.activeKey) ? resolved.activeKey
              : (resolved.matchStatuses && resolved.matchStatuses.length === 1 ? resolved.matchStatuses[0] : String(q.status))))
      }
    },
    clearStudentFilter() {
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      this.filters.studentId = ''
      const q = { ...this.$route.query }
      delete q.studentId
      delete q.studentNo
      delete q.studentName
      this.$router.replace({ query: q }).catch(() => {})
    },
    onStatusSelect() {
      const q = { ...this.$route.query }
      if (!this.filters.status) delete q.status
      else q.status = this.filters.status
      this.$router.replace({ query: q }).catch(() => {})
      this.reload()
    },
    /** 切换快捷队列：条件变了必须回第一页，否则会停在新条件下不存在的页码。 */
    selectQueue(key) {
      this.activeQueue = this.activeQueue === key && key !== 'ALL' ? 'ALL' : key
      this.scanResult = ''
      this.pagination.page = 1
      this.load()
    },
    /** 队列 → 服务端只读过滤参数。全部交给后端做 SQL 条件，前端不做本地筛。 */
    queueParams() {
      switch (this.activeQueue) {
        case 'HIGH': return { priority: 'HIGH_CRITICAL' }
        case 'OVERDUE': return { overdueOnly: true }
        case 'UNASSIGNED': return { unassignedOnly: true }
        case 'MINE': return { ownerId: 'me' }
        case 'FOLLOWING': return { status: 'FOLLOWING' }
        default: return {}
      }
    },
    async load({ background = false } = {}) {
      if (!background) this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listRiskRecords({
          ...this.filters,
          ...this.queueParams(),
          page: this.pagination.page,
          pageSize: this.pagination.pageSize
        })
        this.risks = res.data.items || []
        this.total = res.data.total || 0
        this.pagination.total = this.total
        this.stats = res.data.stats || null
      } catch (e) {
        this.errorMessage = e.message || '风险数据加载失败'
      } finally {
        if (!background) this.loading = false
      }
    },
    reload() {
      this.scanResult = ''
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    ownerLabel(row) {
      if (!row.ownerId) return '待分派'
      if (row.ownerName) {
        return row.ownerLoginName
          ? `${row.ownerName} / ${row.ownerLoginName}`
          : row.ownerName
      }
      return '责任人账号异常'
    },
    createRisk() {
      const sid = this.studentFilter?.studentId
      this.createDlg = { visible: true, studentId: sid ? String(sid) : '', riskLevel: 'MEDIUM', title: '', detail: '', error: '' }
    },
    async submitCreate() {
      const d = this.createDlg
      if (!d.studentId) { d.error = '请选择学生'; return }
      if (!d.title.trim()) { d.error = '请填写风险标题'; return }
      if (d.detail.trim().length < 5) { d.error = '风险详情不少于 5 字'; return }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.createRiskRecord({
        studentId: d.studentId,
        source: 'MANUAL',
        sourceRefId: `manual-${Date.now()}`,
        riskLevel: d.riskLevel,
        title: d.title.trim(),
        detail: d.detail.trim()
      }))
      if (ok) d.visible = false
    },
    assign(risk) {
      this.assignDlg = {
        visible: true,
        riskId: risk.riskId,
        ownerId: risk.ownerId || '',
        version: risk.version
      }
    },
    async submitAssign() {
      const d = this.assignDlg
      if (!d.ownerId) { this.errorMessage = '请选择责任人'; return }
      const ok = await this.runAction(() => studentAffairsApi.assignRisk(d.riskId, d.ownerId, d.version))
      if (ok) d.visible = false
    },
    process(risk, action = 'PROCESS') {
      this.processDlg = { visible: true, riskId: risk.riskId, version: risk.version, action }
    },
    async submitProcess({ reason }) {
      const d = this.processDlg
      const request = {
        PROCESS: () => studentAffairsApi.processRisk(d.riskId, reason, d.version),
        FOLLOW: () => studentAffairsApi.followRisk(d.riskId, reason, d.version),
        TAKEOVER: () => studentAffairsApi.takeoverRisk(d.riskId, reason, d.version)
      }[d.action]
      const ok = await this.runAction(request)
      if (ok) this.processDlg.visible = false
    },
    async scanTimeout() {
      this.actioning = true
      try {
        const res = await studentAffairsApi.scanRiskTimeout()
        this.scanResult = `本次扫描自动分派 ${res.data.assigned || 0} 条，升级 ${res.data.escalated || 0} 条`
        await this.load()
      } catch (e) {
        this.errorMessage = e.message || '风险超时扫描失败'
      } finally {
        this.actioning = false
      }
    },
    async runAction(fn) {
      this.actioning = true
      this.errorMessage = ''
      try {
        await fn()
        await this.load()
        return true
      } catch (e) {
        if (e.bizCode === 'APPROVAL_VERSION_CONFLICT') {
          this.errorMessage = '该记录已被其他人处理，数据已刷新'
          await this.load()
          return false
        }
        this.errorMessage = e.message || '操作失败'
        return false
      } finally {
        this.actioning = false
      }
    },
    async runRowAction(row, action, fn) {
      if (this.rowActioning.riskId) return false
      this.rowActioning = { riskId: String(row.riskId), action }
      this.errorMessage = ''
      try {
        await fn()
        await this.load({ background: true })
        return true
      } catch (e) {
        if (e.bizCode === 'APPROVAL_VERSION_CONFLICT') {
          this.errorMessage = '该记录已被其他人处理，数据已刷新'
          await this.load({ background: true })
          return false
        }
        this.errorMessage = e.message || '操作失败'
        return false
      } finally {
        this.rowActioning = { riskId: '', action: '' }
      }
    },
    sourceLabel(source) {
      return ({
        ACADEMIC_WARNING: '学业预警',
        LEAVE_OVERDUE: '请假异常',
        DORM: '宿舍异常',
        MENTAL: '心理关注',
        MANUAL: '人工建单'
      })[source] || source || '未设置'
    },
    statusKind(status) {
      if (status === 'CLOSED') return 'success'
      if (status === 'ESCALATED') return 'danger'
      if (['PROCESSING', 'FOLLOWING'].includes(status)) return 'warning'
      return 'info'
    }
  }
}
</script>

<style scoped>
.sa-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

/* 快捷队列：一排可切换的胶囊，数字直接来自服务端 stats，
   点进去的列表条数与这里显示的一致（后端同一份谓词）。 */
.sa-queues {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-light, #eef0f4);
}
.sa-queue {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px 14px 7px 11px;
  border: 1px solid var(--border-light, #e5e8ee);
  border-radius: 999px;
  background: var(--bg-card, #fff);
  color: var(--text-secondary, #5a6473);
  font: inherit;
  font-size: var(--font-size-sm, 13px);
  line-height: 1.2;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease,
              color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}
.sa-queue:hover {
  border-color: var(--queue-accent, var(--primary-400, #93b4fd));
  color: var(--text-primary, #1f2937);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(17, 24, 39, 0.06);
}
.sa-queue:focus-visible {
  outline: 2px solid var(--queue-accent, var(--primary-600, #2563eb));
  outline-offset: 2px;
}
.sa-queue__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--queue-accent, var(--text-tertiary, #98a2b3));
  flex: none;
}
.sa-queue__label { white-space: nowrap; }
.sa-queue__count {
  min-width: 20px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--bg-subtle, #f2f4f7);
  color: var(--text-secondary, #5a6473);
  font-size: var(--font-size-xs, 12px);
  font-variant-numeric: tabular-nums;
  text-align: center;
}
/* 选中态：整枚胶囊染成该队列的语义色，一眼看出当前在看哪一队 */
.sa-queue.is-on {
  border-color: var(--queue-accent, var(--primary-600, #2563eb));
  background: var(--queue-soft, var(--primary-50, #eff6ff));
  color: var(--queue-strong, var(--primary-700, #1d4ed8));
  font-weight: var(--font-weight-medium, 500);
}
.sa-queue.is-on .sa-queue__count {
  background: var(--queue-accent, var(--primary-600, #2563eb));
  color: #fff;
}
/* 语义色：高危/超时=红，待分派=橙，我负责的=蓝，全部/跟进=中性 */
.sa-queue.is-risk {
  --queue-accent: var(--danger-600, #dc2626);
  --queue-soft: var(--danger-50, #fef2f2);
  --queue-strong: var(--danger-700, #b91c1c);
}
.sa-queue.is-warning {
  --queue-accent: var(--warning-600, #d97706);
  --queue-soft: var(--warning-50, #fffbeb);
  --queue-strong: var(--warning-700, #b45309);
}
.sa-queue.is-primary {
  --queue-accent: var(--primary-600, #2563eb);
  --queue-soft: var(--primary-50, #eff6ff);
  --queue-strong: var(--primary-700, #1d4ed8);
}
.sa-queue.is-neutral {
  --queue-accent: var(--text-tertiary, #98a2b3);
  --queue-soft: var(--bg-subtle, #f2f4f7);
  --queue-strong: var(--text-primary, #1f2937);
}
/* 数字为 0 的队列淡出：让老师一眼看出哪几队真的有事要做。
   仍可点击（点进去是"当前没有"的空态，比按钮直接消失更好理解）。 */
.sa-queue.is-empty:not(.is-on) {
  opacity: 0.55;
}
.sa-queue.is-empty:not(.is-on):hover {
  opacity: 1;
}
@media (max-width: 720px) {
  .sa-queues { gap: 6px; }
  .sa-queue { padding: 6px 10px 6px 8px; }
}
.sa-student-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--warning-50, #fffbeb);
  border: 1px solid var(--warning-200, #fde68a);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.sa-filter {
  width: 150px;
}
.sa-scan {
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-200);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
.sa-rule span {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 240px;
}
.sa-actions__recommended {
  position: relative;
  display: inline-flex;
  padding-top: 12px;
}
.sa-actions__hint {
  position: absolute;
  top: -2px;
  left: 9px;
  z-index: 1;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--primary-50, #eff6ff);
  color: var(--primary-700, #1d4ed8);
  font-size: 9px;
  font-weight: 700;
  line-height: 15px;
  letter-spacing: .08em;
  white-space: nowrap;
}
.sa-actions__primary :deep(.app-button) {
  min-width: 96px;
  padding-inline: 13px 11px;
  border-radius: 10px;
  box-shadow: 0 8px 18px -10px var(--glow, rgba(37, 99, 235, .65));
}
.sa-actions__arrow {
  margin-left: 2px;
  font-size: 15px;
  line-height: 1;
  transition: transform .16s ease;
}
.sa-actions__primary:hover .sa-actions__arrow {
  transform: translateX(2px);
}
.sa-actions__claim :deep(.app-button) {
  border-color: var(--primary-200, #bfdbfe);
  background: var(--primary-50, #eff6ff);
  color: var(--primary-700, #1d4ed8);
  font-weight: 600;
}
.sa-actions__claim :deep(.app-button:hover:not(:disabled)) {
  border-color: var(--primary-400, #60a5fa);
  background: #fff;
}
.sa-actions__claim-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-500, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .12);
}
.sa-actions__secondary {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 3px;
}
.sa-actions__secondary :deep(.app-button) {
  padding-inline: 9px;
}
.sa-actions__detail :deep(.app-button) {
  color: var(--text-tertiary, #8a94a3);
}
@media (max-width: 1080px) {
  .sa-actions {
    min-width: 210px;
  }
  .sa-actions__hint {
    position: static;
    align-self: center;
    margin-right: 4px;
  }
  .sa-actions__recommended {
    padding-top: 0;
    align-items: center;
  }
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
.sa-rules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.sa-rule {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-4);
}
@media (max-width: 960px) {
  .sa-grid--metrics,
  .sa-rules {
    grid-template-columns: 1fr;
  }
}
@import '@/styles/module-page.css';
</style>
