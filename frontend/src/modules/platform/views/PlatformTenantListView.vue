<template>
  <ModulePageShell
    title="租户 / 学校管理"
    :subtitle="'共 ' + pagination.total + ' 个租户 · 联系人电话默认脱敏'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar">
        <template #right>
          <div class="pt-cols">
            <button class="mp-link" @click="colsOpen = !colsOpen">▥ 列设置</button>
            <div v-if="colsOpen" class="pt-cols__pop">
              <label v-for="c in columnsConfig" :key="c.key" class="pt-cols__item">
                <input type="checkbox" :checked="c.visible" :disabled="c.locked" @change="c.visible = $event.target.checked" />
                {{ c.title }}<span v-if="c.locked" class="mp-note">（固定）</span>
              </label>
            </div>
          </div>
        </template>
      </ModuleToolbar>
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的租户" description="可调整筛选条件，或通过「新增租户 / 批量导入」开通新学校" />
      <DataTable
        v-else
        :columns="visibleColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        row-clickable
        :pagination="pagination"
        @row-click="(row) => $router.push('/admin/platform/tenants/' + row.id)"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button class="mp-link" :class="{ 'is-disabled': !can('batchRemindRenew') }" :title="reason('batchRemindRenew')" @click="doBatchRemind">批量续费提醒</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('exportTenants') }" :title="reason('exportTenants')" @click="exportOpen = can('exportTenants')">导出所选</button>
        </template>
        <template #cell-tenant="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.code }} · 联系人 {{ row.contactName || '—' }} {{ maskPhone(row.contactPhone) }}</div>
        </template>
        <template #cell-region="{ row }">{{ row.regionLabel }}</template>
        <template #cell-packageName="{ row }">
          <div class="mp-cell-main">{{ row.packageName }}</div>
          <div class="mp-cell-sub">{{ row.moduleCount }} 个模块</div>
        </template>
        <template #cell-usage="{ row }">
          <span :class="{ 'pt-over': row.studentLimit && row.studentCount / row.studentLimit > 0.9 }">
            {{ row.studentCount.toLocaleString() }} / {{ row.studentLimit ? row.studentLimit.toLocaleString() : '—' }}
          </span>
        </template>
        <template #cell-expireAt="{ row }">{{ row.expireAt }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTone(row.status)" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click.stop="$router.push('/admin/platform/tenants/' + row.id)">查看</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('editTenant') }" :title="reason('editTenant')" @click.stop="openEdit(row)">编辑</button>
          <button
            v-if="row.status !== 'SUSPENDED'"
            class="mp-link pt-danger"
            :class="{ 'is-disabled': !can('disableTenant') }"
            :title="reason('disableTenant')"
            @click.stop="askSuspend(row)"
          >停用</button>
          <button v-else class="mp-link" :class="{ 'is-disabled': !can('disableTenant') }" :title="reason('disableTenant')" @click.stop="askResume(row)">恢复</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑租户 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑租户' : '新增租户'" mode="modal" size="medium">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">
        新租户初始为「试用中」；正式开通与有效期以订单授权为准。学校品牌项在租户详情中配置。
      </p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">{{ form.id ? '保存修改' : '创建租户' }}</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmSuspend"
      type="danger"
      :title="'停用租户「' + (actionRow ? actionRow.name : '') + '」？'"
      message="停用后普通用户不可进入，管理员保留导出能力；数据完整保留（逻辑操作），恢复需双人复核。"
      confirm-text="确认停用并留痕"
      require-reason
      reason-label="停用原因"
      :submitting="confirmSubmitting"
      @confirm="doSuspend"
    />
    <AppConfirmDialog
      v-model:visible="confirmResume"
      type="primary"
      :title="'恢复租户「' + (actionRow ? actionRow.name : '') + '」？'"
      message="恢复后按原套餐授权继续服务。"
      confirm-text="确认恢复"
      :submitting="confirmSubmitting"
      @confirm="doResume"
    />

    <ImportDialog
      v-model:visible="importOpen"
      :template="ctx.importTemplates.tenants"
      :run-validate="(f) => api.importTenants({ fileName: f })"
      :run-import="(f) => api.importTenants({ fileName: f, confirm: true })"
      @done="load"
    />
    <ExportDialog
      v-model:visible="exportOpen"
      title="导出租户清单"
      :options="ctx.exportOptions.tenants"
      :selected-count="selected.length"
      :data-scope-name="ctx.dataScope.scopeName"
      :run-export="api.exportTenants"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 租户 / 学校管理（/admin/platform/tenants）：
 * 新增 / 查看（详情页）/ 编辑 / 停用恢复（原因留痕）/ 批量导入导出 / 批量续费提醒 / 高级筛选 / 列设置。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/platform/components/FormFields.vue'
import ImportDialog from '@/modules/platform/components/ImportDialog.vue'
import ExportDialog from '@/modules/platform/components/ExportDialog.vue'
import { platformApi } from '@/modules/platform/api/platform.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', region: '', packageId: '', status: '', csOwner: '' })

