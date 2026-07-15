<template>
  <ModulePageShell
    title="学期切换记录"
    subtitle="谁在什么时候把「当前学期」从哪个学期切到了哪个学期 · 只读审计，数据来自学期发布/当前学期设置留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="还没有切换记录"
        description="在「学年学期」发布学期或在「当前学期设置」切换当前学期后，这里会自动生成记录"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-occurredAt="{ row }">{{ formatTime(row.occurredAt) }}</template>
        <template #cell-switch="{ row }">
          <div class="aa-switch-cell">
            <span v-if="row.fromTermLabel" class="aa-switch-from">{{ row.fromTermLabel }}</span>
            <span v-else class="aa-switch-from aa-switch-from--empty">（首次设置）</span>
            <span class="aa-switch-arrow">→</span>
            <span class="aa-switch-to">{{ row.toTermLabel || '—' }}</span>
          </div>
        </template>
        <template #cell-action="{ row }">
          <AppStatusTag :type="actionType(row.action)" dot>{{ actionLabel(row.action) }}</AppStatusTag>
        </template>
        <template #cell-operator="{ row }">
          <div class="mp-cell-main">{{ row.operator || '—' }}</div>
          <div class="mp-cell-sub" v-if="row.roleName">{{ row.roleName }}</div>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学期切换记录（/admin/academic-affairs/terms/switch-log）：GET /academic-affairs/terms/switch-log。
 * 设计来源：existing_code——读取既有 t_affairs_audit_trail(biz_type=AA_TERM) 审计流水，
 * 覆盖 publish_term/set_current_term 两个写入口已落的 PUBLISH/SET_CURRENT 事件，
 * 按时间顺序推导每次「当前学期」切出/切入学期，不新建表、不新增写入口。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const ACTION_LABEL = { PUBLISH: '发布并设为当前', SET_CURRENT: '切换当前学期' }
const ACTION_TYPE = { PUBLISH: 'success', SET_CURRENT: 'processing' }

export default {
  name: 'AaTermSwitchLogView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'occurredAt', title: '切换时间' },
        { key: 'switch', title: '切换详情' },
        { key: 'action', title: '触发动作' },
        { key: 'operator', title: '操作人' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    actionLabel(a) { return ACTION_LABEL[a] || a || '' },
    actionType(a) { return ACTION_TYPE[a] || 'default' },
    formatTime(t) {
      return t ? String(t).replace('T', ' ').slice(0, 19) : '—'
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTermSwitchLog({
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
.aa-switch-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.aa-switch-from {
  color: var(--text-700, #4e5969);
}
.aa-switch-from--empty {
  color: var(--text-400, #86909c);
  font-style: italic;
}
.aa-switch-arrow {
  color: var(--text-400, #86909c);
}
.aa-switch-to {
  color: var(--text-900, #1f2329);
  font-weight: 600;
}
</style>
