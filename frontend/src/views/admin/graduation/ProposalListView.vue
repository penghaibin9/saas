<template>
  <ModulePageShell
    title="开题材料"
    subtitle="承接学生端 P15 毕设提交 / 教师端 T24 开题批阅 · 驳回原因必填并同步学生端"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="onFilterSearch" @reset="onFilterReset" />
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前页签暂无开题材料" description="可切换页签查看其他状态" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }} · 指导教师 {{ row.advisorName }}</div>
        </template>
        <template #cell-topic="{ row }">
          <div style="font-size: var(--font-size-sm)">{{ row.topicTitle }}</div>
        </template>
        <template #cell-version="{ row }">
          <StatusTag v-if="row.isResubmit" type="info" :label="row.version + ' 重交'" />
          <span v-else>{{ row.version }}</span>
        </template>
        <template #cell-submitAt="{ row }">
          <AppDateDisplay :value="row.submitAt" mode="datetime" />
          <div v-if="row.deadline" class="mp-cell-sub"><AppDateDisplay :value="row.deadline" mode="deadline" /></div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status === 'NOT_SUBMITTED' ? 'OVERDUE' : row.status" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'NOT_SUBMITTED'" class="mp-link" @click="remind(row)">催交</button>
          <button v-else class="mp-link" @click="$router.push('/admin/graduation/proposals/' + row.id)">
            {{ row.status === 'PENDING_REVIEW' ? '批阅' : '查看' }}
          </button>
        </template>
      </DataTable>

      <p class="mp-note">筛选默认「全部时间」，空日期不会导致查无数据。「通过 / 驳回」在批阅详情内按指导教师权限控制。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 开题材料列表（/admin/graduation/proposals）。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

export default {
  name: 'ProposalListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: { status: 'PENDING_REVIEW', dateStart: '', dateEnd: '' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      tabs: [
        { value: 'PENDING_REVIEW', label: '待审阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已驳回' },
        { value: 'NOT_SUBMITTED', label: '逾期未交' },
        { value: '', label: '全部' }
      ],
      columns: [
        { key: 'student', title: '学生' },
        { key: 'topic', title: '课题' },
        { key: 'version', title: '版本' },
        { key: 'submitAt', title: '提交 / 截止' },
        { key: 'attachments', title: '附件' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [{
        key: 'date', label: '提交时间', type: 'daterange',
        startKey: 'dateStart', endKey: 'dateEnd',
        memoryKey: 'graduation.proposals.dateRange', emptyLabel: '全部时间'
      }]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportProposals', label: '导出开题材料' }]
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
    async onToolbar() {
      const res = await graduationApi.downloadProposalsExport(this.filters.status)
      if (res.code === 0) toast.success('开题材料台账已导出（含导出人/时间抬头），已写入审计日志')
      else toast.error(res.message || '导出失败')
    },
    async remind(row) {
      const res = await graduationApi.remindProposal(row.projectId || row.gdStudentId)
      if (res.code === 0) toast.success('已向 ' + row.studentName + ' 发送开题催交提醒（GD-R04 联动），催办已留痕')
      else toast.error(res.message || '催交失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getProposals({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
