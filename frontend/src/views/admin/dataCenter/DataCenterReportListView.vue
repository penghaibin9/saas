<template>
  <ModulePageShell
    title="专题报表"
    :subtitle="'共 ' + pagination.total + ' 份报表配置 · 作废为逻辑删除，全程留痕可追溯'"
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
        description="可调整筛选条件，或新增一份报表配置"
      />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-report="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.id.toUpperCase() }} · {{ row.description }}</div>
        </template>
        <template #cell-cycle="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.cycleLabel }}</div>
          <div class="mp-cell-sub">{{ row.scopeName }}</div>
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
          >
            编辑
          </button>
          <button
            v-if="pa.voidReport && pa.voidReport.visible"
            class="mp-link dcrl-void"
            :class="{ 'is-disabled': !canVoidRow(row) }"
            :title="voidRowReason(row)"
            style="margin-left: var(--space-2)"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">审计留痕摘要（最近 {{ audits.length }} 条）</span>
          <span class="mp-note">导出 / 配置变更 / 作废等敏感操作均自动留痕</span>
        </div>
        <div class="mp-card__body">
          <table class="mp-audit">
            <thead>
              <tr><th>操作人</th><th>时间</th><th>动作</th><th>对象</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in audits" :key="a.id">
                <td class="is-who">{{ a.userName }} · {{ a.roleName }}</td>
                <td>{{ a.time }}</td>
                <td>{{ a.action }}</td>
                <td>{{ a.target }}</td>
                <td>{{ a.detail }}</td>
              </tr>
              <tr v-if="!audits.length">
                <td colspan="5" class="mp-note">暂无审计记录</td>
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
          <span class="dcrl-field__label">数据范围说明</span>
          <input v-model="form.data.scopeName" type="text" class="dcrl-input" placeholder="例如：全校 · 2026 届" />
        </label>
        <label class="dcrl-field">
          <span class="dcrl-field__label">报表说明</span>
          <textarea v-model="form.data.description" class="mp-textarea" placeholder="说明报表用途、指标口径与共享范围，便于审计与交接"></textarea>
        </label>
        <p v-if="form.error" class="mp-form-err">{{ form.error }}</p>
        <p class="mp-note">保存后生成配置版本并写入审计日志；新报表默认为「草稿」状态，发布需具备报表发布权限的角色操作。</p>
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
      :message="voidState.row ? '确认作废「' + voidState.row.name + '」？作废后停止数据更新并对订阅方隐藏，历史数据与审计记录仍保留可追溯。' : ''"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请说明作废原因（如口径调整、报表重复等），将永久写入审计日志"
      :submitting="voidState.submitting"
      @confirm="onVoidConfirm"
    />

    <AppConfirmDialog
      v-model:visible="exportVisible"
      type="primary"
      title="导出报表清单"
      :message="ctx.exportOptions.policyNote"
      confirm-text="确认导出"
      :submitting="exporting"
      @confirm="onExportConfirm"
    >
      <div class="mp-note" style="margin-bottom: var(--space-2)">导出用途（必选，写入审计日志）</div>
      <div
        v-for="p in ctx.exportOptions.purposes"
        :key="p.value"
        class="mp-radio"
        :class="{ 'is-active': exportPurpose === p.value }"
        @click="exportPurpose = p.value"
      >
        <input type="radio" :checked="exportPurpose === p.value" style="margin-top: 3px" />
        <div>
          <div class="mp-radio__title">{{ p.label }}</div>
          <div class="mp-radio__desc">{{ p.desc }}</div>
        </div>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 专题报表列表（/admin/data-center/reports）。
 * 新增 / 编辑走 AppDrawer 表单，作废为 danger 二次确认 + 原因必填（逻辑删除）；
 * 页脚展示最近审计留痕摘要；部分演示角色无本页访问权限（渲染 forbidden 状态）。
 */
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
const EMPTY_FORM = () => ({ name: '', category: 'ACADEMIC', cycle: 'MONTHLY', scopeName: '', description: '' })

