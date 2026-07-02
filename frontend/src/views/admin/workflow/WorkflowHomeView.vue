<template>
  <div class="wf-page">
    <AppSectionHeader index="11" title="权限与流程中心" subtitle="全系统审批、权限、角色与数据范围的统一底座" />
    <WorkflowStateBlock :loading="loading" :error="error" :empty="!overview" :view-state="viewState" @retry="load">
      <template v-if="overview">
        <div class="wf-page__grid4">
          <WorkflowOverviewCard label="待处理审批" :value="overview.pendingTaskCount" unit="项" hint="点击进入审批任务中心" clickable @click="go('/admin/workflow/tasks')" />
          <WorkflowOverviewCard label="流程模板" :value="overview.templateCount" unit="个" :hint="`已启用 ${overview.enabledTemplateCount} 个`" clickable @click="go('/admin/workflow/processes')" />
          <WorkflowOverviewCard label="角色" :value="overview.roleCount" unit="个" hint="含数据范围绑定" clickable @click="go('/admin/workflow/roles')" />
          <WorkflowOverviewCard label="权限点" :value="overview.permissionCount" unit="个" hint="MENU / PAGE / BUTTON / DATA" clickable @click="go('/admin/workflow/permissions')" />
        </div>

        <AppInlineAlert
          v-for="h in overview.abnormalHints"
          :key="h.type"
          :type="h.level === 'warning' ? 'warning' : 'info'"
          :description="h.text"
          class="wf-page__hint"
        />

        <div class="wf-page__cols">
          <AppCard class="wf-page__card">
            <AppSectionHeader title="各模块流程启用情况" compact />
            <table class="wf-table">
              <thead>
                <tr><th>业务模块</th><th>模板（启用/总数）</th><th>待处理审批</th></tr>
              </thead>
              <tbody>
                <tr v-for="m in overview.moduleUsage" :key="m.moduleCode">
                  <td>{{ moduleLabel(m.moduleCode) }}</td>
                  <td>{{ m.enabledTemplates }} / {{ m.totalTemplates }}</td>
                  <td>
                    <AppBadge :type="m.pendingTasks > 0 ? 'warning' : 'neutral'">{{ m.pendingTasks }}</AppBadge>
                  </td>
                </tr>
              </tbody>
            </table>
          </AppCard>

          <AppCard class="wf-page__card">
            <AppSectionHeader title="最近审批记录" compact />
            <ApprovalTimeline :records="overview.recentRecords" />
          </AppCard>
        </div>

        <AppCard class="wf-page__card">
          <AppSectionHeader title="高频业务流程入口" subtitle="后续业务模块（实习/毕设/迎新/主档）统一挂接本中心" compact />
          <div class="wf-page__entries">
            <AppButton v-for="e in entries" :key="e.label" variant="secondary" @click="go(e.path)">{{ e.label }}</AppButton>
          </div>
        </AppCard>
      </template>
    </WorkflowStateBlock>
  </div>
</template>

<script>
/** 页面 1：/admin/workflow 权限与流程中心首页 */
import { AppCard, AppBadge, AppButton, AppSectionHeader } from '@/components/ui'
import AppInlineAlert from '@/components/common/AppInlineAlert.vue'
import WorkflowStateBlock from '@/modules/workflow/components/WorkflowStateBlock.vue'
import WorkflowOverviewCard from '@/modules/workflow/components/WorkflowOverviewCard.vue'
import ApprovalTimeline from '@/modules/workflow/components/ApprovalTimeline.vue'
import { workflowProvider, getModuleLabel } from '@/modules/workflow'

export default {
  name: 'WorkflowHomeView',
  components: { AppCard, AppBadge, AppButton, AppSectionHeader, AppInlineAlert, WorkflowStateBlock, WorkflowOverviewCard, ApprovalTimeline },
  data() {
    return {
      loading: false,
      error: '',
      overview: null,
      entries: [
        { label: '实习申请审批', path: '/admin/workflow/tasks' },
        { label: '实习周报批阅', path: '/admin/workflow/tasks' },
        { label: '毕设材料审阅', path: '/admin/workflow/tasks' },
        { label: '主档变更审批', path: '/admin/workflow/tasks' },
        { label: '流程模板维护', path: '/admin/workflow/processes' }
      ]
    }
  },
  computed: {
    viewState() {
      return workflowProvider.getLicenseViewState()
    }
  },
  watch: {
    '$route.query.lv'() {
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    moduleLabel: getModuleLabel,
    go(path) {
      this.$router.push(path)
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await workflowProvider.getWorkflowOverview()
        if (res.code === 0) this.overview = res.data
        else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import './workflow-page.css';
</style>
