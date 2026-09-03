<template>
  <AppPageShell class="sa-v6-page-shell" title="今日工作" watermark-purpose="学工今日工作查看">
    <template #actions>
      <AppPermissionButton :allowed="canView && !loading" code="studentAffairs.dashboard.view" variant="secondary" @click="load">刷新</AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="pageState === 'ready'" />
      <button
        class="sa-v6-button"
        data-action="all-todo"
        type="button"
        :disabled="!cardPath('pendingTodo')"
        @click="go(cardPath('pendingTodo'))"
      >全部待办</button>
    </template>

    <!-- A new request must not retain the shared state component's previous ready content. -->
    <AppGlobalState
      :key="requestId"
      :state="pageState"
      :title="stateTitle"
      :description="stateDescription"
      loading-text="正在加载学工今日工作真实数据…"
      @retry="load"
      @back="$router.push('/workbench')"
    >
      <div v-if="pageState === 'ready'" class="sa-v6-dashboard">
        <section class="sa-v6-hero" aria-labelledby="sa-v6-hero-title">
          <div class="sa-v6-hero__summary">
            <div class="sa-v6-hero__copy">
              <h2 id="sa-v6-hero-title" :title="heroConclusion">{{ heroConclusion }}</h2>
              <p :title="heroGuidance">{{ heroGuidance }}</p>
            </div>
            <dl class="sa-v6-hero__metrics" aria-label="今日工作关键指标">
              <div v-for="item in heroMetrics" :key="item.key" :data-metric="item.key">
                <dt>{{ item.label }}</dt>
                <dd :title="formatCount(item.value)">{{ formatCount(item.value) }}</dd>
              </div>
            </dl>
          </div>
          <ol class="sa-v6-flow" aria-label="今日工作闭环">
            <li v-for="(step, index) in workflowSteps" :key="step" :class="{ 'is-active': index === 0 }">
              <span>{{ index + 1 }}</span>{{ step }}
            </li>
          </ol>
        </section>

        <div class="sa-v6-workspace">
          <AppSectionCard class="sa-v6-panel sa-v6-queue-card" title="现在先处理" compact no-padding>
            <template #header-extra>
              <span class="sa-v6-scope-note" :title="scopeLabel">{{ scopeLabel }}</span>
            </template>
            <ul class="sa-v6-queue" aria-label="当前业务队列">
              <li v-for="item in businessQueues" :key="item.key">
                <button
                  type="button"
                  class="sa-v6-queue-row"
                  :class="`is-${item.tone}`"
                  :data-queue="item.key"
                  :disabled="!item.path"
                  :title="item.path ? item.description : '当前身份无可用入口'"
                  @click="go(item.path)"
                >
                  <span class="sa-v6-queue-row__icon" aria-hidden="true">{{ item.icon }}</span>
                  <span class="sa-v6-queue-row__copy">
                    <span class="sa-v6-queue-row__title">
                      <strong>{{ item.label }}</strong>
                      <AppStatusTag :type="item.statusType" :label="item.statusLabel" />
                    </span>
                    <span class="sa-v6-queue-row__description" :title="item.description">{{ item.description }}</span>
                  </span>
                  <span class="sa-v6-queue-row__count">
                    <strong>{{ formatCount(item.count) }}</strong>
                    <small v-if="item.count !== null">{{ item.unit }}</small>
                  </span>
                  <span class="sa-v6-queue-row__action">
                    {{ item.path ? item.action : '无可用入口' }}<span v-if="item.path" aria-hidden="true"> →</span>
                  </span>
                </button>
              </li>
            </ul>
          </AppSectionCard>

          <aside class="sa-v6-side" aria-label="今日工作辅助信息">
            <AppSectionCard class="sa-v6-panel sa-v6-scope-card" title="当前工作范围" compact>
              <dl class="sa-v6-scope-grid">
                <div><dt>当前身份</dt><dd :title="dashboard.viewLabel">{{ dashboard.viewLabel || '当前身份' }}</dd></div>
                <div><dt>数据范围</dt><dd :title="scopeLabel">{{ scopeLabel }}</dd></div>
                <div><dt>范围学生</dt><dd>{{ formatCount(cardValue('studentTotal')) }}</dd></div>
                <div><dt>范围班级</dt><dd>{{ formatCount(cardValue('classTotal')) }}</dd></div>
              </dl>
              <p class="sa-v6-note">数据更新于 <AppDateDisplay :value="dashboard.updatedAt" mode="datetime" empty-text="未提供" /></p>
            </AppSectionCard>

            <AppSectionCard class="sa-v6-panel sa-v6-risk-card" title="风险摘要" compact>
              <template #header-extra>
                <AppRiskTag v-if="cardValue('riskStudents') > 0 && riskLevel" :level="riskLevel" />
                <AppStatusTag
                  v-else
                  :type="cardValue('riskStudents') === 0 ? 'success' : 'warning'"
                  :label="cardValue('riskStudents') === 0 ? '无未关闭风险' : '摘要待核实'"
                />
              </template>
              <dl class="sa-v6-risk-numbers">
                <div><dt>危急风险</dt><dd>{{ formatCount(criticalRiskCount) }}</dd></div>
                <div><dt>高风险</dt><dd>{{ formatCount(highRiskCount) }}</dd></div>
                <div><dt>未关闭风险</dt><dd>{{ formatCount(cardValue('riskStudents')) }}</dd></div>
              </dl>
              <p class="sa-v6-note">优先核查危急风险，再按责任人持续跟进。</p>
              <button
                class="sa-v6-button sa-v6-risk-link"
                data-action="risk-workbench"
                type="button"
                :disabled="!cardPath('riskStudents')"
                @click="go(cardPath('riskStudents'))"
              >进入风险工作台</button>
            </AppSectionCard>

            <AppSectionCard class="sa-v6-panel sa-v6-entry-card" title="高频入口" compact>
              <div class="sa-v6-entry-grid">
                <button
                  v-for="entry in highFrequencyEntries"
                  :key="entry.path"
                  type="button"
                  class="sa-v6-entry"
                  :title="entry.hint"
                  @click="go(entry.path)"
                >
                  <strong>{{ entry.label }}</strong><small>{{ entry.hint }}</small>
                </button>
              </div>
              <p v-if="!highFrequencyEntries.length" class="sa-v6-note">当前身份暂无可用入口。</p>
            </AppSectionCard>
          </aside>
        </div>

        <p v-if="hasMissingMetrics" class="sa-v6-inline-warning" role="status">部分汇总暂未取得，已用“—”标明；请刷新或进入对应工作页核查。</p>
        <div class="sa-v6-support-grid">
          <AppSectionCard class="sa-v6-panel sa-dashboard-panel--audit" title="最近处理与审计" compact>
            <p v-if="auditLoading" class="sa-v6-note" role="status">正在读取操作记录…</p>
            <p v-else-if="auditUnavailable" class="sa-v6-inline-warning" role="status">操作记录暂不可用，请稍后刷新。当前工作汇总仍可查看。</p>
            <AppAuditTrail v-else :records="auditLogs" compact empty-text="暂无可展示审计记录" />
          </AppSectionCard>
          <AppSectionCard class="sa-v6-panel" title="跨中心协同" compact>
            <div class="sa-v6-bridge-actions">
              <button
                v-for="entry in crossCenterEntries"
                :key="entry.path"
                class="sa-v6-button"
                type="button"
                @click="go(entry.path)"
              >{{ entry.label }}</button>
            </div>
            <p v-if="!crossCenterEntries.length" class="sa-v6-note">当前身份暂无跨中心入口。</p>
          </AppSectionCard>
        </div>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppAuditTrail, AppDateDisplay, AppExportButton, AppGlobalState, AppPageShell, AppPermissionButton, AppRiskTag, AppSectionCard, AppStatusTag } from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const CARD_PERM = {
  studentTotal: 'studentAffairs.student.view', classTotal: 'studentAffairs.class.view',
  pendingTodo: 'approval.todo.view', pendingLeave: 'studentAffairs.leave.view',
  overdueLeave: 'studentAffairs.leave.view', pendingAid: 'studentAffairs.aid.view',
  pendingFunding: 'studentAffairs.funding.view', pendingDiscipline: 'studentAffairs.discipline.view',
  riskStudents: 'studentAffairs.risk.view'
}
const FALLBACK_DRILL = {
  studentTotal: '/admin/student/list', classTotal: '/admin/campus-service/classes',
  pendingTodo: '/admin/approval/todos', pendingLeave: '/admin/student-affairs/leave',
  overdueLeave: '/admin/student-affairs/leave/ledger?status=OVERDUE',
  pendingAid: '/admin/student-affairs/aid?status=REVIEW', pendingFunding: '/admin/student-affairs/funding?status=REVIEW',
  pendingDiscipline: '/admin/student-affairs/discipline?status=REVIEW', riskStudents: '/admin/student-affairs/risk?status=OPEN'
}
const FORMATTER = new Intl.NumberFormat('zh-CN')
const emptyDashboard = () => ({ summaryCards: [], moduleCards: [], riskSummary: {}, view: '', viewLabel: '', scopeMode: '', scopeType: '', scopeLabel: '' })
const objectValue = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)

