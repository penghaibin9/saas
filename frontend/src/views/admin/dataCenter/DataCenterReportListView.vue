<template>
  <ModulePageShell
    title="专题报表"
    :subtitle="'共 ' + pagination.total + ' 份报表配置 · 发布版本冻结，作废全程留痕可追溯'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <AppGlobalState
      v-if="!viewAllowed"
      state="forbidden"
      :description="viewReason"
      @back="$router.push('/admin/data-center')"
    />

    <div v-else class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="没有符合条件的报表"
        description="当前服务端查询无结果；可调整筛选条件或新增报表草稿。"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-report="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.reportNo }} · {{ row.description }}</div>
        </template>
        <template #cell-cycle="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.cycleLabel }}</div>
          <div class="mp-cell-sub">{{ row.scopeName }} · {{ row.caliberLabel }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/data-center/reports/' + row.id)">查看</button>
          <button
            v-if="pa.editReport && pa.editReport.visible"
            class="mp-link"
            :class="{ 'is-disabled': !canEditRow(row) }"
            :title="editRowReason(row)"
            style="margin-left: var(--space-2)"
            @click="openEdit(row)"
          >编辑</button>
          <button
            v-if="pa.voidReport && pa.voidReport.visible"
            class="mp-link dcrl-void"
            :class="{ 'is-disabled': !canVoidRow(row) }"
            :title="voidRowReason(row)"
            style="margin-left: var(--space-2)"
            @click="openVoid(row)"
          >作废</button>
        </template>
      </DataTable>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">审计留痕摘要</span>
          <span class="mp-note">配置变更 / 发布 / 撤回 / 作废均由服务端留痕</span>
        </div>
        <div class="mp-card__body">
          <ErrorState v-if="auditError" :description="auditError" @retry="loadAudits" />
          <LoadingState v-else-if="auditLoading" text="正在读取真实审计记录…" />
          <EmptyState
            v-else-if="!audits.length"
            title="暂无审计记录"
            description="服务端查询成功，但当前范围内尚无数据中心报表审计记录。"
          />
          <table v-else class="mp-audit">
            <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>对象</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="a in audits" :key="a.id">
                <td class="is-who">{{ a.userName }} · {{ a.roleName }}</td>
                <td>{{ a.time }}</td>
                <td>{{ a.action }}</td>
                <td>{{ a.target }}</td>
                <td>{{ a.detail }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <AppDrawer v-model:visible="form.visible" :title="form.mode === 'create' ? '新增报表配置' : '编辑报表配置'">
      <div class="mp-stack">
        <label class="dcrl-field">
          <span class="dcrl-field__label">报表名称 <i class="dcrl-required">*</i></span>
          <input v-model="form.data.name" type="text" class="dcrl-input" placeholder="例如：2026 届就业质量季度分析" />
        </label>
        <label class="dcrl-field">
          <span class="dcrl-field__label">报表分类</span>
          <select v-model="form.data.category" class="dcrl-input">
            <option v-for="c in ctx.filterOptions.reportCategories" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <label class="dcrl-field">
          <span class="dcrl-field__label">统计周期</span>
          <select v-model="form.data.cycle" class="dcrl-input">
            <option v-for="c in ctx.statusOptions.reportCycles" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <label class="dcrl-field">
          <span class="dcrl-field__label">统计口径</span>
          <select v-model="form.data.caliber" class="dcrl-input">
            <option v-for="c in ctx.filterOptions.calibers" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <label class="dcrl-field">
          <span class="dcrl-field__label">数据范围说明</span>
          <input v-model="form.data.scopeName" type="text" class="dcrl-input" placeholder="例如：全校 · 2026 届" />
        </label>
        <label class="dcrl-field">
          <span class="dcrl-field__label">报表说明</span>
          <textarea v-model="form.data.description" class="mp-textarea" placeholder="说明报表用途、指标口径与共享范围，便于审计与交接"></textarea>
        </label>
        <p v-if="form.error" class="mp-form-err">{{ form.error }}</p>
        <p class="mp-note">草稿可编辑；发布后服务端冻结指标版本，必须先撤回才可继续修改工作副本。</p>
      </div>
      <template #footer>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">
          {{ form.mode === 'create' ? '保存并创建' : '保存修改' }}
        </AppButton>
        <AppButton variant="ghost" @click="form.visible = false">取消</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="voidState.visible"
      type="danger"
      title="作废报表"
      :message="voidState.row ? '确认作废「' + voidState.row.name + '」？已发布历史版本仍永久保留，当前报表停止使用。' : ''"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请说明作废原因（如口径调整、报表重复等），将永久写入审计日志"
      :submitting="voidState.submitting"
      @confirm="onVoidConfirm"
    />
  </ModulePageShell>
</template>

<script>
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
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import { AppDrawer, AppButton } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', category: '', status: '' })
const EMPTY_FORM = () => ({
  name: '', category: 'ACADEMIC', cycle: 'MONTHLY', caliber: 'REGISTERED', scopeName: '全校', description: ''
})

export default {
  name: 'DataCenterReportListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppGlobalState, AppConfirmDialog, AppDrawer, AppButton
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      audits: [],
      auditLoading: false,
      auditError: '',
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'report', title: '报表' },
        { key: 'categoryLabel', title: '分类', width: '90px' },
        { key: 'cycle', title: '周期 / 范围 / 口径' },
        { key: 'ownerName', title: '负责人', width: '90px' },
        { key: 'updatedAt', title: '最近更新', width: '140px' },
        { key: 'status', title: '状态', width: '100px' },
        { key: 'actions', title: '操作', width: '150px' }
      ],
      form: { visible: false, mode: 'create', editingId: '', submitting: false, error: '', data: EMPTY_FORM() },
      voidState: { visible: false, row: null, submitting: false }
    }
  },
  computed: {
    pa() { return this.ctx.permissionActions },
    viewAllowed() {
      const pa = this.pa.viewReports
      return !!(pa && pa.visible && pa.allowed)
    },
    viewReason() {
      const pa = this.pa.viewReports
      return (pa && pa.reason) || '当前角色未开通专题报表模块权限'
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '报表名称 / 编号' },
        { key: 'category', label: '报表分类', type: 'select', options: this.ctx.filterOptions.reportCategories },
        { key: 'status', label: '状态', type: 'select', options: this.ctx.statusOptions.reportStatus }
      ]
    },
    toolbarActions() {
      return [{ key: 'createReport', label: '＋ 新增报表配置', variant: 'primary' }]
        .filter((a) => this.pa[a.key] && this.pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !this.pa[a.key].allowed, disabledReason: this.pa[a.key].reason }))
    }
  },
  created() {
    if (this.viewAllowed) {
      this.load()
      this.loadAudits()
    }
  },
  methods: {
    canEditRow(row) {
      const pa = this.pa.editReport
      return !!(pa && pa.visible && pa.allowed) && ['DRAFT', 'WITHDRAWN'].includes(row.status)
    },
    editRowReason(row) {
      if (row.status === 'VOIDED') return '已作废的报表不可编辑'
      if (row.status === 'PUBLISHED') return '已发布报表必须先进入详情撤回，才能修改工作副本'
      const pa = this.pa.editReport
      return pa && !pa.allowed ? pa.reason : ''
    },
    canVoidRow(row) {
      const pa = this.pa.voidReport
      return !!(pa && pa.visible && pa.allowed) && row.status !== 'VOIDED'
    },
    voidRowReason(row) {
      if (row.status === 'VOIDED') return '该报表已作废'
      const pa = this.pa.voidReport
      return pa && !pa.allowed ? pa.reason : ''
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    search() { this.pagination.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.pagination.page = 1; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getReports({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list || []
        this.pagination.total = res.data.total || 0
      } else {
        this.rows = []
        this.pagination.total = 0
        this.error = res.message
      }
      this.loading = false
    },
    async loadAudits() {
      this.auditLoading = true
      this.auditError = ''
      const res = await dataCenterApi.getAuditLogs({ limit: 6 })
      if (res.code === 0) {
        this.audits = res.data || []
      } else {
        this.audits = []
        this.auditError = res.message || '审计记录加载失败'
      }
      this.auditLoading = false
    },
    onToolbar(key) {
      if (key !== 'createReport') return
      this.form.mode = 'create'
      this.form.editingId = ''
      this.form.data = EMPTY_FORM()
      this.form.error = ''
      this.form.visible = true
    },
    openEdit(row) {
      if (!this.canEditRow(row)) return
      this.form.mode = 'edit'
      this.form.editingId = row.id
      this.form.error = ''
      this.form.data = {
        name: row.name, category: row.category, cycle: row.cycle,
        caliber: row.caliber || 'REGISTERED', scopeName: row.scopeName, description: row.description
      }
      this.form.visible = true
    },
    async submitForm() {
      const name = this.form.data.name.trim()
      if (name.length < 4) { this.form.error = '报表名称必填且不少于 4 个字'; return }
      this.form.error = ''
      this.form.submitting = true
      const payload = { ...this.form.data, name }
      const res = this.form.mode === 'create'
        ? await dataCenterApi.createReport(payload)
        : await dataCenterApi.updateReport(this.form.editingId, payload)
      this.form.submitting = false
      if (res.code === 0) {
        this.form.visible = false
        toast.success(this.form.mode === 'create' ? '报表草稿已创建并写入服务端审计' : '报表工作副本已更新并写入服务端审计')
        await Promise.all([this.load(), this.loadAudits()])
      } else {
        this.form.error = res.message
        if (res.bizCode === 'DATA_VERSION_CONFLICT') await this.load()
      }
    },
    openVoid(row) {
      if (!this.canVoidRow(row)) return
      this.voidState.row = row
      this.voidState.visible = true
    },
    async onVoidConfirm({ reason }) {
      if (!this.voidState.row) return
      this.voidState.submitting = true
      const res = await dataCenterApi.voidReport(this.voidState.row.id, { reason, version: this.voidState.row.version })
      this.voidState.submitting = false
      if (res.code === 0) {
        this.voidState.visible = false
        toast.success('报表已作废，历史发布版本与审计记录继续保留')
        await Promise.all([this.load(), this.loadAudits()])
      } else {
        toast.error(res.message)
        if (res.bizCode === 'DATA_VERSION_CONFLICT') await this.load()
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcrl-void:not(.is-disabled) { color: var(--danger-600); }
.dcrl-field { display: flex; flex-direction: column; gap: var(--space-1); }
.dcrl-field__label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.dcrl-required { color: var(--danger-600); font-style: normal; }
.dcrl-input {
  min-height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.dcrl-input:focus { border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-50); }
</style>
