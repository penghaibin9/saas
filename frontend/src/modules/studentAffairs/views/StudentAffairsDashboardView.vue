<template>
  <AppPageShell
    title="今日工作"
    subtitle="聚合当前身份范围内的待办、请假返校、风险、困难资助与处分事项，先看结论，再逐项处理。"
    :role-name="dashboard.viewLabel"
    :data-scope-name="scopeLabel"
    watermark-purpose="学工今日工作查看"
  >
    <template #actions>
      <span class="sa-updated-hint">
        数据更新于 <AppDateDisplay :value="dashboard.updatedAt" mode="datetime" empty-text="—" />
      </span>
      <AppPermissionButton
        :allowed="canBtn('studentAffairs.dashboard.view')"
        code="studentAffairs.dashboard.view"
        variant="secondary"
        @click="load"
      >
        刷新
      </AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="true" />
      <AppPermissionButton
        :allowed="!!allTodoPath"
        code="approval.todo.view"
        :show-lock="false"
        @click="go(allTodoPath)"
      >
        全部待办
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :title="stateTitle"
      :description="stateDescription"
      loading-text="正在加载学工今日工作真实数据…"
      @retry="load"
      @back="$router.push('/workbench')"
    >
      <div class="sa-today-workbench-v6">
        <section class="sa-summary-strip" aria-labelledby="sa-today-conclusion">
          <div class="sa-summary-strip__content">
            <span class="sa-summary-strip__eyebrow">TODAY · 当前运行结论</span>
            <h2 id="sa-today-conclusion" class="sa-summary-strip__title">{{ primaryConclusion }}</h2>
            <p class="sa-summary-strip__text">{{ conclusionDetail }}</p>
          </div>

          <div class="sa-dashboard-metrics" aria-label="今日工作关键指标">
            <button
              v-for="item in heroMetrics"
              :key="item.key"
              type="button"
              class="sa-hero-metric"
              :class="`is-${item.tone}`"
              :disabled="!item.path"
              :title="item.path ? `进入${item.label}` : '当前身份无此业务入口'"
              @click="go(item.path)"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small v-if="item.value !== '—'">{{ item.unit }}</small>
            </button>
          </div>
        </section>

        <nav class="sa-journey-strip" aria-label="今日工作闭环">
          <strong>今日工作闭环</strong>
          <ol>
            <li v-for="(step, index) in journeySteps" :key="step" :class="{ 'is-current': index === 1 }">
              <span>{{ index + 1 }}</span>
              <b>{{ step }}</b>
            </li>
          </ol>
        </nav>

        <div class="sa-dashboard-workspace">
          <div class="sa-grid sa-grid--priority">
            <div class="sa-priority-main">
              <AppSectionCard
                class="sa-priority-panel"
                title="现在先处理"
                subtitle="风险与逾期优先；每条队列进入对应业务工作页。"
                compact
                no-padding
              >
                <template #header-extra>
                  <span class="sa-priority-rule">风险 / 超期优先</span>
                </template>

                <ul class="sa-work-queue" aria-label="当前业务队列">
                  <li v-for="item in todoItems" :key="item.key">
                    <button
                      type="button"
                      class="sa-work-queue__row"
                      :class="[{ 'is-disabled': !item.path }, `is-${item.tone}`]"
                      :disabled="!item.path"
                      :aria-label="item.path ? `${item.label}，${item.value}${item.unit}，${item.action}` : `${item.label}，当前身份无业务入口`"
                      @click="go(item.path)"
                    >
                      <span class="sa-queue-icon" aria-hidden="true">{{ item.icon }}</span>
                      <span class="sa-queue-copy">
                        <span class="sa-queue-title">
                          <strong>{{ item.label }}</strong>
                          <AppStatusTag :type="item.statusType" :label="item.statusLabel" />
                        </span>
                        <span class="sa-queue-hint">{{ item.hint }}</span>
                        <span class="sa-queue-meta">按当前身份与数据范围汇总</span>
                      </span>
                      <span class="sa-queue-count">
                        <strong>{{ item.value }}</strong>
                        <small v-if="item.value !== '—'">{{ item.unit }}</small>
                      </span>
                      <span class="sa-queue-action">{{ item.path ? item.action : '无权限' }}</span>
                    </button>
                  </li>
                </ul>
              </AppSectionCard>
            </div>

            <aside class="sa-insight-stack" aria-label="今日工作辅助信息">
              <AppSectionCard class="sa-dashboard-panel sa-scope-panel" title="当前工作范围" compact>
                <div class="sa-scope-grid">
                  <div>
                    <span>当前身份</span>
                    <strong :title="dashboard.viewLabel || '当前角色'">{{ dashboard.viewLabel || '当前角色' }}</strong>
                  </div>
                  <div>
                    <span>数据范围</span>
                    <strong :title="scopeLabel">{{ scopeLabel }}</strong>
                  </div>
                </div>
                <p class="sa-fact-note"><span aria-hidden="true">✓</span> 页面只显示当前身份可查看、可进入的工作范围。</p>
              </AppSectionCard>

              <AppSectionCard class="sa-dashboard-panel sa-risk-panel" title="风险摘要" compact>
                <template #header-extra>
                  <AppRiskTag v-if="riskOpenCount > 0" :level="riskLevel" :label="`最高等级：${riskLevelLabel}`" />
                  <AppStatusTag v-else type="success" label="当前无未关闭风险" />
                </template>
                <div class="sa-risk-kpis">
                  <div>
                    <span>高风险</span>
                    <strong>{{ highRiskCount }}</strong>
                  </div>
                  <div>
                    <span>危急风险</span>
                    <strong>{{ criticalRiskCount }}</strong>
                  </div>
                  <div>
                    <span>未关闭风险</span>
                    <strong>{{ riskOpenCount }}</strong>
                  </div>
                </div>
                <p class="sa-fact-note">进入风险页后，按当前状态、责任人和可用动作继续处理。</p>
              </AppSectionCard>

              <AppSectionCard class="sa-dashboard-panel sa-entry-panel" title="高频入口" compact>
                <div class="sa-dashboard-services">
                  <button
                    v-for="entry in quickEntries"
                    :key="entry.key"
                    type="button"
                    class="sa-entry-button"
                    :disabled="!entry.path"
                    :title="entry.path ? entry.hint : '当前身份无此业务入口'"
                    @click="go(entry.path)"
                  >
                    <span aria-hidden="true">{{ entry.icon }}</span>
                    <b>{{ entry.label }}</b>
                    <small>{{ entry.hint }}</small>
                  </button>
                </div>
                <div class="sa-cross-center" aria-label="跨中心风险入口">
                  <span>跨中心风险</span>
                  <button
                    v-for="entry in crossCenterEntries"
                    :key="entry.key"
                    type="button"
                    :disabled="!entry.path"
                    @click="go(entry.path)"
                  >{{ entry.label }}</button>
                </div>
              </AppSectionCard>
            </aside>
          </div>

          <AppSectionCard
            class="sa-dashboard-panel sa-dashboard-panel--audit"
            title="最近处理与审计"
            subtitle="当前权限与数据范围内的真实操作留痕。"
            compact
          >
            <p v-if="auditError" class="sa-audit-warning" role="status">{{ auditError }}</p>
            <AppAuditTrail :records="auditLogs" compact empty-text="暂无可展示审计记录" />
          </AppSectionCard>
        </div>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppAuditTrail,
  AppDateDisplay,
  AppExportButton,
  AppGlobalState,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

