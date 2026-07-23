<template>
  <ModulePageShell
    title="数据范围管理"
    subtitle="数据范围独立于角色配置：全校 / 学院 / 专业 / 班级 / 本人 / 指导关系 / 企业授权 / 临时授权"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="load" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的规则" description="可调整筛选条件或新增数据范围规则" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id">
        <template #cell-rule="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.scopeCode }}</div>
        </template>
        <template #cell-scopeLabel="{ row }">
          <StatusTag type="info" :label="row.scopeLabel" />
        </template>
        <template #cell-appliedRoles="{ row }">
          <span class="mp-cell-sub">{{ row.appliedRoles.join('、') || '未引用' }}</span>
        </template>
        <template #cell-affectedUsers="{ row }">
          <button class="mp-link" :class="{ 'is-disabled': !can('viewScopeAffected') }" :title="reason('viewScopeAffected')" @click="openAffected(row)">
            {{ row.affectedUsers }} 人
          </button>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :class="{ 'is-disabled': !can('editScopeRule') }" :title="reason('editScopeRule')" @click="openEdit(row)">编辑</button>
          <button
            v-if="row.status === 'ENABLED'"
            class="mp-link ds-danger"
            :class="{ 'is-disabled': !can('deprecateScopeRule') }"
            :title="reason('deprecateScopeRule')"
            @click="askDeprecate(row)"
          >作废</button>
          <span v-else class="mp-note">已作废</span>
        </template>
      </DataTable>

      <p class="mp-note">
        规则变更影响所有引用角色的成员可见范围，保存后写入审计日志；作废前必须先在角色配置中解除引用（影响人数为 0）。
      </p>
    </div>

    <!-- 新增 / 编辑规则 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑数据范围规则' : '新增数据范围规则'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存规则</AppButton>
      </template>
    </AppDrawer>

    <!-- 影响用户 -->
    <AppDrawer v-model:visible="affected.open" :title="'影响用户 · ' + affected.name">
      <LoadingState v-if="affected.loading" />
      <EmptyState v-else-if="!affected.list.length" title="暂无影响用户" description="该规则当前没有被任何账号的角色引用" />
      <template v-else>
        <div v-for="u in affected.list" :key="u.id" class="mp-kv">
          <span class="mp-kv__k">{{ u.name }} · {{ u.roleName || '—' }}</span>
          <span class="mp-kv__v">{{ u.orgName || u.userNo || '—' }}</span>
        </div>
        <p class="mp-note" style="margin-top: var(--space-2)">仅展示姓名与组织，联系方式等敏感字段不在此页展示。</p>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmDeprecate"
      type="danger"
      :title="'作废规则「' + (deprecateRow ? deprecateRow.name : '') + '」？'"
      message="作废为逻辑删除：历史引用记录保留可追溯；作废后该规则不可再被角色引用。"
      confirm-text="确认作废并留痕"
      require-reason
      reason-label="作废原因"
      :submitting="deprecateSubmitting"
      @confirm="doDeprecate"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 数据范围管理（/admin/system/scopes）：
 * 新增 / 编辑 / 作废（逻辑删除+原因留痕）/ 查看影响用户 / 导出规则清单。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemDataScopeView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, FormFields
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: { keyword: '', status: '' },
      columns: [
        { key: 'rule', title: '规则' },
        { key: 'scopeLabel', title: '范围类型' },
        { key: 'appliedRoles', title: '引用角色' },
        { key: 'affectedUsers', title: '影响用户' },
        { key: 'remark', title: '说明' },
        { key: 'status', title: '状态' },
        { key: 'updatedAt', title: '最近更新' },
        { key: 'actions', title: '操作', width: '140px' }
      ],
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      affected: { open: false, loading: false, name: '', list: [] },
      confirmDeprecate: false,
      deprecateRow: null,
      deprecateSubmitting: false
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '规则名称' },
        { key: 'status', label: '状态', type: 'select', options: this.ctx.statusOptions.ruleStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createScopeRule', label: '＋ 新增规则', variant: 'primary' },
        { key: 'exportScopeRules', label: '⇩ 导出规则清单' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '规则名称', required: true, placeholder: '如：本学院范围' },
        { key: 'scopeCode', label: '范围类型', type: 'select', required: true, options: this.ctx.statusOptions.scopeTypes },
        { key: 'remark', label: '规则说明', type: 'textarea', full: true, placeholder: '计算口径与边界，如「按任职学院自动计算，跨院不可见」' }
      ]
    }
  },
  created() {
    this.load()
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
    reset() {
      this.filters = { keyword: '', status: '' }
      this.load()
    },
    async onToolbar(key) {
      if (key === 'createScopeRule') this.openEdit(null)
      if (key === 'exportScopeRules') {
        const res = await systemApi.exportScopeRules()
        if (res.code === 0) toast.success('导出任务已创建：' + res.data.fileName + '（含水印），已留痕')
      }
    },
    openEdit(row) {
      const key = row ? 'editScopeRule' : 'createScopeRule'
      if (!this.can(key)) return
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row ? { name: row.name, scopeCode: row.scopeCode, remark: row.remark } : { name: '', scopeCode: '', remark: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await systemApi.saveScopeRule({ id: this.form.id || undefined, ...this.form.value })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('规则已保存并留痕')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openAffected(row) {
      if (!this.can('viewScopeAffected')) return
      this.affected = { open: true, loading: true, name: row.name, list: [] }
      const res = await systemApi.getScopeAffectedUsers(row.id)
      this.affected.loading = false
      if (res.code === 0) this.affected.list = res.data
    },
    askDeprecate(row) {
      if (!this.can('deprecateScopeRule')) return
      this.deprecateRow = row
      this.confirmDeprecate = true
    },
    async doDeprecate({ reason }) {
      this.deprecateSubmitting = true
      const res = await systemApi.deprecateScopeRule(this.deprecateRow.id, { reason })
      this.deprecateSubmitting = false
      if (res.code === 0) {
        toast.success('规则已作废（逻辑删除），原因已留痕')
        this.confirmDeprecate = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getScopeRules(this.filters)
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ds-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