export default {
  name: 'PlatformTenantListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog,
    FormFields, ImportDialog, ExportDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      api: platformApi,
      loading: true,
      error: '',
      rows: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      colsOpen: false,
      columnsConfig: this.ctx.fieldColumns.tenants.map((c) => ({ ...c, visible: c.defaultVisible })),
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      confirmSuspend: false,
      confirmResume: false,
      actionRow: null,
      confirmSubmitting: false,
      importOpen: false,
      exportOpen: false
    }
  },
  computed: {
    visibleColumns() {
      return this.columnsConfig.filter((c) => c.visible).map((c) => ({ key: c.key, title: c.title }))
    },
    filterFields() {
      const o = this.ctx
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学校名称 / 租户编码' },
        { key: 'region', label: '区域', type: 'select', options: o.filterOptions.regions },
        { key: 'packageId', label: '套餐', type: 'select', options: o.filterOptions.packages },
        { key: 'status', label: '租户状态', type: 'select', options: o.statusOptions.tenantStatus },
        { key: 'csOwner', label: '客户成功', type: 'select', options: o.filterOptions.csOwners }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createTenant', label: '＋ 新增租户', variant: 'primary' },
        { key: 'importTenants', label: '⇪ 批量导入' },
        { key: 'exportTenants', label: '⇩ 批量导出' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '学校名称', required: true, disabled: !!this.form.id, lockNote: this.form.id ? '（开通后由平台管理员变更）' : '' },
        { key: 'code', label: '租户编码', required: true, disabled: !!this.form.id, lockNote: this.form.id ? '（不可修改）' : '', placeholder: '如 JC-GC' },
        { key: 'region', label: '区域', type: 'select', required: true, options: this.ctx.filterOptions.regions },
        { key: 'packageId', label: '套餐', type: 'select', required: !this.form.id, options: this.ctx.filterOptions.packages, disabled: !!this.form.id, lockNote: this.form.id ? '（套餐变更走订单授权）' : '' },
        { key: 'csOwner', label: '客户成功负责人', type: 'select', options: this.ctx.filterOptions.csOwners },
        { key: 'expireAt', label: '试用截止日', placeholder: 'YYYY-MM-DD' },
        { key: 'contactName', label: '联系人' },
        { key: 'contactPhone', label: '联系电话', hint: '列表与导出默认脱敏' }
      ]
    }
  },
  created() {
    this.load()
    if (this.$route.query.action === 'create') this.openEdit(null)
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    maskPhone(v) {
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : ''
    },
    statusTone(s) {
      return { ACTIVE: 'success', TRIAL: 'processing', EXPIRING: 'warning', EXPIRED: 'danger', SUSPENDED: 'default' }[s] || 'default'
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
      this.load()
    },
    onToolbar(key) {
      if (key === 'createTenant') this.openEdit(null)
      if (key === 'importTenants') this.importOpen = true
      if (key === 'exportTenants') this.exportOpen = true
    },
    openEdit(row) {
      if (row && !this.can('editTenant')) return
      if (!row && !this.can('createTenant')) return
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row
          ? { name: row.name, code: row.code, region: row.region, packageId: row.packageId, csOwner: row.csOwner, expireAt: row.expireAt, contactName: row.contactName, contactPhone: row.contactPhone }
          : { name: '', code: '', region: '', packageId: '', csOwner: '', expireAt: '', contactName: '', contactPhone: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = this.form.id
        ? await platformApi.updateTenant(this.form.id, this.form.value)
        : await platformApi.createTenant(this.form.value)
      this.form.submitting = false
      if (res.code === 0) {
        toast.success((this.form.id ? '租户已更新' : '租户已创建（试用中）') + '，已写入审计日志')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    askSuspend(row) {
      if (!this.can('disableTenant')) return
      this.actionRow = row
      this.confirmSuspend = true
    },
    askResume(row) {
      if (!this.can('disableTenant')) return
      this.actionRow = row
      this.confirmResume = true
    },
    async doSuspend({ reason }) {
      this.confirmSubmitting = true
      const res = await platformApi.setTenantStatus(this.actionRow.id, { action: 'SUSPEND', reason })
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success('租户已停用（数据保留），原因已留痕')
        this.confirmSuspend = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doResume() {
      this.confirmSubmitting = true
      const res = await platformApi.setTenantStatus(this.actionRow.id, { action: 'RESUME' })
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success('租户已恢复，已留痕')
        this.confirmResume = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doBatchRemind() {
      if (!this.can('batchRemindRenew') || !this.selected.length) return
      const res = await platformApi.batchRemindRenew(this.selected)
      if (res.code === 0) {
        toast.success('已向 ' + res.data.count + ' 个租户发送续费提醒，已留痕')
        this.selected = []
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformApi.getTenants({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
.pt-danger {
  color: var(--danger-600);
}
.pt-over {
  color: var(--warning-600);
  font-weight: var(--font-weight-medium);
}
.pt-cols {
  position: relative;
}
.pt-cols__pop {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  z-index: var(--z-sticky);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: var(--space-2) var(--space-3);
  min-width: 200px;
}
.pt-cols__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  padding: var(--space-1) 0;
  white-space: nowrap;
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