/** 卡片 key → 权限码；无权限时不下钻（避免假入口）。 */
const CARD_PERM = {
  studentTotal: 'studentAffairs.student.view',
  classTotal: 'studentAffairs.class.view',
  pendingTodo: 'approval.todo.view',
  pendingLeave: 'studentAffairs.leave.view',
  overdueLeave: 'studentAffairs.leave.view',
  pendingAid: 'studentAffairs.aid.view',
  pendingFunding: 'studentAffairs.funding.view',
  pendingDiscipline: 'studentAffairs.discipline.view',
  riskStudents: 'studentAffairs.risk.view'
}

const FALLBACK_DRILL = {
  studentTotal: '/admin/student/list',
  classTotal: '/admin/campus-service/classes',
  pendingTodo: '/admin/approval/todos',
  pendingLeave: '/admin/student-affairs/leave',
  overdueLeave: '/admin/student-affairs/leave/ledger?status=OVERDUE',
  pendingAid: '/admin/student-affairs/aid?status=REVIEW',
  pendingFunding: '/admin/student-affairs/funding?status=REVIEW',
  pendingDiscipline: '/admin/student-affairs/discipline?status=REVIEW',
  riskStudents: '/admin/student-affairs/risk?status=OPEN'
}

const RISK_LABEL = {
  CRITICAL: '危急',
  HIGH: '高',
  MEDIUM: '中',
  LOW: '低'
}

