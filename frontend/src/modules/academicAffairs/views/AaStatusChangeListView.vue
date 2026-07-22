<template>
  <ModulePageShell
    title="学籍异动"
    subtitle="休学 / 退学 / 复学 / 留级 / 转专业 —— 多节点审批，终审生效写主档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/status-changes/new')">＋ 发起异动</AppButton>
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无学籍异动" description="点击右上角「发起异动」或从学籍名册对某学生发起" />
      <template v-else>
        <div class="aa-chips">
          <span v-for="c in pageStats" :key="c.key" class="aa-chip">{{ c.label }} {{ c.count }}</span>
          <span class="aa-chips__note">（本页 {{ rows.length }} 条统计）</span>
        </div>
        <DataTable
          :columns="columns"
          :rows="rows"
          row-key="changeId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.realName }}</div>
            <div class="mp-cell-sub">{{ row.fromStatus }} → {{ row.toStatus }}</div>
          </template>
          <template #cell-type="{ row }">
            <AppStatusTag type="primary">{{ row.changeTypeLabel }}</AppStatusTag>
          </template>
          <template #cell-node="{ row }">
            <span>{{ nodeLabel(row.currentNode) }}</span>
          </template>
          <template #cell-status="{ row }">
            <AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <button class="mp-link" @click="goDetail(row)">详情 / 审批</button>
          </template>
        </DataTable>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学籍异动列表（/admin/academic-affairs/status-changes）：GET /academic-affairs/status-changes。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TYPE_LABEL, STATUS_LABEL, NODE_LABEL, statusColor } from '@/modules/academicAffairs/constants/status-change'

export default {
  name: 'AaStatusChangeListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AdvancedFilter },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TYPE_LABEL,
      STATUS_LABEL,
      loading: true,
      error: '',
      rows: [],
      filters: { changeType: '', status: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'student', title: '学生 / 状态变化' },
        { key: 'type', title: '异动类型' },
        { key: 'node', title: '当前节点' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        {
          key: 'changeType',
          label: '异动类型',
          type: 'select',
          placeholder: '全部',
          options: Object.keys(TYPE_LABEL).map((val) => ({ value: val, label: TYPE_LABEL[val] }))
        },
        {
          key: 'status',
          label: '状态',
          type: 'select',
          placeholder: '全部',
          options: Object.keys(STATUS_LABEL).map((val) => ({ value: val, label: STATUS_LABEL[val] }))
        }
      ]
    },
    pageStats() {
      const m = {}
      for (const r of this.rows) m[r.status] = (m[r.status] || 0) + 1
      return Object.keys(m).map((k) => ({ key: k, label: STATUS_LABEL[k] || k, count: m[k] }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusColor,
    nodeLabel(n) { return n ? (NODE_LABEL[n] || n) : '—' },
    goDetail(row) {
      this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`)
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
      this.filters.changeType = ''
      this.filters.status = ''
      this.search()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getStatusChanges({
        changeType: this.filters.changeType || undefined,
        status: this.filters.status || undefined,
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
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-chips { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.aa-chip { padding: 3px 10px; border-radius: 12px; background: var(--fill-100, #f2f3f5); font-size: 12px; color: var(--text-700, #4e5969); }
.aa-chips__note { font-size: 12px; color: var(--text-400, #8a9099); }
</style>
