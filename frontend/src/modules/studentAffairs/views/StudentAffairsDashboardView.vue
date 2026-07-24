<template>
  <AppPageShell
    title="学工看板"
    subtitle="聚合今日待办、学生风险、请假审批、宿舍异常和跨系统入口，数据按当前身份范围返回。"
    :role-name="dashboard.viewLabel"
    :data-scope-name="scopeLabel"
    watermark-purpose="学工看板查看"
  >
    <template #actions>
      <span class="sa-updated-hint">
        数据更新于 <AppDateDisplay :value="dashboard.updatedAt" mode="datetime" empty-text="—" />
      </span>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dashboard.refresh')" code="studentAffairs.dashboard.refresh" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="true" />
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学工看板真实数据…"
      @retry="load"
      @back="$router.push('/')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard
          v-for="card in metricCards"
          :key="card.key"
          :title="card.label"
          :value="card.value"
          :unit="card.unit"
          :accent="metricAccent(card.key)"
          drillable
          :drill-target="metricTarget(card.key)"
          @drill="go"
        />
      </div>

      <div class="sa-grid sa-grid--two">
        <AppSectionCard title="今日待办">
          <ul class="sa-list">
            <li v-for="item in todoItems" :key="item.key">
              <span>
                <strong>{{ item.label }}</strong>
                <small>{{ item.hint }}</small>
              </span>
              <AppStatusTag :type="item.count > 0 ? 'warning' : 'success'" :label="`${item.count} 件`" />
            </li>
          </ul>
        </AppSectionCard>

        <AppSectionCard title="学生风险概览">
          <div class="sa-risk-row">
            <AppRiskTag :level="riskLevel" />
            <span>{{ riskSummary }}</span>
          </div>
          <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" variant="secondary" @click="go('/admin/student-affairs/risk')">
            进入风险预警
          </AppPermissionButton>
        </AppSectionCard>

        <AppSectionCard title="数字迎新摘要">
          <div class="sa-bridge">
            <AppStatusTag type="info" label="外部系统承接" />
            <p>本轮只提供入口和摘要，不修数字迎新主链路、日期底座或导出台账。</p>
            <AppPermissionButton :allowed="canBtn('orientation.dashboard.view')" code="orientation.dashboard.view" variant="secondary" @click="go('/admin/orientation')">
              打开数字迎新
            </AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="在校服务摘要">
          <div class="sa-bridge">
            <AppStatusTag type="info" label="过渡入口" />
            <p>请假、宿舍、风险等高频入口逐步收口到学工中心，旧在校服务保留兼容跳转。</p>
            <AppPermissionButton :allowed="canBtn('campusService.dashboard.view')" code="campusService.dashboard.view" variant="secondary" @click="go('/admin/campus-service')">
              打开在校服务
            </AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="跨中心风险入口">
          <div class="sa-actions">
            <AppPermissionButton :allowed="canBtn('internship.risk.view')" code="internship.risk.view" variant="secondary" @click="go('/admin/internship/risks')">
              岗位实习风险
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('graduation.risk.view')" code="graduation.risk.view" variant="secondary" @click="go('/admin/graduation/risk-archive?panel=risk')">
              毕业设计风险
            </AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="操作审计入口">
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
      dashboard: { summaryCards: [], moduleCards: [], viewLabel: '', scopeMode: '' },
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
      return this.dashboard.summaryCards || []
    },
    scopeLabel() {
      const map = { ADMIN_TENANT: '全校', SCOPED: '本人负责范围', TENANT_FALLBACK: '当前租户' }
      return map[this.dashboard.scopeMode] || this.dashboard.scopeMode || '按当前身份'
    },
    todoItems() {
      const value = (key) => this.metricCards.find((c) => c.key === key)?.value || 0
      return [
        { key: 'todo', label: '今日待办', count: value('pendingTodo'), hint: '统一待办中心待处理事项' },
        { key: 'leave', label: '请假审批概览', count: value('pendingLeave'), hint: '待辅导员/学院/学工处处理' },
        { key: 'dorm', label: '宿舍异常概览', count: value('overdueLeave'), hint: 'B2 接入夜不归宿与宿舍异常' },
        { key: 'focus', label: '重点学生提醒', count: value('riskStudents'), hint: '来自风险预警未关闭学生' }
      ]
    },
    riskLevel() {
      const count = Number(this.metricCards.find((c) => c.key === 'riskStudents')?.value || 0)
      if (count >= 10) return 'HIGH'
      if (count > 0) return 'MEDIUM'
      return 'LOW'
    },
    riskSummary() {
      const count = this.metricCards.find((c) => c.key === 'riskStudents')?.value || 0
      return count ? `当前范围内有 ${count} 名学生存在未关闭风险。` : '当前范围暂无未关闭风险。'
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
    metricTarget(key) {
      const map = {
        studentTotal: '/admin/student/list',
        classTotal: '/admin/campus-service/classes',
        pendingLeave: '/admin/campus-service/leave',
        overdueLeave: '/admin/campus-service/leave-extensions',
        riskStudents: '/admin/student-affairs/risk'
      }
      return map[key] || '/admin/approval/todos'
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
.sa-grid--metrics {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}
.sa-grid--two {
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
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
}
.sa-list small {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-risk-row,
.sa-actions,
.sa-bridge {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.sa-bridge p {
  flex-basis: 100%;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.sa-updated-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
</style>

