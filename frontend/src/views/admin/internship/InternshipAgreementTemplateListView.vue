<template>
  <ModulePageShell
    title="申请与协议"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无协议模板" description="可「＋ 新建模板」创建实习三方协议 / 安全责任书等模板" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}<span v-if="row.isDefault" class="at-default">默认</span></div>
          <div class="mp-cell-sub">{{ row.category || '未分类' }} · {{ row.version }}</div>
        </template>
        <template #cell-scope="{ row }">
          <span class="mp-cell-sub">{{ row.scopeSummary }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <button v-if="row.status !== 'ARCHIVED'" class="mp-link" style="margin-left: var(--space-2)" @click="openEdit(row)">编辑</button>
          <button v-if="['DRAFT', 'DISABLED'].includes(row.status)" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'ENABLE')">启用</button>
          <button v-else-if="row.status === 'ENABLED'" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'DISABLE')">停用</button>
          <button v-if="row.status === 'ENABLED' && !row.isDefault" class="mp-link" style="margin-left: var(--space-2)" @click="askDefault(row, true)">设默认</button>
          <button v-if="row.isDefault" class="mp-link" style="margin-left: var(--space-2)" @click="askDefault(row, false)">取消默认</button>
          <button v-if="row.status !== 'ARCHIVED'" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askStatus(row, 'ARCHIVE')">归档</button>
        </template>
      </DataTable>
    </div>

    <!-- 新建/编辑/详情已升级为独立页：/agreement-templates/new、/agreement-templates/:id/edit、/agreement-templates/:id -->

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 实习协议模板库（/admin/internship/agreement-templates）：筛选 / 台账导出 / 启用 / 停用 / 归档 / 设默认。
 * 新建/编辑入口跳独立页 AgreementTemplateFormView（/agreement-templates/new、/agreement-templates/:id/edit）；
 * 详情跳 AgreementTemplateDetailView（/agreement-templates/:id）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppExportButton } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { agreementTemplateApi } from '@/modules/internship/api/agreement-template.api'
import { toast } from '@/utils/toast'

const STATUS_OPTS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'ENABLED', label: '启用中' },
  { value: 'DISABLED', label: '已停用' },
  { value: 'ARCHIVED', label: '已归档' }
]
const CATEGORY_OPTS = ['三方协议', '顶岗实习协议', '安全责任书', '实习承诺书', '保密协议']
const EMPTY_FILTERS = () => ({ keyword: '', status: '', category: '' })

export default {
  name: 'InternshipAgreementTemplateListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppStatusTag, AppExportButton, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'name', title: '模板 / 类型·版本' },
        { key: 'scope', title: '适用范围' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '280px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '模板名称 / 类型' },
        { key: 'status', label: '状态', type: 'select', options: STATUS_OPTS },
        { key: 'category', label: '类型', type: 'select', options: CATEGORY_OPTS.map((c) => ({ value: c, label: c })) }
      ]
    },
    toolbarActions() {
      return [{ key: 'create', label: '＋ 新建模板', variant: 'primary' }]
    },
    pageSubtitle() {
      return `共 ${this.total} 个协议模板 · 支持适用范围 / 版本 / 默认模板 / 变量占位`
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      const res = await agreementTemplateApi.getTemplates(p)
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    exportFn() { return agreementTemplateApi.exportTemplates({ ...this.filters }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 个模板（已写审计）`) },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
    },
    openCreate() {
      this.$router.push('/admin/internship/agreement-templates/new')
    },
    openEdit(row) {
      this.$router.push(`/admin/internship/agreement-templates/${row.id}/edit`)
    },
    openDetail(row) {
      this.$router.push(`/admin/internship/agreement-templates/${row.id}`)
    },
    askStatus(row, action) {
      const map = {
        ENABLE: { t: '启用模板', c: '确认启用', type: 'primary', reason: false },
        DISABLE: { t: '停用模板', c: '确认停用', type: 'warning', reason: false },
        ARCHIVE: { t: '归档模板', c: '确认归档', type: 'danger', reason: true }
      }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.name}」执行「${m.t}」？${action === 'ARCHIVE' ? '（归档后不可编辑、不可再启用）' : ''}`, type: m.type, confirmText: m.c, requireReason: m.reason, reasonLabel: '原因', action: 'STATUS_' + action, row }
    },
    askDefault(row, on) {
      this.confirm = { visible: true, title: on ? '设为默认模板' : '取消默认', message: on ? `确认将「${row.name}」设为该类型默认协议模板？（同类型原默认会被替换）` : `确认取消「${row.name}」的默认标记？`, type: 'primary', confirmText: '确认', requireReason: false, action: on ? 'DEFAULT_ON' : 'DEFAULT_OFF', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action.startsWith('STATUS_')) res = await agreementTemplateApi.setStatus(row.id, { action: action.slice(7), reason: reason || '' })
        else if (action === 'DEFAULT_ON') res = await agreementTemplateApi.setDefault(row.id, true)
        else if (action === 'DEFAULT_OFF') res = await agreementTemplateApi.setDefault(row.id, false)
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.at-default { margin-left: var(--space-2); font-size: 11px; padding: 1px 6px; border-radius: 6px; background: var(--success-50, #ecfdf5); color: var(--success, #16a34a); }
.mp-link--danger { color: var(--danger, #dc2626); }
</style>
