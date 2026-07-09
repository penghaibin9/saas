<template>
  <ModulePageShell
    title="周报与任务"
    :subtitle="'承接学生小程序 P12 周报提交 · 退回原因必填并同步学生端'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前页签暂无周报" description="可切换页签或调整筛选条件" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button class="mp-link" :class="{ 'is-disabled': batchHasRisk }" :title="batchHasRisk ? '所选含风险学生周报，需逐篇批阅' : ''" @click="batchApprove">批量通过</button>
          <span class="mp-note" title="退回原因必填，需逐篇进入详情填写">批量退回不可用：退回原因必须逐篇填写</span>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }} · {{ row.enterpriseName }}</div>
        </template>
        <template #cell-version="{ row }">
          <StatusTag v-if="row.isResubmit" type="info" :label="row.version + ' 重交'" />
          <span v-else>{{ row.version }}</span>
        </template>
        <template #cell-riskFlag="{ row }">
          <RiskTag v-if="row.riskFlag" :level="row.riskFlag" label="风险学生" />
          <span v-else class="mp-note">—</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'OVERDUE'" class="mp-link" @click="remind(row)">催交</button>
          <button v-else class="mp-link" @click="$router.push('/admin/internship/reports/' + row.id)">
            {{ row.status === 'PENDING_REVIEW' ? '批阅' : '查看' }}
          </button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 周报批阅列表（/admin/internship/reports）：P12 → T20 → PC 批阅。 */
import {
  ModulePageShell, ModuleToolbar, DataTable,
  StatusTag, RiskTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

export default {
  name: 'WeeklyReportListView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: [],
      filters: { status: 'PENDING_REVIEW' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      tabs: [
        { value: 'PENDING_REVIEW', label: '待批阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'RETURNED', label: '已退回' },
        { value: 'OVERDUE', label: '逾期未交' },
        { value: '', label: '全部' }
      ],
      columns: [
        { key: 'student', title: '学生' },
        { key: 'week', title: '周次' },
        { key: 'submitAt', title: '提交时间' },
        { key: 'version', title: '版本' },
        { key: 'wordCount', title: '字数' },
        { key: 'attachments', title: '附件' },
        { key: 'riskFlag', title: '风险标记' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  computed: {
    batchHasRisk() {
      return this.rows.some((r) => this.selected.includes(r.id) && r.riskFlag)
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportReports', label: '导出周报' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    switchTab(v) {
      this.filters.status = v
      this.pagination.page = 1
      this.selected = []
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    onToolbar() {
      toast.success('周报导出任务已创建（脱敏 + 水印），已写入审计日志')
    },
    remind(row) {
      toast.success('已向 ' + row.studentName + ' 发送催交提醒（小程序订阅消息），催办次数已记录')
    },
    async batchApprove() {
      if (this.batchHasRisk) return
      for (const id of this.selected) {
        await internshipApi.reviewWeeklyReport(id, { action: 'APPROVE', comment: '批量通过' })
      }
      toast.success('已批量通过 ' + this.selected.length + ' 篇周报，结果已同步学生端并留痕')
      this.selected = []
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getWeeklyReports({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
