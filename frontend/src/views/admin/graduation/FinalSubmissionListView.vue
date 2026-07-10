<template>
  <ModulePageShell
    title="成果提交"
    subtitle="初稿 / 定稿版本与查重状态 · 查重超标的成果不可直接通过，须退回修改"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton
        v-if="exportPerm.visible"
        :export-fn="exportFinalsFn"
        :has-permission="exportPerm.allowed"
      >导出成果清单</AppExportButton>
    </template>

    <div class="mp-stack">
      <GraduationBatchStrip />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="onFilterSearch" @reset="onFilterReset" />
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前页签暂无成果提交" description="可切换页签查看其他状态" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }} · 指导教师 {{ row.advisorName }}</div>
        </template>
        <template #cell-topic="{ row }">
          <div style="font-size: var(--font-size-sm)">{{ row.topicTitle }}</div>
        </template>
        <template #cell-typeVersion="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.type }} {{ row.version }}</div>
          <div class="mp-cell-sub"><AppDateDisplay :value="row.submitAt" mode="datetime" empty-text="未提交" /></div>
          <div v-if="row.deadline" class="mp-cell-sub"><AppDateDisplay :value="row.deadline" mode="deadline" /></div>
        </template>
        <template #cell-plagiarism="{ row }">
          <StatusTag :type="row.plagiarismTone" :label="row.plagiarismRate + ' · ' + row.plagiarismStatus" />
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status === 'NOT_SUBMITTED' ? 'PENDING_SUBMIT' : row.status" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status !== 'NOT_SUBMITTED'" class="mp-link" @click="$router.push('/admin/graduation/students/' + row.projectId)">查看档案</button>
          <button
            v-if="row.status === 'PENDING_REVIEW'"
            class="mp-link"
            :class="{ 'is-disabled': !canReview }"
            :title="reviewReason"
            style="margin-left: var(--space-2)"
            @click="askReview(row, 'APPROVE')"
          >通过</button>
          <button
            v-if="row.status === 'PENDING_REVIEW'"
            class="mp-link"
            :class="{ 'is-disabled': !canReview }"
            :title="reviewReason"
            style="margin-left: var(--space-2)"
            @click="askReview(row, 'REJECT')"
          >退回</button>
          <button v-if="row.status === 'NOT_SUBMITTED'" class="mp-link" @click="remind(row)">催交</button>
        </template>
      </DataTable>

      <p class="mp-note">成果批阅（通过 / 退回修改）由指导教师执行；查重超标（&gt;30%）系统拦截不可直接通过。查重报告在学生毕设详情「查重记录」页签查看，学生端同步可见。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :submitting="submitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 成果提交列表（/admin/graduation/finals）：成果状态 + 查重状态一屏监管 + 真实批阅/催交/导出。 */
import {
  ModulePageShell, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton } from '@/components/common'
import { AppDateDisplay } from '@/components/common/date'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'

export default {
  name: 'FinalSubmissionListView',
  components: { GraduationBatchStrip, ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppDateDisplay, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      submitting: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确定', requireReason: false, reasonLabel: '', action: '', row: null },
      filters: { status: '', dateStart: '', dateEnd: '' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      tabs: [
        { value: '', label: '全部' },
        { value: 'PENDING_REVIEW', label: '待审阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已退回修改' },
        { value: 'NOT_SUBMITTED', label: '未提交' }
      ],
      columns: [
        { key: 'student', title: '学生' },
        { key: 'topic', title: '课题' },
        { key: 'typeVersion', title: '成果 / 版本' },
        { key: 'plagiarism', title: '查重' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [{
        key: 'date', label: '提交截止/时间', type: 'daterange',
        startKey: 'dateStart', endKey: 'dateEnd',
        memoryKey: 'graduation.finals.dateRange', emptyLabel: '全部时间'
      }]
    },
    canReview() {
      const pa = this.ctx.permissionActions.reviewFinal
      return !!(pa && pa.visible && pa.allowed)
    },
    reviewReason() {
      const pa = this.ctx.permissionActions.reviewFinal
      return pa && !pa.allowed ? pa.reason : ''
    },
    exportPerm() {
      const pa = this.ctx.permissionActions.exportStats || {}
      return { visible: !!pa.visible, allowed: !!pa.allowed }
    }
  },
  created() {
    this.load()
  },
  methods: {
    switchTab(v) {
      this.filters.status = v
      this.pagination.page = 1
      this.load()
    },
    onFilterSearch() { this.pagination.page = 1; this.load() },
    onFilterReset() {
      this.filters = { ...this.filters, dateStart: '', dateEnd: '' }
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    exportFinalsFn() {
      return graduationApi.exportFinals(this.filters.status)
    },
    askReview(row, action) {
      if (!this.canReview) return
      if (action === 'APPROVE') {
        this.confirm = { visible: true, title: '通过成果', message: `确认通过「${row.studentName}」的${row.type} ${row.version}？查重超标将被系统拦截。`, type: 'primary', confirmText: '通过', requireReason: false, reasonLabel: '', action: 'APPROVE', row }
      } else {
        this.confirm = { visible: true, title: '退回修改', message: `退回「${row.studentName}」的${row.type} ${row.version}，请填写退回原因（≥5 字），学生端同步可见。`, type: 'danger', confirmText: '退回修改', requireReason: true, reasonLabel: '退回原因', action: 'REJECT', row }
      }
    },
    async onConfirm({ reason } = {}) {
      const row = this.confirm.row
      if (!row) return
      this.submitting = true
      const res = await graduationApi.reviewFinal(row.id, { action: this.confirm.action, comment: reason || '' })
      this.submitting = false
      if (res.code === 0) {
        toast.success(this.confirm.action === 'APPROVE' ? '已通过，结果同步学生端' : '已退回修改，学生端可见退回原因')
        this.confirm.visible = false
        this.load()
      } else {
        toast.error(res.message || '批阅失败')
      }
    },
    async remind(row) {
      const res = await graduationApi.remindFinal(row.projectId || row.gdStudentId)
      if (res.code === 0) toast.success('已向 ' + row.studentName + ' 发送成果催交提醒，催办已留痕')
      else toast.error(res.message || '催交失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getFinalSubmissions({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