const EMPTY_DASHBOARD = {
  summaryCards: [],
  moduleCards: [],
  view: '',
  viewLabel: '',
  scopeMode: '',
  scopeLabel: '',
  riskSummary: {}
}

export default {
  name: 'StudentAffairsDashboardView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppAuditTrail,
    AppDateDisplay,
    AppExportButton,
    AppGlobalState,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      errorMessage: '',
      dashboard: { ...EMPTY_DASHBOARD },
      auditLogs: [],
      auditError: ''
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      if (this.dashboard.scopeMode === 'NONE') return 'empty'
      return this.metricCards.length ? 'ready' : 'empty'
    },
    stateTitle() {
      if (this.dashboard.scopeMode === 'NONE') return '当前身份暂无学工数据范围'
      if (!this.loading && !this.errorMessage && !this.metricCards.length) return '暂无可用的学工聚合数据'
      return ''
    },
    stateDescription() {
      if (this.errorMessage) return this.errorMessage
      if (this.dashboard.scopeMode === 'NONE') {
        return '系统已按最小权限关闭业务数据。请联系学校管理员配置学工数据范围后重试。'
      }
      if (!this.loading && !this.metricCards.length) {
        return '当前暂未取得可用的学工汇总，请刷新后重试。系统不会把加载失败显示为 0。'
      }
      return ''
    },
    metricCards() {
      return (this.dashboard.summaryCards || []).map((card) => {
        const perm = CARD_PERM[card.key]
        const allowed = !perm || this.canBtn(perm)
        const drillPath = allowed
          ? (card.drillPath || FALLBACK_DRILL[card.key] || '')
          : ''
        return { ...card, drillPath }
      })
    },
    scopeLabel() {
      if (this.dashboard.scopeLabel) return this.dashboard.scopeLabel
      const map = {
        ADMIN_TENANT: '全校',
        SCOPED: '本人负责范围',
        NONE: '无数据范围',
        SELF: '本人负责范围'
      }
      return map[this.dashboard.scopeMode] || '按当前身份'
    },
    heroMetrics() {
      const card = (key) => this.metricCards.find((item) => item.key === key) || {}
      return [
        {
          key: 'pendingTodo', label: '统一待办', tone: 'primary',
          value: this.cardValue(card('pendingTodo')), unit: card('pendingTodo').unit || '件',
          path: card('pendingTodo').drillPath
        },
        {
          key: 'pendingLeave', label: '待审请假', tone: 'warning',
          value: this.cardValue(card('pendingLeave')), unit: card('pendingLeave').unit || '件',
          path: card('pendingLeave').drillPath
        },
        {
          key: 'overdueLeave', label: '逾期返校', tone: 'danger',
          value: this.cardValue(card('overdueLeave')), unit: card('overdueLeave').unit || '件',
          path: card('overdueLeave').drillPath
        },
        {
          key: 'riskStudents', label: '未关闭风险', tone: 'danger',
          value: this.cardValue(card('riskStudents')), unit: card('riskStudents').unit || '人',
          path: card('riskStudents').drillPath
        }
      ]
    },
    allTodoPath() {
      return this.heroMetrics.find((item) => item.key === 'pendingTodo')?.path || ''
    },
    journeySteps() {
      return ['查看今日全局', '处理当前待办', '核查重点风险', '谈话 / 家校', '回访并留痕']
    },
    todoItems() {
      const card = (key) => this.metricCards.find((item) => item.key === key) || {}
      const rows = [
        {
          key: 'riskStudents', icon: '险', label: '风险与重点学生', tone: 'danger',
          statusLabel: '未关闭', statusType: 'danger', action: '查看风险',
          hint: '查看未关闭风险学生，按当前状态与责任人继续处置。',
          value: this.cardValue(card('riskStudents')), unit: card('riskStudents').unit || '人',
          path: card('riskStudents').drillPath
        },
        {
          key: 'overdueLeave', icon: '返', label: '逾期未销假', tone: 'warning',
          statusLabel: '已逾期', statusType: 'danger', action: '查看逾期',
          hint: '核查应返校但尚未完成销假确认的请假记录。',
          value: this.cardValue(card('overdueLeave')), unit: card('overdueLeave').unit || '件',
          path: card('overdueLeave').drillPath
        },
        {
          key: 'pendingLeave', icon: '假', label: '请假待审批', tone: 'primary',
          statusLabel: '待审批', statusType: 'processing', action: '查看待审',
          hint: '按辅导员、学院与学工处当前审批节点进入连续处理。',
          value: this.cardValue(card('pendingLeave')), unit: card('pendingLeave').unit || '件',
          path: card('pendingLeave').drillPath
        },
        {
          key: 'pendingAid', icon: '困', label: '困难认定材料与审核', tone: 'warning',
          statusLabel: '待认定', statusType: 'warning', action: '查看认定',
          hint: '进入困难认定工作台核对材料、资格与当前审核节点。',
          value: this.cardValue(card('pendingAid')), unit: card('pendingAid').unit || '件',
          path: card('pendingAid').drillPath
        },
        {
          key: 'pendingFunding', icon: '奖', label: '奖助评审与公示', tone: 'success',
          statusLabel: '待评审', statusType: 'warning', action: '查看奖助',
          hint: '进入奖助工作台继续资格核对、评审与公示流程。',
          value: this.cardValue(card('pendingFunding')), unit: card('pendingFunding').unit || '件',
          path: card('pendingFunding').drillPath
        },
        {
          key: 'pendingDiscipline', icon: '纪', label: '处分审批与解除', tone: 'violet',
          statusLabel: '待处理', statusType: 'warning', action: '查看处分',
          hint: '进入处分工作台处理审批、生效或解除节点，并保留完整审计链路。',
          value: this.cardValue(card('pendingDiscipline')), unit: card('pendingDiscipline').unit || '件',
          path: card('pendingDiscipline').drillPath
        }
      ]
      return rows.map((item) => {
        const numeric = Number(item.value)
        if (item.value !== '—' && Number.isFinite(numeric) && numeric === 0) {
          return { ...item, statusLabel: '已清零', statusType: 'success' }
        }
        return item
      })
    },
    primaryConclusion() {
      const todo = this.metricNumber('pendingTodo')
      const overdue = this.metricNumber('overdueLeave')
      const risk = this.riskOpenCount
      if (!todo && !overdue && !risk) {
        return '当前范围的统一待办、逾期返校与未关闭风险均已清零。'
      }
      const lead = todo ? `当前有 ${todo} 项统一待办` : '当前统一待办已清零'
      const focus = []
      if (overdue) focus.push(`${overdue} 条逾期未销假`)
      if (risk) focus.push(`${risk} 名未关闭风险学生`)
      return focus.length ? `${lead}；先核查 ${focus.join('与')}。` : `${lead}。`
    },
    conclusionDetail() {
      const prefix = `${this.dashboard.viewLabel || '当前身份'} · ${this.scopeLabel}`
      const riskParts = []
      if (this.criticalRiskCount > 0) riskParts.push(`危急风险 ${this.criticalRiskCount} 人`)
      if (this.highRiskCount > 0) riskParts.push(`高风险 ${this.highRiskCount} 人`)
      const riskText = riskParts.length ? `${riskParts.join('、')}；` : ''
      return `${prefix}。${riskText}请假、困难、奖助和处分事项均可从下方队列继续处理。`
    },
    riskOpenCount() {
      const summary = this.dashboard.riskSummary || {}
      if (summary.openStudentCount != null) return Number(summary.openStudentCount) || 0
      return this.metricNumber('riskStudents')
    },
    highRiskCount() {
      return Number(this.dashboard.riskSummary?.highCount) || 0
    },
    criticalRiskCount() {
      return Number(this.dashboard.riskSummary?.criticalCount) || 0
    },
    riskLevel() {
      const card = this.metricCards.find((item) => item.key === 'riskStudents') || {}
      const fromCard = card.topRiskLevel
      const fromSummary = this.dashboard.riskSummary?.topRiskLevel || ''
      const level = String(fromCard || fromSummary || 'LOW').toUpperCase()
      return ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(level) ? level : 'LOW'
    },
    riskLevelLabel() {
      return RISK_LABEL[this.riskLevel] || '待确认'
    },
    quickEntries() {
      const student = this.metricCards.find((item) => item.key === 'studentTotal') || {}
      const orientationAllowed = this.canBtn('orientation.dashboard.view') || this.canBtn('studentAffairs.orientation.view')
      return [
        { key: 'student', icon: '生', label: '学生主档', hint: '唯一找学生入口', path: student.drillPath || '' },
        { key: 'orientation', icon: '新', label: '数字迎新', hint: '报到与异常工作区', path: orientationAllowed ? '/admin/orientation' : '' }
      ]
    },
    crossCenterEntries() {
      return [
        {
          key: 'internship', label: '岗位实习',
          path: this.canBtn('internship.risk.view') ? '/admin/internship/risks' : ''
        },
        {
          key: 'graduation', label: '毕业设计',
          path: this.canBtn('graduation.risk.view') ? '/admin/graduation/risk-archive?panel=risk' : ''
        }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    canBtn(code) {
      return canCode(this.ctx, code)
    },
    cardValue(card) {
      return card && card.value != null ? card.value : '—'
    },
    metricNumber(key) {
      const card = this.metricCards.find((item) => item.key === key)
      return Number(card?.value) || 0
    },
    async load() {
      this.loading = true
      this.errorMessage = ''
      this.auditError = ''
      try {
        const [dashboardRes, auditRes] = await Promise.all([
          studentAffairsApi.getDashboard(),
          studentAffairsApi.getAuditLogs({ page: 1, pageSize: 8 }).catch((e) => {
            this.auditError = e?.message || '最近处理与审计暂不可用'
            return { data: [] }
          })
        ])
        this.dashboard = dashboardRes.data || { ...EMPTY_DASHBOARD }
        this.auditLogs = auditRes.data || []
      } catch (e) {
        this.errorMessage = e?.message || '学工今日工作加载失败'
      } finally {
        this.loading = false
      }
    },
    go(path) {
      if (!path) return
      this.$router.push(path)
    },
    exportLedger() {
      return studentAffairsApi.exportProfileLedger({ purpose: '学工看板范围学生台账导出' })
    }
  }
}
</script>

