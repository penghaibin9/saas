<template>
  <ModulePageShell
    title="退回记录"
    subtitle="跟踪本人退回件的原因说明与申请人整改进度"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" hint="导出默认脱敏并加水印" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="当前没有退回记录"
        description="说明近期经手的申请材料质量良好；发生退回后会在此跟踪整改进度"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-task="{ row }">
          <div class="mp-cell-main">{{ row.title }}</div>
          <div class="mp-cell-sub">{{ row.taskId }} · {{ row.bizTypeLabel }}</div>
        </template>
        <template #cell-applicant="{ row }">
          <div class="mp-cell-main">{{ row.applicantName }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-reason="{ row }">
          <span class="rl-reason" :title="row.reason">{{ row.reason }}</span>
        </template>
        <template #cell-returned="{ row }">
          <div class="mp-cell-main">{{ row.returnedBy }}</div>
          <div class="mp-cell-sub">{{ row.returnTime }}</div>
        </template>
        <template #cell-rectify="{ row }">
          <StatusTag :type="rectifyTone(row.rectifyStatus)" :label="row.rectifyStatusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/approval/todos/' + row.taskId)">查看</button>
        </template>
      </DataTable>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">整改状态说明</span>
        </div>
        <div class="mp-card__body">
          <p class="mp-note" style="margin: 0">
            待整改重报：申请人尚未重新提交；已重新提交：新版本已进入待办队列；已关闭：本次申请终止，可重新发起。
          </p>
        </div>
      </section>
    </div>

    <AppConfirmDialog
      v-model:visible="exportDialog"
      title="导出退回记录"
      message="导出文件默认脱敏敏感字段并添加页面水印，导出动作将写入审计日志。"
      type="primary"
      confirm-text="确认导出"
      :submitting="submitting"
      @confirm="doExport"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 退回记录（/admin/approval/returned）：退回原因 / 退回人 / 整改状态跟踪。
 * 行「查看」进入详情页回看时间线；空状态给出友好文案。
 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
  DataTable,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { approvalApi } from '@/modules/approval/api/approval.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ rectifyStatus: '', keyword: '' })

export default {
  name: 'ApprovalReturnedListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      exportDialog: false,
      submitting: false,
      columns: [
        { key: 'task', title: '审批任务' },
        { key: 'applicant', title: '申请人' },
        { key: 'reason', title: '退回原因', width: '260px' },
        { key: 'returned', title: '退回人 / 时间' },
        { key: 'rectify', title: '整改状态' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'rectifyStatus', label: '整改状态', type: 'select', options: this.ctx.filterOptions.rectifyStatuses },
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '标题 / 申请人' }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportRecords', label: '导出退回记录' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    rectifyTone(status) {
      if (status === 'PENDING_RESUBMIT') return 'warning'
      if (status === 'RESUBMITTED') return 'processing'
      return 'default'
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    onToolbar(key) {
      if (key === 'exportRecords') this.exportDialog = true
    },
    async doExport() {
      this.submitting = true
      const res = await approvalApi.exportRecords({ scope: 'RETURNED', purpose: '退回整改跟踪' })
      this.submitting = false
      this.exportDialog = false
      if (res.code === 0) {
        toast.success('导出任务已创建（' + res.data.auditId + '）：字段已脱敏、文件含水印，已写入审计日志')
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await approvalApi.getReturnedItems({
        ...this.filters,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.rl-reason {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}
</style>
