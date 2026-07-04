<template>
  <BasePortalLayout
    title="高校学生全生命周期管理平台"
    subtitle="产品体验中心"
    :menus="navMenus"
    :active-key="activeSection"
    @menu-select="onMenuSelect"
    @menu-disabled="onMenuDisabled"
  >
    <template #header-right>
      <DataQualityBar :quality="dashboard.dataQuality" />
      <AppStatusTag type="processing" :label="dashboard.dataQuality.environment" dot />
      <span class="header-user">{{ dashboard.teacherRole }}</span>
    </template>

    <div class="experience">
      <div id="overview">
        <LifecycleTimeline
          title="高校学生全生命周期运行中心"
          subtitle="围绕迎新、毕业设计、岗位实习、基础能力验证的全过程协同与风险闭环"
          :stages="dashboard.lifecycleBannerStages"
          :capsules="dashboard.bannerCapsules"
        />
      </div>

      <AppGlobalState :state="dashboard.viewState" @retry="dashboard.initDashboard()">
        <template v-if="dashboard.initialized">
          <section id="lifecycle" class="dash-section">
            <AppSectionHeader
              index="01"
              title="生命周期阶段进度"
              subtitle="各环节完成率与风险联动监测"
            />
            <div class="dash-grid-stages">
              <AppLifecycleStageCard
                v-for="s in dashboard.lifecycleStageCards"
                :key="s.stageId"
                :name="s.name"
                :status="s.cardStatus"
                :status-type="s.statusType"
                :rate="s.completionRate ?? s.rate"
                :risk-count="s.riskCount"
                :action-label="s.actionLabel || s.actionText"
                @action="setTopicTab('internship')"
              />
            </div>
          </section>

          <section id="kpi" class="dash-section">
            <AppSectionHeader
              index="02"
              title="核心运行指标"
              subtitle="全校学生生命周期关键指标一览"
            />
            <div class="dash-grid-kpi">
              <MetricCard
                v-for="m in dashboard.dashboardMetrics"
                :key="m.metricId || m.id"
                v-bind="m"
                :accent="metricAccent(m)"
                @drill="onDrill"
              />
            </div>
          </section>

          <section id="risk-center" class="dash-section dash-section--risk">
            <AppSectionHeader index="03" title="风险预警中心" subtitle="多维度风险识别与处理闭环">
              <template #title-extra>
                <AppStatusTag type="warning" label="重点关注" dot />
              </template>
              <template #extra>
                <button
                  v-if="!dashboard.showAllRisks && dashboard.activeRisks.length > 3"
                  type="button"
                  class="dash-risk-summary-toggle"
                  @click="dashboard.setShowAllRisks(true)"
                >
                  查看全部 {{ dashboard.activeRisks.length }} 类
                </button>
                <span v-else class="dash-badge-count"
                  >{{ dashboard.activeRisks.length }} 类待关注</span
                >
              </template>
            </AppSectionHeader>
            <div class="dash-risk-list">
              <RiskAlertCard
                v-for="r in dashboard.displayedRiskAlerts"
                :key="r.riskId"
                :risk="r"
                @handle="onRiskHandle(r.riskId)"
              />
            </div>
          </section>

          <div class="dash-grid-split">
            <section id="workbench" class="dash-section">
              <AppSectionHeader
                index="04"
                title="教师今日工作台"
                :subtitle="dashboard.workbenchSubtitle"
                compact
              >
                <template #extra>
                  <span class="dash-badge-count dash-badge-count--warning"
                    >{{ dashboard.activeTodoTotal }} 项待办</span
                  >
                </template>
              </AppSectionHeader>
              <TaskWorkbenchPanel
                :groups="dashboard.limitedTaskGroups"
                @handle-task="dashboard.openTaskDrawer"
              />
            </section>

            <section id="students" class="dash-section dash-section--risk">
              <AppSectionHeader
                index="05"
                title="重点关注学生"
                subtitle="中高风险学生持续跟进画像"
                compact
              >
                <template #title-extra>
                  <span class="dash-badge-count">{{ dashboard.focusStudentCount }}人</span>
                </template>
              </AppSectionHeader>
              <div class="dash-card-list" ref="studentListRef">
                <StudentRiskCard
                  v-for="s in dashboard.focusStudents"
                  :key="s.studentId"
                  :data-student-id="s.studentId"
                  :student="s"
                  @contact="dashboard.openStudentDrawer(s.studentId)"
                  @remind="dashboard.remindStudent()"
                  @follow="dashboard.addFollowUp()"
                  @resolve="dashboard.resolveRisk()"
                />
              </div>
            </section>
          </div>

          <section id="records" class="dash-section">
            <AppSectionHeader
              index="06"
              title="最近处理记录"
              subtitle="风险处理与业务操作留痕台账"
              compact
            />
            <OperationLogList :logs="dashboard.latestOperationLogs" />
          </section>

          <section id="topics" class="dash-section">
            <AppSectionHeader index="07" title="专题明细" subtitle="按业务专题查看指标明细" />
            <TopicDetailPanel
              :active-tab="activeTopicTab"
              :practice-metrics="dashboard.overviewMetrics"
              :graduation-metrics="dashboard.gdMetrics"
              :internship-metrics="dashboard.internshipMetrics"
              @update:active-tab="activeTopicTab = $event"
              @drill="onDrill"
            />
          </section>
        </template>
      </AppGlobalState>
    </div>

    <RiskHandleDrawer
      :visible="dashboard.drawerVisible"
      :title="dashboard.drawerTitle"
      :payload="dashboard.selectedHandleDetail"
      @update:visible="
        (v) => {
          if (!v) dashboard.closeHandleDrawer()
        }
      "
      @contact="dashboard.contactStudent()"
      @remind="dashboard.remindStudent()"
      @follow="dashboard.addFollowUp()"
      @resolve="dashboard.resolveRisk()"
    />
  </BasePortalLayout>
