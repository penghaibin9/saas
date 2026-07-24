<template>
  <ModulePageShell
    title="毕设批次"
    :subtitle="'共 ' + total + ' 个批次 · 一届毕业设计的组织与规则容器'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="mp-actions">
        <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
        <AppExportButton :export-fn="exportBatchesFn">导出台账</AppExportButton>
      </div>
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <!-- 空态分两种：筛选无果 ≠ 真的还没建。前者给「清空筛选」，后者给「怎么开始」。 -->
      <EmptyState
        v-else-if="!rows.length && filtered"
        title="没有符合条件的批次"
        description="当前筛选条件下没有批次。可以放宽条件，或清空筛选看全部。"
      >
        <template #actions>
          <button class="mp-btn" @click="reset">清空筛选</button>
        </template>
      </EmptyState>
      <EmptyState
        v-else-if="!rows.length"
        title="还没有毕设批次"
        description="批次是一届毕业设计的容器——学生、题目、导师、答辩、成绩都挂在批次下。建好批次并配好阶段时间轴，才能开始选题。"
      >
        <template #actions>
          <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/batches/create')">＋ 新建批次</button>
          <button class="mp-btn" @click="$router.push('/admin/help?topic=gd-card-batch-create')">怎么建批次？</button>
        </template>
      </EmptyState>
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-batch="{ row }">
          <div class="mp-cell-main">{{ row.batchName }}</div>
          <div class="mp-cell-sub">{{ row.batchNo }} · {{ row.gradeYear || '—' }} · {{ row.academicYear || '—' }}</div>
        </template>
        <template #cell-range="{ row }">
          <AppDateDisplay :value="row.startDate" /> ~ <AppDateDisplay :value="row.endDate" />
        </template>
        <template #cell-status="{ row }"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情/配置</button>
          <button v-if="editable(row)" class="mp-link" style="margin-left: var(--space-2)" @click="openEdit(row)">编辑</button>
          <button v-if="row.status === 'DRAFT'" class="mp-link" style="margin-left: var(--space-2)" @click="askState(row, 'activate')">启用</button>
          <button v-else-if="row.status === 'RUNNING'" class="mp-link" style="margin-left: var(--space-2)" @click="askState(row, 'close')">结束</button>
          <button v-else-if="row.status === 'CLOSED'" class="mp-link" style="margin-left: var(--space-2)" @click="askState(row, 'archive')">归档</button>
          <button v-if="row.status === 'DRAFT'" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askVoid(row)">作废</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
    <!-- 首次进入本模块时的 4 步说明；「已看过」存后端偏好，顶栏「?」可重看 -->
    <AppPageGuide guide-key="graduation.gd-batches" />
  </ModulePageShell>
</template>

<script>
/** 毕设批次列表（/admin/graduation/batches）：生产级只走真实后端；建/改/阶段+规则配置/状态机/作废/Excel台账导出。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton, AppPageGuide } from '@/components/common'
import { AppDateDisplay } from '@/components/common/date'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'
import { BATCH_STATUS } from '@/modules/graduation/constants/graduation-batch.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', dateStart: '', dateEnd: '' })


export default {
  name: 'GraduationBatchListView',
  components: { AppPageGuide, 
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppDateDisplay, AppExportButton
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      preferredTab: 'stages',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'batch', title: '批次 / 编号' },
        { key: 'range', title: '起止' },
        { key: 'plannedCount', title: '计划人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '250px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '批次名称 / 编号 / 届' },
        { key: 'status', label: '状态', type: 'select', options: BATCH_STATUS }
      ]
    },
    toolbarActions() { return [{ key: 'create', label: '＋ 新建批次', variant: 'primary' }] }
  },
  created() { this.applyPanel(this.$route.query.panel, true) },
  watch: {
    '$route.query.panel'(p) { this.applyPanel(p, false) }
  },
  methods: {
    editable(row) { return !['CLOSED', 'ARCHIVED', 'VOIDED'].includes(row.status) },
    /** 按左侧三级菜单的 ?panel= 切换到对应视图/动作（每个 panel 是独立 ref，点击都能导航） */
    applyPanel(panel, initial) {
      panel = panel || 'list'
      if (panel === 'create') {
        this.filters.status = ''; this.page = 1; this.load()
        this.$router.push('/admin/graduation/batches/create')
        return
      }
      if (panel === 'export') { this.filters.status = ''; this.page = 1; this.load(); this.$nextTick(() => this.triggerBatchExport()); return }
      if (panel === 'running' || panel === 'archived') {
        this.filters.status = panel === 'running' ? 'RUNNING' : 'ARCHIVED'; this.page = 1; this.load(); return
      }
      if (panel === 'stages' || panel === 'rules') {
        this.preferredTab = panel; this.filters.status = ''; this.page = 1; this.load()
        if (!initial) toast.info(panel === 'stages' ? '点某个批次「详情/配置」即可编辑阶段时间轴' : '点某个批次「详情/配置」即可编辑规则')
        return
      }
      // list（默认）
      this.preferredTab = 'stages'; this.filters.status = ''; this.page = 1; this.load()
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await graduationBatchApi.getBatches({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') this.$router.push('/admin/graduation/batches/create')
    },
    openEdit(row) {
      this.$router.push(`/admin/graduation/batches/${row.id}/edit`)
    },
    openDetail(row) {
      const tab = this.preferredTab === 'rules' ? 'rules' : 'stages'
      this.$router.push({ path: `/admin/graduation/batches/${row.id}`, query: { tab } })
    },
    askState(row, action) {
      const m = { activate: { t: '启用批次', c: '确认启用', type: 'primary' }, close: { t: '结束批次', c: '确认结束', type: 'warning' }, archive: { t: '归档批次', c: '确认归档', type: 'primary' } }[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.batchName}」执行「${m.t}」？`, type: m.type, confirmText: m.c, requireReason: false, action, row }
    },
    askVoid(row) {
      this.confirm = { visible: true, title: '作废批次', message: `确认作废「${row.batchName}」？（仅草稿可作废，不可恢复）`, type: 'danger', confirmText: '确认作废', requireReason: true, reasonLabel: '作废原因', action: 'void', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'activate') res = await graduationBatchApi.activateBatch(row.id)
        else if (action === 'close') res = await graduationBatchApi.closeBatch(row.id)
        else if (action === 'archive') res = await graduationBatchApi.archiveBatch(row.id)
        else if (action === 'void') res = await graduationBatchApi.voidBatch(row.id, reason || '')
        if (res && res.code === 0) { toast.success('已更新'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    },
    exportBatchesFn() {
      return graduationBatchApi.exportBatches({ ...this.filters })
    },
    async triggerBatchExport() {
      const res = await this.exportBatchesFn()
      if (res.code === 0) {
        const { downloadXlsxFromApi } = await import('@/utils/xlsxDownload')
        downloadXlsxFromApi(res.data, '毕设批次台账.xlsx')
        toast.success(`已导出 ${res.data.rowCount} 个批次台账`)
      } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-actions { flex-wrap: wrap; }
</style>