export default {
  name: 'StudentAffairsDashboardView',
  props: { ctx: { type: Object, default: null } },
  components: { AppAuditTrail, AppDateDisplay, AppExportButton, AppGlobalState, AppPageShell, AppPermissionButton, AppRiskTag, AppSectionCard, AppStatusTag },
  data() {
    return {
      loading: true,
      errorMessage: '',
      errorKind: 'error',
      dashboard: emptyDashboard(),
      auditLogs: [],
      auditLoading: false,
      auditUnavailable: false,
      requestId: 0,
      loadedContext: '',
      workflowSteps: ['发现事项', '确认优先级', '进入业务办理', '返回今日队列', '审计沉淀']
    }
  },
  computed: {
    contextKey() {
      const ctx = this.ctx || {}
      return JSON.stringify([ctx.ctxKey, ctx.tenantId, ctx.userId, ctx.currentRole, ctx.dataScope, ctx.permissionPatterns, ctx.rbacOk])
    },
    canView() { return this.canBtn('studentAffairs.dashboard.view') },
    hasNoScope() {
      return this.dashboard.scopeMode === 'NONE' || this.dashboard.scopeType === 'NONE' || this.dashboard.scopeLabel === '无数据范围'
    },
    pageState() {
      if (!this.canView) return 'forbidden'
      if (this.loading || this.loadedContext !== this.contextKey) return 'loading'
      if (this.errorMessage) return this.errorKind
      if (this.hasNoScope) return 'empty'
      return this.dashboard.summaryCards.length ? 'ready' : 'empty'
    },
    stateTitle() {
      if (this.pageState === 'forbidden') return '当前身份无权查看学工今日工作'
      if (this.pageState === 'error') return '学工今日工作加载失败'
      if (this.hasNoScope) return '当前账号未配置学工数据范围'
      return this.pageState === 'empty' ? '当前范围暂无可展示的学工汇总' : ''
    },
    stateDescription() {
      if (this.errorMessage) return this.errorMessage
      if (this.pageState === 'forbidden') return '请切换到已授权身份，或联系学校管理员。'
      if (this.hasNoScope) return '请联系学校管理员配置负责学院、班级或学生范围。'
      return '请刷新后重试，或返回工作台。'
    },
    scopeLabel() {
      return this.dashboard.scopeLabel || ({ ADMIN_TENANT: '全校', SCOPED: '本人负责范围', SELF: '本人负责范围', NONE: '无数据范围' })[this.dashboard.scopeMode] || '按当前身份'
    },
    metricCards() {
      return this.dashboard.summaryCards.map((card) => {
        const allowed = card.key === 'studentTotal'
          ? this.canBtn('student.profile.view') || this.canBtn(CARD_PERM.studentTotal)
          : !!CARD_PERM[card.key] && this.canBtn(CARD_PERM[card.key])
        const path = card.drillPath == null || card.drillPath === '' ? FALLBACK_DRILL[card.key] : card.drillPath
        return { ...card, drillPath: allowed && this.pageState === 'ready' ? this.safeDrill(path, FALLBACK_DRILL[card.key]) : '' }
      })
    },
    cardMap() {
      const result = Object.create(null)
      for (const card of this.metricCards) result[card.key] = card
      return result
    },
    heroMetrics() {
      return [['pendingTodo', '统一待办'], ['pendingLeave', '待审请假'], ['overdueLeave', '逾期未销假'], ['riskStudents', '未关闭风险']]
        .map(([key, label]) => ({ key, label, value: this.cardValue(key) }))
    },
    highRiskCount() { return this.toCount(this.dashboard.riskSummary?.highCount) },
    criticalRiskCount() { return this.toCount(this.dashboard.riskSummary?.criticalCount) },
    hasMissingMetrics() {
      return Object.keys(CARD_PERM).some((key) => this.cardValue(key) === null) || this.highRiskCount === null || this.criticalRiskCount === null
    },
    heroConclusion() {
      if (this.criticalRiskCount > 0) return `优先核查 ${this.formatCount(this.criticalRiskCount)} 名危急风险学生。`
      if (this.highRiskCount > 0) return `当前有 ${this.formatCount(this.highRiskCount)} 名高风险学生，请优先跟进。`
      if (this.cardValue('overdueLeave') > 0) return `先核查 ${this.formatCount(this.cardValue('overdueLeave'))} 条逾期未销假。`
      if (this.cardValue('riskStudents') > 0) return `当前有 ${this.formatCount(this.cardValue('riskStudents'))} 名未关闭风险学生。`
      if (this.hasMissingMetrics) return '部分汇总暂未取得，请核查对应工作队列。'
      if (this.cardValue('pendingTodo') > 0) return `当前有 ${this.formatCount(this.cardValue('pendingTodo'))} 项统一待办。`
      return '当前未见高危与逾期事项，请继续检查各项待审队列。'
    },
    heroGuidance() {
      return ({ COUNSELOR: '关注本人负责学生，处理后回到队列继续跟进。', COLLEGE_SA: '核查本院待办与风险，按责任分工继续处理。', SA_ADMIN: '查看全校业务积压，个案进入对应工作页办理。' })[this.dashboard.view] || '按当前身份负责范围，逐项查看与办理。'
    },
    businessQueues() {
      const card = (key) => this.cardMap[key] || {}
      const rows = [
        { key: 'riskStudents', label: '风险与重点学生', icon: '险', action: '查看风险', description: '查看未关闭风险，按等级和责任人继续跟进。', tone: 'danger', unit: '人', path: card('riskStudents').drillPath },
        { key: 'overdueLeave', label: '逾期未销假', icon: '返', action: '查看逾期', description: '核查返校事实，再进入销假与后续处理。', tone: 'warning', path: card('overdueLeave').drillPath },
        { key: 'pendingTodo', label: '统一待办', icon: '办', action: '查看待办', description: '查看当前身份需要处理的统一待办。', tone: 'primary', path: card('pendingTodo').drillPath },
        { key: 'pendingLeave', label: '请假待审批', icon: '假', action: '查看待审', description: '查看当前审批节点，核对请假时间与原因。', tone: 'primary', path: card('pendingLeave').drillPath },
        { key: 'pendingAid', label: '困难认定待处理', icon: '困', action: '查看认定', description: '核对申请材料、认定资格与审核意见。', tone: 'warning', path: card('pendingAid').drillPath },
        { key: 'pendingFunding', label: '奖助申请待评审', icon: '助', action: '查看评审', description: '核对项目条件、申请资格与评审节点。', tone: 'warning', path: card('pendingFunding').drillPath },
        { key: 'pendingDiscipline', label: '处分事项待处理', icon: '纪', action: '查看处分', description: '查看处分审批与解除申请，保留办理记录。', tone: 'neutral', path: card('pendingDiscipline').drillPath }
      ]
      return rows.map((row) => {
        const count = this.cardValue(row.key)
        return {
          ...row,
          count,
          unit: card(row.key).unit || row.unit || '件',
          tone: count === null ? 'neutral' : count === 0 ? 'success' : row.tone,
          statusType: count === null ? 'warning' : count === 0 ? 'success' : row.tone === 'danger' ? 'danger' : 'info',
          statusLabel: count === null ? '汇总未取得' : count === 0 ? '当前无事项' : row.key === 'overdueLeave' ? '已逾期' : '待查看'
        }
      })
    },
    riskLevel() {
      const level = this.dashboard.riskSummary?.topRiskLevel || this.cardMap.riskStudents?.topRiskLevel
      return ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(level) ? level : ''
    },
    highFrequencyEntries() {
      if (this.pageState !== 'ready') return []
      return [
        { label: '学生主档', hint: '找学生、看完整背景', path: '/admin/student/list', allowed: this.canBtn('student.profile.view') || this.canBtn('studentAffairs.student.view') },
        { label: '数字迎新', hint: '报到与异常核查', path: '/admin/orientation', allowed: this.canBtn('studentAffairs.orientation.view') },
        { label: '宿舍异常', hint: '住宿情况与异常处理', path: '/admin/student-affairs/dorm/exception', allowed: this.canBtn('studentAffairs.dorm.view') }
      ].filter((entry) => entry.allowed)
    },
    crossCenterEntries() {
      if (this.pageState !== 'ready') return []
      return [
        { label: '数字迎新', path: '/admin/orientation', code: 'studentAffairs.orientation.view' },
        { label: '岗位实习风险', path: '/admin/internship/risks', code: 'internship.risk.view' },
        { label: '毕业设计风险', path: '/admin/graduation/risk-archive?panel=risk', code: 'graduation.risk.view' }
      ].filter((entry) => this.canBtn(entry.code))
    }
  },
  watch: { contextKey: { flush: 'sync', handler() { this.load() } } },
  created() { this.load() },
  beforeUnmount() { this.requestId += 1 },
  methods: {
    canBtn(code) {
      return this.ctx?.rbacOk !== false && Array.isArray(this.ctx?.permissionPatterns) && canCode(this.ctx, code)
    },
    toCount(value) {
      if (typeof value !== 'number' && (typeof value !== 'string' || !/^\d+$/.test(value))) return null
      const count = Number(value)
      return Number.isSafeInteger(count) && count >= 0 ? count : null
    },
    formatCount(value) {
      const count = this.toCount(value)
      return count === null ? '—' : FORMATTER.format(count)
    },
    cardValue(key) { return this.toCount(this.cardMap[key]?.value) },
    cardPath(key) { return this.cardMap[key]?.drillPath || '' },
    safeDrill(path, fallback) {
      if (typeof path !== 'string' || !fallback || !path.startsWith('/') || path.startsWith('//') || /[\\\s]/.test(path)) return ''
      // Preserve the server query verbatim, but only for this metric's existing destination.
      return path.split(/[?#]/)[0] === fallback.split('?')[0] ? path : ''
    },
    isCurrent(id, key) { return id === this.requestId && key === this.contextKey },
    async loadAudit(id, key) {
      try {
        const result = await studentAffairsApi.getAuditLogs()
        if (!this.isCurrent(id, key)) return
        if (!result || result.code !== 0 || !Array.isArray(result.data)) throw new Error('操作记录格式异常')
        this.auditLogs = result.data
      } catch {
        if (this.isCurrent(id, key)) {
          this.auditLogs = []
          this.auditUnavailable = true
        }
      } finally {
        if (this.isCurrent(id, key)) this.auditLoading = false
      }
    },
    async load() {
      const id = ++this.requestId
      const key = this.contextKey
      this.loading = true
      this.loadedContext = key
      this.errorMessage = ''
      this.errorKind = 'error'
      this.dashboard = emptyDashboard()
      this.auditLogs = []
      this.auditUnavailable = false
      this.auditLoading = false
      if (!this.canView) {
        this.loading = false
        return
      }
      try {
        const result = await studentAffairsApi.getDashboard()
        if (!this.isCurrent(id, key)) return
        if (!result || result.code !== 0 || !objectValue(result.data) || !Array.isArray(result.data.summaryCards) ||
          result.data.summaryCards.some((card) => !objectValue(card) || typeof card.key !== 'string')) {
          throw new Error('未取得有效的学工汇总，请重试。')
        }
        this.dashboard = { ...emptyDashboard(), ...result.data }
        if (!this.hasNoScope) {
          this.auditLoading = true
          this.loadAudit(id, key)
        }
      } catch (error) {
        if (!this.isCurrent(id, key)) return
        this.dashboard = emptyDashboard()
        this.errorMessage = error?.message || '学工今日工作加载失败'
        const code = Number(error?.code)
        this.errorKind = code === 403 || Math.floor(code / 1000) === 403 ? 'forbidden' : 'error'
      } finally {
        if (this.isCurrent(id, key)) this.loading = false
      }
    },
    go(path) {
      if (!path || this.pageState !== 'ready') return
      const entries = [
        ...this.metricCards.map((card) => ({ path: card.drillPath })),
        ...this.highFrequencyEntries,
        ...this.crossCenterEntries
      ]
      if (entries.some((entry) => entry.path === path)) this.$router.push(path)
    },
    exportLedger() {
      if (this.pageState !== 'ready') return Promise.reject(new Error('请等待当前身份的数据加载完成。'))
      return studentAffairsApi.exportProfileLedger({ purpose: '学工看板范围学生台账导出' })
    }
  }
}
</script>

<style scoped>
.sa-v6-page-shell {
  gap: var(--space-1);
  min-width: 0;
}
.sa-v6-page-shell :deep(.mps__head) {
  min-height: 36px;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--space-2);
}
.sa-v6-page-shell :deep(.mps__title-wrap) { min-width: 0; }
.sa-v6-page-shell :deep(.mps__title) {
  font-size: var(--font-size-xl);
  line-height: 1.35;
}
.sa-v6-page-shell :deep(.mps__meta) {
  min-width: 0;
  flex: none;
  gap: var(--space-1);
}
.sa-v6-page-shell :deep(.mps__actions) { gap: var(--space-1); }
.sa-v6-dashboard {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
}
.sa-v6-hero {
  display: grid;
  gap: 2px;
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border-base);
  border-top: 3px solid var(--pri);
  border-radius: var(--radius-lg);
  background: linear-gradient(110deg, var(--pri-bg), var(--bg-card) 72%);
}
.sa-v6-hero__summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  min-height: 38px;
}
.sa-v6-hero__copy {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}
.sa-v6-hero h2 {
  margin: 0;
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-lg);
  line-height: 24px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-hero p {
  margin: 0;
  min-width: 0;
  max-width: 430px;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-hero__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(72px, 84px));
  margin: 0;
}
.sa-v6-hero__metrics > div {
  min-width: 0;
  padding: 0 var(--space-2);
  border-left: 1px solid var(--border-light);
}
.sa-v6-hero__metrics dt {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-hero__metrics dd {
  margin: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-flow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-1);
  min-height: 20px;
  margin: 0;
  padding: 2px 0 0;
  border-top: 1px solid var(--border-light);
  list-style: none;
}
.sa-v6-flow li {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 18px;
  white-space: nowrap;
}
.sa-v6-flow li > span {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex: none;
  border-radius: var(--radius-full);
  color: var(--pri);
  background: var(--pri-bg);
}
.sa-v6-flow .is-active > span {
  color: var(--text-inverse);
  background: var(--pri);
}
.sa-v6-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 296px;
  align-items: start;
  gap: var(--space-2);
  min-width: 0;
}
.sa-v6-panel {
  min-width: 0;
  overflow: hidden;
  border-radius: var(--radius-lg);
}
.sa-v6-panel :deep(.app-section-card__head) {
  min-height: 36px !important;
  align-items: center !important;
  padding: var(--space-1) var(--space-3) !important;
}
.sa-v6-panel :deep(.app-section-card__head-main),
.sa-v6-panel :deep(.app-section-card__head-extra) {
  align-items: center !important;
}
.sa-v6-panel :deep(.app-section-card__title) {
  font-size: var(--font-size-md);
  line-height: 22px;
}
.sa-v6-panel :deep(.app-section-card__body) { padding: var(--space-2); }
.sa-v6-queue-card :deep(.app-section-card__body) {
  padding: var(--space-1) var(--space-2) var(--space-2) !important;
}
.sa-v6-scope-note {
  max-width: 180px;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-queue {
  display: grid;
  gap: var(--space-1);
  padding: 0;
  margin: 0;
  list-style: none;
}
.sa-v6-queue li { min-width: 0; }
.sa-v6-queue-row {
  --row-tone: var(--pri);
  --row-soft: var(--pri-bg);
  width: 100%;
  min-height: 60px;
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto 94px;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-base);
  border-left: 3px solid var(--row-tone);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  color: var(--text-primary);
  text-align: left;
}
.sa-v6-queue-row.is-danger { --row-tone: var(--danger-600); --row-soft: var(--danger-50); }
.sa-v6-queue-row.is-warning { --row-tone: var(--warning-700); --row-soft: var(--warning-50); }
.sa-v6-queue-row.is-success { --row-tone: var(--success-700); --row-soft: var(--success-50); }
.sa-v6-queue-row.is-neutral { --row-tone: var(--text-secondary); --row-soft: var(--bg-section); }
.sa-v6-queue-row:not(:disabled):hover {
  border-color: var(--row-tone);
  background: var(--row-soft);
}
.sa-v6-queue-row:disabled { cursor: not-allowed; }
.sa-v6-queue-row__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  color: var(--row-tone);
  background: var(--row-soft);
  font-weight: 600;
}
.sa-v6-queue-row__copy { min-width: 0; }
.sa-v6-queue-row__title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-2);
}
.sa-v6-queue-row__title strong { font-size: var(--font-size-sm); }
.sa-v6-queue-row__description {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-queue-row__count {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
  font-variant-numeric: tabular-nums;
}
.sa-v6-queue-row__count strong {
  font-size: var(--font-size-xl);
  font-weight: 600;
}
.sa-v6-queue-row__count small {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}
.sa-v6-queue-row__action {
  min-height: 36px;
  display: grid;
  grid-auto-flow: column;
  align-items: center;
  justify-content: center;
  color: var(--row-tone);
  background: var(--row-soft);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
}
.sa-v6-side {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}
.sa-v6-scope-grid,
.sa-v6-risk-numbers {
  display: grid;
  gap: var(--space-2);
  margin: 0;
}
.sa-v6-scope-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.sa-v6-risk-numbers { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.sa-v6-scope-grid > div,
.sa-v6-risk-numbers > div {
  min-width: 0;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-section);
}
.sa-v6-scope-grid dt,
.sa-v6-risk-numbers dt {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}
.sa-v6-scope-grid dd,
.sa-v6-risk-numbers dd {
  margin: var(--space-1) 0 0;
  overflow-wrap: anywhere;
  color: var(--text-primary);
  font-weight: 600;
}
.sa-v6-risk-numbers dd {
  font-size: var(--font-size-xl);
  font-variant-numeric: tabular-nums;
}
.sa-v6-note {
  margin: var(--space-2) 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
.sa-v6-button {
  min-height: 36px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--pri-bg);
  color: var(--pri);
  font: inherit;
  white-space: nowrap;
}
.sa-v6-button:disabled {
  cursor: not-allowed;
  color: var(--text-secondary);
  background: var(--bg-section);
}
.sa-v6-risk-link {
  width: 100%;
  margin-top: var(--space-2);
}
.sa-v6-entry-grid {
  display: grid;
  gap: var(--space-2);
}
.sa-v6-entry {
  min-height: 40px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-section);
  color: var(--text-primary);
  text-align: left;
}
.sa-v6-entry strong,
.sa-v6-entry small { font-size: var(--font-size-xs); }
.sa-v6-entry small { color: var(--text-secondary); }
.sa-v6-support-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 296px;
  gap: var(--space-2);
}
.sa-dashboard-panel--audit :deep(.app-section-card__body) {
  max-height: 240px;
  overflow: auto;
}
.sa-v6-bridge-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-v6-inline-warning {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--warning-50);
  color: var(--warning-700);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
}
.sa-v6-page-shell button:focus-visible {
  outline: 2px solid var(--pri);
  outline-offset: 2px;
}
/* The SLA is read-only. Preserve its DOM, fetch and error states, and keep Risk/Leave unchanged. */
:global(.student-affairs-ui-scope:has(> .sa-v6-page-shell)) {
  display: flex;
  flex-direction: column;
}
:global(.student-affairs-ui-scope > .sa-v6-page-shell) { order: 1; }
:global(.student-affairs-ui-scope:has(> .sa-v6-page-shell) > .sa-context-stack) {
  order: 2;
  margin: var(--space-4) 0 0;
}
@media (max-width: 1180px) {
  .sa-v6-workspace,
  .sa-v6-support-grid { grid-template-columns: 1fr; }
  .sa-v6-side { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sa-v6-hero__summary {
    grid-template-columns: 1fr;
    gap: var(--space-1);
  }
  .sa-v6-hero__copy { display: grid; gap: 0; }
  .sa-v6-hero__metrics { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
  .sa-v6-page-shell :deep(.mps__head) { flex-wrap: wrap; }
  .sa-v6-side { grid-template-columns: 1fr; }
  .sa-v6-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sa-v6-queue-row { grid-template-columns: 36px minmax(0, 1fr) auto; }
  .sa-v6-queue-row__action {
    grid-column: 2 / -1;
    justify-self: end;
    padding-inline: var(--space-2);
  }
  .sa-v6-hero h2,
  .sa-v6-hero p,
  .sa-v6-queue-row__description { white-space: normal; }
}
</style>
