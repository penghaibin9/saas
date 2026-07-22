<template>
  <ModulePageShell
    title="学籍异动记录"
    subtitle="学籍管理 · 只读展示，办理请前往「学籍异动」发起与审批"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <div v-if="stats" class="aa-metric-row">
        <AppMetricCard title="累计异动" :value="stats.total" unit="条" accent-tone="primary" />
        <AppMetricCard title="已生效" :value="stats.effective" unit="条" accent-tone="success" />
        <AppMetricCard title="在途待审" :value="stats.pending" unit="条" accent-tone="warning" />
        <AppMetricCard title="已驳回" :value="stats.rejected" unit="条" accent-tone="risk" />
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无异动记录" description="当前筛选条件下没有学籍异动记录" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="changeId"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-student="{ row }">
          <button class="mp-link" @click="goStudent(row.studentId)">{{ row.realName || row.studentId }}</button>
        </template>
        <template #cell-changeType="{ row }">{{ CHANGE_TYPE_LABEL[row.changeType] || row.changeType }}</template>
        <template #cell-transition="{ row }">{{ statusLabel(row.fromStatus) }} → {{ statusLabel(row.toStatus) }}</template>
        <template #cell-status="{ row }"><AppStatusTag :status="row.status" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row.changeId)">详情</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学籍异动记录（/admin/academic-affairs/roster/changes）：只读展示，复用「学籍异动」二级模块 Round1 已建的
 * GET /academic-affairs/status-changes + /status-changes/stats（AaStatusChange 表），不重复实现审批链/发起逻辑。
 * 与「学籍异动」模块「异动台账」页共用同一后端数据源，仅去除发起/审批操作，专供「学籍管理」域内查阅。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppStatusTag, AppMetricCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const CHANGE_TYPE_LABEL = {
  ENROLL_REGISTER: '入学注册', ANNUAL_REGISTER: '学年注册', SEMESTER_REGISTER: '学期注册',
  SUSPEND: '休学', WITHDRAW: '退学', RESUME: '复学', RETAIN: '留级', TRANSFER_MAJOR: '转专业'
}
const STATUS_LABEL = {
  SUBMITTED: '待审', IN_REVIEW: '审核中', EFFECTIVE: '已生效', REJECTED: '已驳回',
  RETURNED: '已退回', CANCELLED: '已撤回'
}

export default {
  name: 'AaRosterChangeRecordsView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppMetricCard, AdvancedFilter },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      CHANGE_TYPE_LABEL, STATUS_LABEL,
      loading: true, error: '', rows: [], stats: null,
      filters: {
        changeType: '', status: '',
        studentId: this.$route.query.studentId || '',
        dateStart: '', dateEnd: ''
      },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'changeType', title: '异动类型' },
        { key: 'transition', title: '状态迁移' },
        { key: 'status', title: '当前状态' },
        { key: 'effectiveDate', title: '生效时间' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'changeType', label: '异动类型', type: 'select', placeholder: '全部',
          options: Object.entries(CHANGE_TYPE_LABEL).map(([value, label]) => ({ value, label })) },
        { key: 'status', label: '状态', type: 'select', placeholder: '全部',
          options: Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label })) },
        { key: 'studentId', label: '学生 ID', type: 'text', placeholder: '按学生 ID 过滤（可选）' },
        { key: 'date', label: '生效时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'academicAffairs.rosterChanges.dateRange', emptyLabel: '全部时间' }
      ]
    }
  },
  created() {
    this.load()
    this.loadStats()
  },
  methods: {
    statusLabel(s) {
      const map = { NORMAL: '正常', PENDING_REGISTER: '待注册', REGISTERED: '在籍注册', UNREGISTERED: '未注册',
        SUSPENDED: '休学', RETAINED: '留级', WITHDRAWN: '退学', TRANSFER_SCHOOL: '转学',
        GRADUATED: '毕业', COMPLETED: '结业', INCOMPLETE: '肄业' }
      return map[s] || s || '—'
    },
    goStudent(studentId) {
      if (studentId) this.$router.push(`/admin/academic-affairs/roster/${studentId}`)
    },
    goDetail(changeId) {
      this.$router.push(`/admin/academic-affairs/status-changes/${changeId}`)
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
      this.filters = { changeType: '', status: '', studentId: '', dateStart: '', dateEnd: '' }
      this.pagination.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getStatusChanges({
        changeType: this.filters.changeType || undefined,
        status: this.filters.status || undefined,
        studentId: this.filters.studentId || undefined,
        dateFrom: this.filters.dateStart || undefined,
        dateTo: this.filters.dateEnd || undefined,
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
    },
    async loadStats() {
      const res = await academicAffairsApi.getStatusChangeStats()
      if (res.code === 0) this.stats = res.data
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input, .aa-select {
  height: 32px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
}
.aa-metric-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--space-4); }
</style>