export default {
  name: 'DataCenterReportListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppGlobalState,
    AppConfirmDialog,
    AppDrawer,
    AppButton
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      audits: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'report', title: '报表' },
        { key: 'categoryLabel', title: '分类', width: '90px' },
        { key: 'cycle', title: '周期 / 范围' },
        { key: 'ownerName', title: '负责人', width: '90px' },
        { key: 'updatedAt', title: '最近更新', width: '140px' },
        { key: 'status', title: '状态', width: '100px' },
        { key: 'actions', title: '操作', width: '150px' }
      ],
      form: {
        visible: false,
        mode: 'create',
        editingId: '',
        submitting: false,
        error: '',
        data: EMPTY_FORM()
      },
      voidState: { visible: false, row: null, submitting: false },
      exportVisible: false,
      exportPurpose: 'ARCHIVE',
      exporting: false
    }
  },
  computed: {
    pa() {
      return this.ctx.permissionActions
    },
    viewAllowed() {
      const pa = this.pa.viewReports
      return !!(pa && pa.visible && pa.allowed)
    },
    viewReason() {
      const pa = this.pa.viewReports
      return (pa && pa.reason) || '当前角色未开通专题报表模块权限'
    },
    filterFields() {
      const o = this.ctx
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '报表名称 / 编号' },
        { key: 'category', label: '报表分类', type: 'select', options: o.filterOptions.reportCategories },
        { key: 'status', label: '状态', type: 'select', options: o.statusOptions.reportStatus }
      ]
    },
    toolbarActions() {
      return [
        { key: 'createReport', label: '＋ 新增报表配置', variant: 'primary' },
        { key: 'exportReport', label: '导出报表清单' }
      ]
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
      return !!(pa && pa.visible && pa.allowed) && row.status !== 'VOIDED'
    },
    editRowReason(row) {
      if (row.status === 'VOIDED') return '已作废的报表不可编辑'
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
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getReports({
        ...this.filters,
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
    async loadAudits() {
      const res = await dataCenterApi.getAuditLogs({ limit: 6 })
      if (res.code === 0) this.audits = res.data
    },
    onToolbar(key) {
      if (key === 'createReport') {
        this.form.mode = 'create'
        this.form.editingId = ''
        this.form.data = EMPTY_FORM()
        this.form.error = ''
        this.form.visible = true
      }
      if (key === 'exportReport') {
        this.exportPurpose = 'ARCHIVE'
        this.exportVisible = true
      }
    },
    openEdit(row) {
      if (!this.canEditRow(row)) return
      this.form.mode = 'edit'
      this.form.editingId = row.id
      this.form.error = ''
      this.form.data = {
        name: row.name,
        category: row.category,
        cycle: row.cycle,
        scopeName: row.scopeName,
        description: row.description
      }
      this.form.visible = true
    },
    async submitForm() {
      const name = this.form.data.name.trim()
      if (name.length < 4) {
        this.form.error = '报表名称必填且不少于 4 个字'
        return
      }
      this.form.error = ''
      this.form.submitting = true
      const payload = { ...this.form.data, name }
      const res =
        this.form.mode === 'create'
          ? await dataCenterApi.createReport(payload)
          : await dataCenterApi.updateReport(this.form.editingId, payload)
      this.form.submitting = false
      if (res.code === 0) {
        this.form.visible = false
        toast.success(this.form.mode === 'create' ? '报表配置已创建（草稿），操作已写入审计日志' : '报表配置已更新，操作已写入审计日志')
        this.load()
        this.loadAudits()
      } else {
        this.form.error = res.message
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
      const res = await dataCenterApi.voidReport(this.voidState.row.id, { reason })
      this.voidState.submitting = false
      if (res.code === 0) {
        this.voidState.visible = false
        toast.success('报表已作废：数据停止更新，作废原因已写入审计日志')
        this.load()
        this.loadAudits()
      } else {
        toast.error(res.message)
      }
    },
    async onExportConfirm() {
      this.exporting = true
      const res = await dataCenterApi.exportData({ scope: 'REPORT', purpose: this.exportPurpose })
      this.exporting = false
      if (res.code === 0) {
        this.exportVisible = false
        toast.success('导出任务 ' + res.data.taskId + ' 已登记并写入审计日志（演示态，暂未生成实际文件）')
        this.loadAudits()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcrl-void:not(.is-disabled) {
  color: var(--danger-600);
}
.dcrl-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.dcrl-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dcrl-required {
  color: var(--danger-600);
  font-style: normal;
}
.dcrl-input {
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
  transition: border-color var(--motion-fast) var(--ease-standard);
}
.dcrl-input:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
</style>