<style scoped>
.sa-today-workbench-v6 {
  display: grid;
  gap: 10px;
  min-width: 0;
}

/* V6 当前结论带：覆盖旧 Screenshot C 的深色大 Hero，但不影响其他页面。 */
.sa-today-workbench-v6 .sa-summary-strip {
  position: relative !important;
  isolation: isolate;
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) auto !important;
  align-items: center !important;
  gap: 18px !important;
  min-height: 108px !important;
  margin: 0 !important;
  padding: 13px 16px !important;
  overflow: hidden !important;
  border: 1px solid color-mix(in srgb, var(--pri) 16%, var(--card-b)) !important;
  border-radius: 14px !important;
  background: linear-gradient(112deg, color-mix(in srgb, var(--pri-bg) 78%, var(--bg-card)), var(--bg-card) 72%) !important;
  color: var(--text-primary) !important;
  box-shadow: none !important;
}
.sa-today-workbench-v6 .sa-summary-strip::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: linear-gradient(90deg, var(--pri), color-mix(in srgb, var(--pri) 55%, transparent));
}
.sa-today-workbench-v6 .sa-summary-strip::after {
  display: none !important;
}
.sa-summary-strip__content { min-width: 0; }
.sa-today-workbench-v6 .sa-summary-strip__eyebrow {
  display: block;
  margin: 0 0 3px;
  color: var(--pri) !important;
  font-size: 12px !important;
  font-weight: 700;
  letter-spacing: 0.04em !important;
}
.sa-today-workbench-v6 .sa-summary-strip__title {
  max-width: none !important;
  margin: 0 !important;
  color: var(--text-primary) !important;
  font-size: 20px !important;
  font-weight: 700;
  line-height: 28px !important;
  letter-spacing: -0.015em !important;
}
.sa-today-workbench-v6 .sa-summary-strip__text {
  max-width: 820px !important;
  margin: 3px 0 0 !important;
  overflow: hidden;
  color: var(--text-secondary) !important;
  font-size: 12px !important;
  line-height: 18px !important;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-dashboard-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(76px, 1fr));
  min-width: 352px;
}
.sa-hero-metric {
  position: relative;
  display: grid;
  grid-template-columns: auto auto;
  grid-template-rows: auto auto;
  align-items: baseline;
  gap: 0 4px;
  min-width: 0;
  min-height: 64px;
  padding: 7px 12px;
  border: 0;
  border-left: 1px solid var(--border-light);
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
}
.sa-hero-metric:first-child { border-left: 0; }
.sa-hero-metric:not(:disabled):hover {
  border-radius: 9px;
  background: color-mix(in srgb, var(--pri-bg) 66%, transparent);
}
.sa-hero-metric:focus-visible {
  z-index: 1;
  outline: 2px solid var(--pri);
  outline-offset: -2px;
  border-radius: 9px;
}
.sa-hero-metric:disabled { cursor: not-allowed; opacity: 0.66; }
.sa-hero-metric > span {
  grid-column: 1 / -1;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-hero-metric strong {
  color: var(--text-primary);
  font-size: 25px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  line-height: 30px;
}
.sa-hero-metric small { color: var(--text-tertiary); font-size: 12px; }
.sa-hero-metric.is-danger strong { color: var(--danger-600); }
.sa-hero-metric.is-warning strong { color: var(--warning-700); }
.sa-hero-metric.is-primary strong { color: var(--pri); }

.sa-journey-strip {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  align-items: center;
  min-height: 36px;
  padding: 4px 7px;
  border: 1px solid var(--border-light);
  border-radius: 11px;
  background: var(--bg-card);
}
.sa-journey-strip > strong {
  padding-left: 5px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 20px;
}
.sa-journey-strip ol {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.sa-journey-strip li {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 0;
  min-height: 26px;
  color: var(--text-tertiary);
  font-size: 12px;
}
.sa-journey-strip li:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -4px;
  width: 8px;
  height: 1px;
  background: var(--border-base);
}
.sa-journey-strip li > span {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  flex: none;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-tertiary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
.sa-journey-strip li > b {
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-journey-strip li.is-current {
  color: var(--pri);
}
.sa-journey-strip li.is-current > span {
  border-color: var(--pri);
  background: var(--pri);
  color: var(--text-inverse);
}

.sa-dashboard-workspace {
  display: grid;
  gap: 10px;
  min-width: 0;
}
.sa-today-workbench-v6 .sa-grid--priority {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(292px, 0.35fr) !important;
  gap: 10px !important;
  min-width: 0;
  margin: 0 !important;
}
.sa-today-workbench-v6 .sa-grid--priority > * {
  min-height: 0 !important;
  overflow: visible !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.sa-priority-main,
.sa-insight-stack { min-width: 0; }
.sa-insight-stack {
  display: grid;
  align-content: start;
  gap: 10px;
}
.sa-priority-panel,
.sa-dashboard-panel {
  overflow: hidden;
  border-radius: 13px;
  box-shadow: none;
}
.sa-priority-panel :deep(.app-section-card__head),
.sa-dashboard-panel :deep(.app-section-card__head) {
  padding: 9px 11px;
}
.sa-priority-panel :deep(.app-section-card__title),
.sa-dashboard-panel :deep(.app-section-card__title) {
  font-size: 15px;
  line-height: 22px;
}
.sa-priority-panel :deep(.app-section-card__subtitle),
.sa-dashboard-panel :deep(.app-section-card__subtitle) {
  font-size: 12px;
  line-height: 18px;
}
.sa-dashboard-panel :deep(.app-section-card__body) { padding: 10px; }
.sa-priority-rule {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 9px;
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.sa-work-queue {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 8px;
  list-style: none;
}
.sa-work-queue > li {
  min-width: 0;
  list-style: none;
}
.sa-work-queue__row {
  display: grid;
  width: 100%;
  grid-template-columns: 38px minmax(0, 1fr) 58px 88px;
  align-items: center;
  gap: 9px;
  min-height: 62px;
  padding: 7px 9px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--bg-card);
  color: var(--text-primary);
  text-align: left;
  transition: border-color 150ms ease, background 150ms ease, transform 150ms ease;
}
.sa-work-queue__row:not(:disabled):hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--pri) 28%, var(--border-base));
  background: color-mix(in srgb, var(--pri-bg) 46%, var(--bg-card));
}
.sa-work-queue__row:focus-visible {
  outline: 2px solid var(--pri);
  outline-offset: 2px;
}
.sa-work-queue__row.is-danger { border-left: 3px solid var(--danger-500); }
.sa-work-queue__row.is-warning { border-left: 3px solid var(--warning-500); }
.sa-work-queue__row.is-primary { border-left: 3px solid var(--pri); }
.sa-work-queue__row.is-success { border-left: 3px solid var(--success-500); }
.sa-work-queue__row.is-violet { border-left: 3px solid var(--info-500); }
.sa-work-queue__row.is-disabled { cursor: not-allowed; opacity: 0.72; }
.sa-queue-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: 13px;
  font-weight: 800;
}
.is-danger .sa-queue-icon { background: var(--danger-50); color: var(--danger-600); }
.is-warning .sa-queue-icon { background: var(--warning-50); color: var(--warning-700); }
.is-success .sa-queue-icon { background: var(--success-50); color: var(--success-700); }
.is-violet .sa-queue-icon { background: var(--info-50); color: var(--info-700); }
.sa-queue-copy {
  display: grid;
  min-width: 0;
}
.sa-queue-title {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}
.sa-queue-title > strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-queue-hint {
  display: block;
  margin-top: 1px;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 17px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-queue-meta {
  display: block;
  margin-top: 1px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 16px;
}
.sa-queue-count {
  display: inline-flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 3px;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.sa-queue-count strong { font-size: 24px; line-height: 28px; }
.sa-queue-count small { color: var(--text-tertiary); font-size: 12px; }
.sa-queue-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--primary-100);
  border-radius: 8px;
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.sa-work-queue__row:not(:disabled) .sa-queue-action::after {
  content: '→';
  margin-left: 4px;
}
.sa-work-queue__row:disabled .sa-queue-action {
  border-color: var(--border-base);
  background: var(--bg-subtle);
  color: var(--text-tertiary);
}

.sa-scope-grid,
.sa-risk-kpis {
  display: grid;
  gap: 7px;
}
.sa-scope-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.sa-risk-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.sa-scope-grid > div,
.sa-risk-kpis > div {
  min-width: 0;
  padding: 8px 9px;
  border: 1px solid var(--border-light);
  border-radius: 9px;
  background: var(--bg-subtle);
}
.sa-scope-grid span,
.sa-risk-kpis span {
  display: block;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 17px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-scope-grid strong,
.sa-risk-kpis strong {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  color: var(--text-primary);
  font-size: 18px;
  font-variant-numeric: tabular-nums;
  line-height: 24px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-risk-kpis > div:nth-child(-n + 2) strong { color: var(--danger-600); }
.sa-fact-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 7px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 18px;
}
.sa-fact-note > span { color: var(--success-700); font-weight: 800; }

.sa-dashboard-services {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}
.sa-entry-button {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  grid-template-rows: auto auto;
  align-items: center;
  gap: 0 7px;
  min-width: 0;
  min-height: 54px;
  padding: 7px 8px;
  border: 1px solid var(--border-light);
  border-radius: 9px;
  background: var(--bg-card);
  color: var(--text-primary);
  text-align: left;
}
.sa-entry-button > span {
  grid-row: 1 / 3;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: 12px;
  font-weight: 800;
}
.sa-entry-button b {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-entry-button small {
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-entry-button:not(:disabled):hover {
  border-color: var(--primary-300);
  background: var(--primary-50);
}
.sa-entry-button:focus-visible { outline: 2px solid var(--pri); outline-offset: 2px; }
.sa-entry-button:disabled { cursor: not-allowed; opacity: 0.62; }
.sa-cross-center {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  min-width: 0;
  color: var(--text-tertiary);
  font-size: 12px;
}
.sa-cross-center > span { margin-right: auto; white-space: nowrap; }
.sa-cross-center button {
  min-height: 28px;
  padding: 0 8px;
  border: 1px solid var(--border-light);
  border-radius: 7px;
  background: var(--bg-card);
  color: var(--text-link);
  font-size: 12px;
}
.sa-cross-center button:not(:disabled):hover { border-color: var(--primary-300); background: var(--primary-50); }
.sa-cross-center button:disabled { color: var(--text-tertiary); cursor: not-allowed; opacity: 0.58; }

.sa-audit-warning {
  margin: 0 0 8px;
  padding: 8px 10px;
  border: 1px solid var(--warning-100);
  border-radius: 8px;
  background: var(--warning-50);
  color: var(--warning-700);
  font-size: 12px;
  line-height: 18px;
}
.sa-dashboard-panel--audit :deep(.app-section-card__body) {
  max-height: 220px;
  overflow-y: auto;
  scrollbar-gutter: stable;
}
.sa-updated-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

/* 仅压缩本页标题区；全局顶栏、搜索、主题、帮助、消息与用户区保持原样。 */
:global(.mps:has(.sa-today-workbench-v6) > .mps__head) {
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap;
}
:global(.mps:has(.sa-today-workbench-v6) > .mps__head .mps__title-wrap) {
  min-width: 0;
  flex: 1 1 auto;
}
:global(.mps:has(.sa-today-workbench-v6) > .mps__head .mps__subtitle) {
  max-width: 760px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
:global(.mps:has(.sa-today-workbench-v6) > .mps__head .mps__meta) {
  flex: 0 0 auto;
  flex-wrap: nowrap;
}

/* Dashboard 的 SLA 真值保持原组件和原接口，仅将其排到主工作区之后，避免说明区挤占首屏。 */
:global(.student-affairs-ui-scope:has(.sa-today-workbench-v6)) {
  display: flex;
  flex-direction: column;
}
:global(.student-affairs-ui-scope:has(.sa-today-workbench-v6) > .mps) { order: 1; }
:global(.student-affairs-ui-scope:has(.sa-today-workbench-v6) > .sa-context-stack) {
  order: 2;
  margin: 16px 0 0;
}

@media (max-width: 1280px) {
  .sa-updated-hint { display: none; }
  .sa-today-workbench-v6 .sa-summary-strip {
    grid-template-columns: minmax(0, 1fr) auto !important;
  }
  .sa-dashboard-metrics { min-width: 320px; }
  .sa-hero-metric { padding-inline: 8px; }
  .sa-today-workbench-v6 .sa-grid--priority {
    grid-template-columns: minmax(0, 1fr) minmax(270px, 0.34fr) !important;
  }
  .sa-queue-hint { max-width: 38vw; }
}
@media (max-width: 1120px) {
  :global(.mps:has(.sa-today-workbench-v6) > .mps__head) { flex-wrap: wrap; }
  :global(.mps:has(.sa-today-workbench-v6) > .mps__head .mps__meta) { flex-wrap: wrap; }
  .sa-today-workbench-v6 .sa-summary-strip {
    grid-template-columns: 1fr !important;
  }
  .sa-dashboard-metrics { width: 100%; min-width: 0; }
  .sa-today-workbench-v6 .sa-grid--priority { grid-template-columns: 1fr !important; }
  .sa-insight-stack { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .sa-queue-hint { max-width: none; }
}
@media (max-width: 860px) {
  .sa-journey-strip { grid-template-columns: 1fr; gap: 4px; }
  .sa-journey-strip > strong { display: none; }
  .sa-insight-stack { grid-template-columns: 1fr; }
  .sa-work-queue__row { grid-template-columns: 36px minmax(0, 1fr) auto; }
  .sa-queue-action { grid-column: 2 / -1; justify-self: end; }
}
@media (max-width: 640px) {
  .sa-today-workbench-v6 .sa-summary-strip__text { white-space: normal; }
  .sa-dashboard-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sa-hero-metric:nth-child(3) { border-left: 0; }
  .sa-journey-strip ol { grid-template-columns: 1fr; }
  .sa-journey-strip li { justify-content: flex-start; }
  .sa-journey-strip li::after { display: none; }
  .sa-work-queue__row { grid-template-columns: 34px minmax(0, 1fr) auto; }
  .sa-queue-title { align-items: flex-start; flex-direction: column; gap: 3px; }
  .sa-queue-hint { white-space: normal; }
  .sa-queue-meta { display: none; }
  .sa-queue-count strong { font-size: 20px; }
  .sa-scope-grid,
  .sa-risk-kpis,
  .sa-dashboard-services { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .sa-work-queue__row,
  .sa-hero-metric { transition: none; }
}
</style>
