<template>
  <ModulePageShell
    title="异动生效"
    subtitle="已终审通过并写入学籍主档的学籍异动（只读；生效时点学籍状态/院系班已发生真实变化）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无已生效异动" description="终审通过的休学/复学/退学/转专业/留级申请将在此展示" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.realName }}</div></template>
        <template #cell-type="{ row }"><StatusTag type="primary" :label="row.changeTypeLabel" dot /></template>
        <template #cell-change="{ row }">
          <span class="mp-cell-sub">{{ row.fromStatus }} → <b>{{ row.toStatus }}</b></span>
        </template>
        <template #cell-effectiveDate="{ row }">{{ row.effectiveDate || '—' }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">异动详情</button>
          <button class="mp-link" style="margin-left: var(--space-2)" @click="goArchive(row)">学籍档案</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学籍异动生效台账（Tier1「异动生效」，/admin/academic-affairs/status-changes/effective）。
 * 只读：复用既有 GET /status-changes?status=EFFECTIVE（终审通过时已经由
 * change_student_status() 单一入口原子写入学籍主档 + StudentStageEvent，本页不重复任何写操作，
 * 仅做「生效结果」的检索与佐证跳转）。
 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TYPE_LABEL } from '@/modules/academicAffairs/constants/status-change'

const EMPTY = () => ({ changeType: '', studentId: '', dateStart: '', dateEnd: '' })

export default {
  name: 'AaStatusChangeEffectiveView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], page: 1, pageSize: 20, total: 0, filters: EMPTY(),
      columns: [
        { key: 'student', title: '学生' },
        { key: 'type', title: '异动类型' },
        { key: 'change', title: '学籍状态变化' },
        { key: 'effectiveDate', title: '生效日期' },
        { key: 'actions', title: '操作', width: '180px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: Object.keys(TYPE_LABEL).map((v) => ({ value: v, label: TYPE_LABEL[v] })) },
        { key: 'studentId', label: '学生ID', type: 'text', placeholder: '按学生主键过滤' },
        { key: 'date', label: '生效时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'academicAffairs.statusChangeEffective.dateRange', emptyLabel: '全部时间' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    goDetail(row) { this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`) },
    goArchive(row) { this.$router.push(`/admin/academic-affairs/roster?keyword=${encodeURIComponent(row.realName || '')}`) },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const res = await academicAffairsApi.getStatusChanges({
        changeType: this.filters.changeType || undefined,
        studentId: this.filters.studentId || undefined,
        dateFrom: this.filters.dateStart || undefined,
        dateTo: this.filters.dateEnd || undefined,
        status: 'EFFECTIVE', page: this.page, pageSize: this.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
