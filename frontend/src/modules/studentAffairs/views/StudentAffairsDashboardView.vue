<template>
  <AppPageShell
    title="学工看板"
    subtitle="聚合今日待办、学生风险、请假审批和跨系统入口，数据按当前身份范围返回。"
    :role-name="dashboard.viewLabel"
    :data-scope-name="scopeLabel"
    watermark-purpose="学工看板查看"
  >
    <template #actions>
      <span class="sa-updated-hint">
        数据更新于 <AppDateDisplay :value="dashboard.updatedAt" mode="datetime" empty-text="—" />
      </span>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dashboard.view')" code="studentAffairs.dashboard.view" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="true" />
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学工看板真实数据…"
      @retry="load"
      @back="$router.push('/workbench')"
    >
      <div class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前工作范围 · {{ scopeLabel }}</span>
          <h3 class="sa-summary-strip__title">先处理待办和未关闭风险，再进入各业务台账</h3>
          <p class="sa-summary-strip__text">{{ riskSummary }} 今日待办、请假审批和重点学生提醒均按当前身份的数据范围汇总。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" variant="secondary" @click="go('/admin/student-affairs/risk?status=OPEN')">
            查看未关闭风险
          </AppPermissionButton>
        </div>
      </div>

      <div class="sa-grid sa-grid--priority">
        <AppSectionCard title="今日优先处理">
          <ul class="sa-list">
            <li v-for="item in todoItems" :key="item.key" :class="{ 'is-actionable': item.path }" @click="go(item.path)">
              <span>
                <strong>{{ item.label }}</strong>
                <small>{{ item.hint }}</small>
              </span>
              <span class="sa-list__action"><AppStatusTag :type="item.count > 0 ? 'warning' : 'success'" :label="`${item.count} 件`" /><button v-if="item.path" type="button" :aria-label="`打开${item.label}`">去处理 <b>→</b></button></span>
            </li>
          </ul>
        </AppSectionCard>

        <AppSectionCard title="学生风险结论">
          <div class="sa-risk-row">
            <AppRiskTag :level="riskLevel" />
            <span>{{ riskSummary }}</span>
          </div>
          <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" variant="secondary" @click="go('/admin/student-affairs/risk?status=OPEN')">
            进入风险预警
          </AppPermissionButton>
        </AppSectionCard>
      </div>

      <div class="sa-dashboard-section-head">
        <div>
          <h2>核心业务指标</h2>
          <p>点击有权限的指标卡，可直接进入对应业务台账。</p>
        </div>
      </div>

      <div class="sa-dashboard-metrics" aria-label="学工核心业务指标">
        <AppMetricCard
          v-for="card in metricCards"
          :key="card.key"
          :title="card.label"
          :value="card.value"
          :unit="card.unit"
          :accent="metricAccent(card.key)"
          :drillable="!!card.drillPath"
          :drill-target="card.drillPath"
          @drill="go"
        />
      </div>

      <div class="sa-dashboard-workspace">
        <div class="sa-dashboard-services">
          <AppSectionCard class="sa-dashboard-panel" title="常用学工业务" subtitle="高频工作直接进入对应台账">
            <div class="sa-dashboard-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.leave.view')" code="studentAffairs.leave.view" variant="secondary" @click="go('/admin/student-affairs/leave')">
                请假审批
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.view')" code="studentAffairs.dorm.view" variant="secondary" @click="go('/admin/student-affairs/dorm/exception')">
                宿舍异常
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" variant="secondary" @click="go('/admin/student-affairs/risk?status=OPEN')">
                风险预警
              </AppPermissionButton>
            </div>
          </AppSectionCard>

          <AppSectionCard class="sa-dashboard-panel" title="数字迎新" subtitle="新生报到与异常情况汇总">
            <div class="sa-dashboard-bridge">
              <p>查看迎新批次、报到进度和异常学生，快速进入迎新工作区。</p>
              <AppPermissionButton :allowed="canBtn('orientation.dashboard.view') || canBtn('studentAffairs.orientation.view')" code="studentAffairs.orientation.view" variant="secondary" @click="go('/admin/orientation')">
                打开数字迎新
              </AppPermissionButton>
            </div>
          </AppSectionCard>

          <AppSectionCard class="sa-dashboard-panel" title="跨中心风险" subtitle="集中查看其他中心的学生风险">
            <div class="sa-dashboard-actions">
              <AppPermissionButton :allowed="canBtn('internship.risk.view')" code="internship.risk.view" variant="secondary" @click="go('/admin/internship/risks')">
                岗位实习风险
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('graduation.risk.view')" code="graduation.risk.view" variant="secondary" @click="go('/admin/graduation/risk-archive?panel=risk')">
                毕业设计风险
              </AppPermissionButton>
            </div>
          </AppSectionCard>
        </div>

        <AppSectionCard class="sa-dashboard-panel sa-dashboard-panel--audit" title="最近操作记录" subtitle="当前权限范围内的真实操作留痕">
          <AppAuditTrail :records="auditLogs" compact empty-text="暂无可展示审计记录" />
        </AppSectionCard>
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
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

