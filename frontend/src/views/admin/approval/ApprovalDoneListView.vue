<template>
  <ModulePageShell
    title="已办 · 抄送"
    subtitle="回看经手的办理记录与抄送知会件，支持导出留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" hint="导出默认脱敏并加水印" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          type="button"
          class="mp-tab"
          :class="{ 'is-active': activeTab === t.key }"
          @click="switchTab(t.key)"
        >
          {{ t.label }}
        </button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        :title="activeTab === 'done' ? '暂无已办记录' : '暂无抄送记录'"
        :description="activeTab === 'done' ? '办理待办后将在此沉淀经手记录' : '有需要知会的审批结果时会抄送到这里'"
      />
      <DataTable
        v-else-if="activeTab === 'done'"
        :columns="doneColumns"
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
        <template #cell-result="{ row }">
          <StatusTag :status="row.result" :label="row.resultLabel" dot />
        </template>
        <template #cell-comment="{ row }">
          <span :class="row.comment ? '' : 'mp-note'">{{ row.comment || '未填写意见' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row.taskId)">查看</button>
        </template>
      </DataTable>
      <DataTable
        v-else
        :columns="ccColumns"
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
        <template #cell-read="{ row }">
          <StatusTag :type="row.readStatus === 'UNREAD' ? 'processing' : 'default'" :label="row.readStatusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row.taskId)">查看</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="exportDialog"
      :title="activeTab === 'done' ? '导出已办记录' : '导出抄送记录'"
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
 * 已办 · 抄送（/admin/approval/done）：页内 tab 切换两类记录。
 * 行「查看」进入详情页（已办结任务详情操作区自动只读）；导出走确认弹窗并留痕。
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

const EMPTY_DONE_FILTERS = () => ({ result: '', bizType: '', keyword: '' })
const EMPTY_CC_FILTERS = () => ({ readStatus: '', keyword: '' })

export default {
  name: 'ApprovalDoneListView',
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
      tabs: [
        { key: 'done', label: '已办' },
        { key: 'cc', label: '抄送' }
      ],
      activeTab: 'done',
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_DONE_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      exportDialog: false,
      submitting: false,
      doneColumns: [
        { key: 'task', title: '审批任务' },
        { key: 'applicant', title: '申请人' },
        { key: 'node', title: '办理节点' },
        { key: 'result', title: '办理结果' },
        { key: 'comment', title: '办理意见' },
        { key: 'finishTime', title: '办结时间' },
        { key: 'actions', title: '操作', width: '90px' }
      ],
      ccColumns: [
        { key: 'task', title: '审批任务' },
        { key: 'applicant', title: '申请人' },
        { key: 'ccReason', title: '抄送说明' },
        { key: 'ccTime', title: '抄送时间' },
        { key: 'read', title: '阅读状态' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.filterOptions
      if (this.activeTab === 'done') {
        return [
          { key: 'result', label: '办理结果', type: 'select', options: o.doneResults },
          { key: 'bizType', label: '业务类型', type: 'select', options: o.bizTypes },
          { key: 'keyword', label: '关键词', type: 'text', placeholder: '标题 / 申请人' }
        ]
      }
      return [
        { key: 'readStatus', label: '阅读状态', type: 'select', options: this.ctx.statusOptions.ccReadStatus },
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '标题 / 申请人' }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportRecords', label: this.activeTab === 'done' ? '导出已办记录' : '导出抄送记录' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    switchTab(key) {
      if (this.activeTab === key) return
      this.activeTab = key
      this.filters = key === 'done' ? EMPTY_DONE_FILTERS() : EMPTY_CC_FILTERS()
      this.pagination.page = 1
      this.load()
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
      this.filters = this.activeTab === 'done' ? EMPTY_DONE_FILTERS() : EMPTY_CC_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    onToolbar(key) {
      if (key === 'exportRecords') this.exportDialog = true
    },
    goDetail(taskId) {
      this.$router.push('/admin/approval/todos/' + taskId)
    },
    async doExport() {
      this.submitting = true
      const res = await approvalApi.exportRecords({
        scope: this.activeTab === 'done' ? 'DONE' : 'CC',
        purpose: this.activeTab === 'done' ? '已办记录归档' : '抄送记录归档'
      })
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
      const params = { ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize }
      const res =
        this.activeTab === 'done'
          ? await approvalApi.getDoneItems(params)
          : await approvalApi.getCcItems(params)
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
</style>