</template>

<script>
import { onMounted } from 'vue'
import { AppStatusTag, AppGlobalState } from '@/components/common'
import {
  AppSectionHeader,
  AppLifecycleStageCard,
  LifecycleTimeline,
  MetricCard,
  RiskAlertCard,
  StudentRiskCard,
  OperationLogList,
  RiskHandleDrawer,
  DataQualityBar,
  TaskWorkbenchPanel,
  TopicDetailPanel
} from '@/components/dashboard'
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { useDashboardStore } from '@/modules/dashboard'
import { metricAccent } from '@/components/dashboard/presentation.js'
import { toast } from '@/utils/toast'
import '@/styles/dashboard.css'

export default {
  name: 'UiPreview',
  components: {
    BasePortalLayout,
    AppStatusTag,
    AppGlobalState,
    AppSectionHeader,
    AppLifecycleStageCard,
    LifecycleTimeline,
    MetricCard,
    RiskAlertCard,
    StudentRiskCard,
    OperationLogList,
    RiskHandleDrawer,
    DataQualityBar,
    TaskWorkbenchPanel,
    TopicDetailPanel
  },
  setup() {
    const dashboard = useDashboardStore()
    onMounted(() => dashboard.initDashboard('t-002'))
    return { dashboard, metricAccent, toast }
  },
  data() {
    return {
      activeSection: 'overview',
      activeTopicTab: 'internship'
    }
  },
  computed: {
    navMenus() {
      const d = this.dashboard
      return [
        { key: 'overview', label: '产品概览', icon: 'overview' },
        { key: 'lifecycle', label: '阶段进度', icon: 'lifecycle' },
        { key: 'kpi', label: '核心指标', icon: 'kpi' },
        {
          key: 'risk-center',
          label: '风险预警',
          icon: 'risk',
          badge: d.activeRisks.length || undefined
        },
        { key: 'workbench', label: '待办任务', icon: 'workbench', badge: d.activeTodoTotal || undefined },
        {
          key: 'students',
          label: '重点关注学生',
          icon: 'students',
          badge: d.focusStudentCount || undefined
        },
        { key: 'topics', label: '专题明细', icon: 'topics' },
        { key: 'records', label: '处理记录', icon: 'records' },
        {
          key: 'enrollment',
          label: '迎新管理',
          icon: 'enrollment',
          disabled: true,
          disabledTip: '迎新管理即将上线'
        },
        {
          key: 'reports',
          label: '数据报表',
          icon: 'reports',
          disabled: true,
          disabledTip: '数据报表即将上线'
        },
        {
          key: 'settings',
          label: '系统设置',
          icon: 'settings',
          disabled: true,
          disabledTip: '系统设置即将上线'
        }
      ]
    }
  },
  methods: {
    scrollTo(id) {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
    setTopicTab(tab) {
      this.activeTopicTab = tab
      this.scrollTo('topics')
    },
    onMenuSelect(item) {
      this.activeSection = item.key
      if (item.key === 'topics') this.activeTopicTab = 'internship'
      this.scrollTo(item.key)
    },
    onMenuDisabled(item) {
      this.toast.info(item.disabledTip || `${item.label}即将上线`)
    },
    onDrill(target) {
      this.toast.info(`下钻至：${target}`)
    },
    onRiskHandle(riskId) {
      const scrollToStudent = (studentId) => {
        const el = this.$refs.studentListRef?.querySelector(`[data-student-id="${studentId}"]`)
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
      this.dashboard.handleRiskAlert(riskId, scrollToStudent)
    }
  }
}
</script>

<style scoped>
.experience {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
  overflow-x: hidden;
}
.header-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
@media (max-width: 760px) {
  .header-user {
    display: none;
  }
}
</style>
