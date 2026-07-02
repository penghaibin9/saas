<template>
  <div class="wf-page">
    <AppSectionHeader title="审批任务中心" subtitle="全模块审批任务的统一处理入口（通过 / 退回 / 撤回全程留痕）" />

    <div class="wf-page__tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="wf-page__tab"
        :class="{ 'is-active': activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >{{ tab.label }}</button>
    </div>

    <div class="wf-page__filters">
      <select v-model="filters.moduleCode" @change="load">
        <option value="">全部模块</option>
        <option v-for="(label, code) in moduleOptions" :key="code" :value="code">{{ label }}</option>
      </select>
      <input v-model.trim="filters.keyword" placeholder="搜索标题 / 申请人 / 业务编号" @keyup.enter="load" />
      <AppButton variant="secondary" @click="load">查询</AppButton>
    </div>

    <WorkflowStateBlock :loading="loading" :error="error" :empty="!list.length" :view-state="viewState" @retry="load">
      <div class="wf-page__split">
        <ApprovalTaskList :tasks="list" :active-id="activeTask ? activeTask.taskId : ''" @select="selectTask" />
        <ApprovalTaskDetailPanel
          :task="activeTask"
          :permission-context="permissionContext"
          :readonly="readonly"
          :submitting="submitting"
          @approve="onApprove"
          @reject="onReject"
          @withdraw="askWithdraw"
        />
      </div>
    </WorkflowStateBlock>

    <AppConfirmDialog
      v-model:visible="withdrawVisible"
      type="warning"
      title="确认撤回"
      message="撤回后任务回到发起节点，需重新提交才会再次进入审批。"
      confirm-text="确认撤回"
      :submitting="submitting"
      @confirm="onWithdrawConfirm"
    />
  </div>
</template>

<script>
/** 页面 3：/admin/workflow/tasks 审批任务中心 */
import { AppButton, AppSectionHeader } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import WorkflowStateBlock from '@/modules/workflow/components/WorkflowStateBlock.vue'
import ApprovalTaskList from '@/modules/workflow/components/ApprovalTaskList.vue'
import ApprovalTaskDetailPanel from '@/modules/workflow/components/ApprovalTaskDetailPanel.vue'
import { workflowProvider, getPermissionContext, TASK_FILTER_TABS, MODULE_LABELS } from '@/modules/workflow'
import { toast } from '@/utils/toast'

export default {
  name: 'WorkflowTasksView',
  components: { AppButton, AppSectionHeader, AppConfirmDialog, WorkflowStateBlock, ApprovalTaskList, ApprovalTaskDetailPanel },
  data() {
    return {
      loading: false,
      error: '',
      list: [],
      activeTab: 'ALL',
      filters: { moduleCode: '', keyword: '' },
      activeTask: null,
      submitting: false,
      withdrawVisible: false,
      withdrawTarget: null
    }
  },
  computed: {
    tabs: () => TASK_FILTER_TABS,
    moduleOptions: () => MODULE_LABELS,
    viewState() {
      return workflowProvider.getLicenseViewState()
    },
    readonly() {
      return this.viewState === 'READONLY'
    },
    permissionContext() {
      return getPermissionContext()
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
    switchTab(key) {
      this.activeTab = key
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await workflowProvider.getApprovalTasks({ tab: this.activeTab, ...this.filters })
        if (res.code === 0) {
          this.list = res.data.list
          // 保持选中任务的最新数据；不存在则默认选第一条
          const keep = this.activeTask && this.list.find((t) => t.taskId === this.activeTask.taskId)
          this.activeTask = keep || this.list[0] || null
        } else {
          this.error = res.message
        }
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async selectTask(t) {
      const res = await workflowProvider.getApprovalTaskDetail(t.taskId)
      this.activeTask = res.code === 0 ? res.data : t
    },
    async onApprove(task) {
      this.submitting = true
      try {
        const res = await workflowProvider.approveTask(task.taskId, {})
        if (res.code === 0) {
          toast.success('已通过，审批记录已留痕')
          this.activeTask = res.data
          await this.load()
        } else {
          toast.warning(res.message)
        }
      } finally {
        this.submitting = false
      }
    },
    async onReject({ task, reason }) {
      this.submitting = true
      try {
        const res = await workflowProvider.rejectTask(task.taskId, { reason })
        if (res.code === 0) {
          toast.success('已退回，业务回到发起人可编辑状态')
          this.activeTask = res.data
          await this.load()
        } else {
          toast.warning(res.message)
        }
      } finally {
        this.submitting = false
      }
    },
    askWithdraw(task) {
      this.withdrawTarget = task
      this.withdrawVisible = true
    },
    async onWithdrawConfirm() {
      if (!this.withdrawTarget) return
      this.submitting = true
      try {
        const res = await workflowProvider.withdrawTask(this.withdrawTarget.taskId, {})
        if (res.code === 0) {
          toast.success('已撤回')
          this.activeTask = res.data
          this.withdrawVisible = false
          await this.load()
        } else {
          toast.warning(res.message)
        }
      } finally {
        this.submitting = false
        this.withdrawTarget = null
      }
    }
  }
}
</script>

<style scoped>
@import './workflow-page.css';
</style>