/** 卡片 key → 权限码；无权限时不下钻（避免假入口） */
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

export default {
  name: 'StudentAffairsDashboardView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppAuditTrail,
    AppDateDisplay,
    AppExportButton,
    AppGlobalState,
    AppMetricCard,
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
      dashboard: { summaryCards: [], moduleCards: [], viewLabel: '', scopeMode: '', scopeLabel: '' },
      auditLogs: []
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return this.metricCards.length ? 'ready' : 'empty'
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
    todoItems() {
      const card = (key) => this.metricCards.find((c) => c.key === key) || {}
      // 宿舍异常无与学工首页同口径可信统计：不展示假宿舍卡，也不用逾期销假顶替
      return [
        { key: 'todo', label: '今日待办', count: card('pendingTodo').value || 0, hint: '按当前身份可见的统一待办', path: card('pendingTodo').drillPath },
        { key: 'leave', label: '请假审批概览', count: card('pendingLeave').value || 0, hint: '待辅导员/学院/学工处处理', path: card('pendingLeave').drillPath },
        { key: 'focus', label: '重点学生提醒', count: card('riskStudents').value || 0, hint: '来自风险预警未关闭学生', path: card('riskStudents').drillPath }
      ]
    },
    riskLevel() {
      const card = this.metricCards.find((c) => c.key === 'riskStudents') || {}
      const fromCard = card.topRiskLevel
      const fromSummary = (this.dashboard && this.dashboard.riskSummary && this.dashboard.riskSummary.topRiskLevel) || ''
      const level = String(fromCard || fromSummary || 'NONE').toUpperCase()
      if (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(level)) return level
      return 'LOW'
    },
    riskSummary() {
      const rs = (this.dashboard && this.dashboard.riskSummary) || {}
      const card = this.metricCards.find((c) => c.key === 'riskStudents') || {}
      const count = Number(rs.openStudentCount != null ? rs.openStudentCount : (card.value || 0))
      const top = rs.topRiskLevel || card.topRiskLevel || ''
      if (!count) return '当前范围暂无未关闭风险。'
      const label = ({ CRITICAL: '危急', HIGH: '高', MEDIUM: '中', LOW: '低' })[top] || top
      return `当前范围内有 ${count} 名学生存在未关闭风险${label ? `（最高等级：${label}）` : ''}。`
    }
  },
  created() {
    this.load()
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const [dashboardRes, auditRes] = await Promise.all([
          studentAffairsApi.getDashboard(),
          studentAffairsApi.getAuditLogs().catch(() => ({ data: [] }))
        ])
        this.dashboard = dashboardRes.data
        this.auditLogs = auditRes.data || []
      } catch (e) {
        this.errorMessage = e?.message || '学工看板加载失败'
      } finally {
        this.loading = false
      }
    },
    metricAccent(key) {
      if (['riskStudents', 'overdueLeave'].includes(key)) return 'risk'
      if (['pendingTodo', 'pendingLeave', 'pendingAid', 'pendingFunding', 'pendingDiscipline'].includes(key)) return 'warning'
      return 'primary'
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
.sa-grid {
  display: grid;
  gap: var(--space-4);
}
.sa-grid--priority {
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  margin-bottom: var(--space-4);
}
.sa-dashboard-section-head { margin: 4px 0 10px; }
.sa-dashboard-section-head h2 { margin: 0; color: var(--text-primary); font-size: 17px; line-height: 1.4; }
.sa-dashboard-section-head p { margin: 3px 0 0; color: var(--text-tertiary); font-size: 12px; line-height: 1.5; }
.sa-dashboard-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(152px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.sa-dashboard-metrics > :deep(.app-metric-card) {
  min-height: 108px;
  max-height: none;
  padding: 15px 16px;
  border-radius: 13px;
  box-shadow: none;
}
.sa-dashboard-metrics :deep(.app-metric-card__title) { min-height: 18px; font-size: 12px; }
.sa-dashboard-metrics :deep(.app-metric-card__value) { font-size: 32px; }
.sa-dashboard-metrics :deep(.app-metric-card__unit) { font-size: 13px; }
.sa-dashboard-metrics :deep(.app-metric-card__footer) { min-height: 4px; }
.sa-dashboard-metrics > :deep(.is-accent-warning) {
  background: linear-gradient(150deg, #fff 66%, color-mix(in srgb, var(--warning-50, #fffaeb) 74%, #fff));
}
.sa-dashboard-metrics > :deep(.is-accent-risk) {
  background: linear-gradient(150deg, #fff 66%, color-mix(in srgb, var(--danger-50, #fef3f2) 76%, #fff));
}
.sa-dashboard-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(330px, 0.34fr);
  align-items: stretch;
  gap: 16px;
}
.sa-dashboard-services {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
  gap: 16px;
  min-width: 0;
}
.sa-dashboard-panel {
  height: 100%;
  overflow: hidden;
  border-radius: 14px;
  box-shadow: none;
}
.sa-dashboard-panel :deep(.app-section-card__head) { padding: 14px 16px 12px; }
.sa-dashboard-panel :deep(.app-section-card__title) { font-size: 15px; }
.sa-dashboard-panel :deep(.app-section-card__body) { padding: 16px; }
.sa-dashboard-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
  gap: 8px;
}
.sa-dashboard-actions :deep(.app-perm-btn),
.sa-dashboard-actions :deep(.app-button) { width: 100%; }
.sa-dashboard-bridge { display: grid; align-content: space-between; gap: 14px; min-height: 88px; }
.sa-dashboard-bridge p { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.65; }
.sa-dashboard-bridge :deep(.app-perm-btn) { justify-self: start; }
.sa-dashboard-panel--audit :deep(.app-section-card__body) {
  max-height: 205px;
  overflow-y: auto;
  scrollbar-gutter: stable;
}
.sa-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-3);
}
.sa-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-light);
}
.sa-list li:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}
.sa-list li.is-actionable { cursor: pointer; border-radius: var(--radius-md); padding: var(--space-2); margin: calc(var(--space-2) * -1); transition: background .15s ease, transform .15s ease; }
.sa-list li.is-actionable:hover { background: var(--primary-50); transform: translateX(2px); }
.sa-list__action { display: inline-flex; align-items: center; gap: var(--space-2); }
.sa-list__action button { border: 0; color: var(--primary-700); background: transparent; font-weight: var(--font-weight-medium); cursor: pointer; white-space: nowrap; }
.sa-list__action b { margin-left: 3px; }
.sa-list small {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-risk-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.sa-risk-row {
  margin-bottom: var(--space-3);
  line-height: 1.6;
}
.sa-updated-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
@media (max-width: 1500px) {
  .sa-dashboard-workspace { grid-template-columns: 1fr; }
  .sa-dashboard-panel--audit :deep(.app-section-card__body) { max-height: 260px; }
}
@media (max-width: 1120px) and (min-width: 961px) {
  .sa-dashboard-services { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sa-dashboard-services > :last-child { grid-column: 1 / -1; }
}
@media (max-width: 960px) {
  .sa-grid--priority { grid-template-columns: 1fr; }
  .sa-dashboard-services { grid-template-columns: 1fr; }
  .sa-dashboard-panel--audit :deep(.app-section-card__body) { max-height: 280px; }
}
@media (max-width: 720px) {
  .sa-dashboard-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 460px) {
  .sa-dashboard-metrics { grid-template-columns: 1fr; }
}
</style>
