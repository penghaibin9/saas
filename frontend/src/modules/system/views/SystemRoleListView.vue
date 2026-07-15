<template>
  <ModulePageShell
    title="角色权限管理"
    :subtitle="'共 ' + pagination.total + ' 个角色 · 内置角色不可作废，自定义角色作废需留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的角色" description="可调整筛选条件，或通过「新增角色 / 复制角色」创建" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-role="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.code }} · {{ row.typeLabel }}</div>
        </template>
        <template #cell-scopeName="{ row }">
          <StatusTag type="info" :label="row.scopeName" />
        </template>
        <template #cell-memberCount="{ row }">{{ row.memberCount }} 人</template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('configRolePermission') }" :title="reason('configRolePermission')" @click="openPermission(row)">配置权限</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('editRole') }" :title="reason('editRole')" @click="openEdit(row)">编辑</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('copyRole') }" :title="reason('copyRole')" @click="doCopy(row)">复制</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('exportRoleConfig') }" :title="reason('exportRoleConfig')" @click="doExport(row)">导出配置</button>
          <span v-if="row.type === 'BUILTIN'" class="mp-note" title="内置角色不允许作废（平台冻结规则）">内置</span>
          <button
            v-else-if="row.status === 'ENABLED'"
            class="mp-link rl-danger"
            :class="{ 'is-disabled': !can('deprecateRole') }"
            :title="reason('deprecateRole')"
            @click="askDeprecate(row)"
          >作废</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑角色 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑角色' : '新增角色'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">新角色默认无菜单权限，创建后请在「配置权限」中授权；角色编码创建后不可修改。</p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">{{ form.id ? '保存修改' : '创建角色' }}</AppButton>
      </template>
    </AppDrawer>

    <!-- 角色详情 -->
    <AppDrawer v-model:visible="detail.open" :title="'角色详情 · ' + (detail.data ? detail.data.name : '')">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <div class="mp-kv"><span class="mp-kv__k">角色编码</span><span class="mp-kv__v">{{ detail.data.code }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">类型 / 状态</span><span class="mp-kv__v">{{ detail.data.typeLabel }} · {{ detail.data.statusLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ detail.data.scopeName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">说明</span><span class="mp-kv__v">{{ detail.data.description || '—' }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">已授权</span><span class="mp-kv__v">菜单 {{ detail.data.menuKeys.length }} 个 · 按钮 {{ detail.data.buttonKeys.length }} 个</span></div>

        <h4 class="rl-sec">成员（{{ detail.data.members.length }}）</h4>
        <EmptyState v-if="!detail.data.members.length" title="暂无成员" description="可在用户账号管理中为用户分配该角色" />
        <div v-for="m in detail.data.members" :key="m.id" class="mp-kv">
          <span class="mp-kv__k">{{ m.name }}</span><span class="mp-kv__v">{{ m.orgName }}</span>
        </div>

        <h4 class="rl-sec">操作留痕</h4>
        <table class="mp-audit">
          <thead><tr><th>操作人</th><th>动作</th><th>影响</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(a, i) in detail.data.auditTrail" :key="i">
              <td class="is-who">{{ a.who }}</td><td>{{ a.action }}</td><td>{{ a.affected }}</td><td>{{ a.time }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </AppDrawer>

    <!-- 配置权限（菜单 / 按钮 / 数据范围） -->
    <AppDrawer v-model:visible="perm.open" :title="'配置权限 · ' + perm.name">
      <LoadingState v-if="perm.loading" />
      <template v-else>
        <h4 class="rl-sec" style="margin-top: 0">数据范围</h4>
        <select v-model="perm.scopeCode" class="rl-select">
          <option v-for="s in ctx.statusOptions.scopeTypes" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
        <p class="mp-note">数据范围决定该角色能看到哪些学生 / 账号；调整后影响所有成员，将写入审计日志并通知复核。</p>

        <h4 class="rl-sec">菜单与按钮权限</h4>
        <PermissionTreeEditor
          :tree="perm.tree"
          v-model:menu-keys="perm.menuKeys"
          v-model:button-keys="perm.buttonKeys"
        />
      </template>
      <template #footer>
        <span class="mp-note" style="margin-right: auto">保存后即时生效并留痕</span>
        <AppButton variant="ghost" @click="perm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="perm.submitting" @click="submitPermission">保存权限配置</AppButton>
      </template>
    </AppDrawer>

    <!-- 作废角色（逻辑删除） -->
    <AppConfirmDialog
      v-model:visible="confirmDeprecate"
      type="danger"
      :title="'作废角色「' + (deprecateRow ? deprecateRow.name : '') + '」？'"
      message="作废为逻辑删除：历史授权记录保留可追溯，该角色不可再分配；如有成员需先移除。"
      confirm-text="确认作废并留痕"
      require-reason
      reason-label="作废原因"
      reason-placeholder="如：临时角色到期 / 职责合并，至少 5 个字"
      :submitting="deprecateSubmitting"
      @confirm="doDeprecate"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 角色权限管理（/admin/system/roles）：
 * 新增 / 查看 / 编辑 / 复制 / 作废（逻辑删除+原因留痕）/ 配置菜单按钮权限 / 配置数据范围 / 导出角色配置。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import PermissionTreeEditor from '@/modules/system/components/PermissionTreeEditor.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '' })

export default {
  name: 'SystemRoleListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog,
    FormFields, PermissionTreeEditor
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'role', title: '角色' },
        { key: 'scopeName', title: '数据范围' },
        { key: 'memberCount', title: '成员' },
        { key: 'description', title: '说明' },
        { key: 'status', title: '状态' },
        { key: 'updatedAt', title: '最近更新' },
        { key: 'actions', title: '操作', width: '300px' }
      ],
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      detail: { open: false, loading: false, data: null },
      perm: { open: false, loading: false, id: '', name: '', tree: [], menuKeys: [], buttonKeys: [], scopeCode: 'COLLEGE', submitting: false },
      confirmDeprecate: false,
      deprecateRow: null,
      deprecateSubmitting: false
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '角色名称 / 编码' },
        { key: 'type', label: '角色类型', type: 'select', options: this.ctx.statusOptions.roleType },
        { key: 'status', label: '状态', type: 'select', options: this.ctx.statusOptions.roleStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'createRole', label: '＋ 新增角色', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '角色名称', required: true, placeholder: '如：教学质量督导' },
        { key: 'code', label: '角色编码', disabled: !!this.form.id, lockNote: this.form.id ? '（不可修改）' : '', placeholder: '大写字母与下划线，留空自动生成' },
        { key: 'scopeCode', label: '默认数据范围', type: 'select', options: this.ctx.statusOptions.scopeTypes },
        { key: 'description', label: '角色说明', type: 'textarea', full: true, placeholder: '该角色的职责与可见范围说明' }
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
      if (key === 'createRole') this.openEdit(null)
    },
    openEdit(row) {
      if (row && !this.can('editRole')) return
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row ? { name: row.name, code: row.code, scopeCode: row.scopeCode, description: row.description } : { name: '', code: '', scopeCode: 'COLLEGE', description: '' },
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
        ? await systemApi.updateRole(this.form.id, this.form.value)
        : await systemApi.createRole(this.form.value)
      this.form.submitting = false
      if (res.code === 0) {
        toast.success((this.form.id ? '角色已更新' : '角色已创建') + '，已写入审计日志')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openDetail(row) {
      this.detail = { open: true, loading: true, data: null }
      const res = await systemApi.getRoleDetail(row.id)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
      else {
        toast.error(res.message)
        this.detail.open = false
      }
    },
    async openPermission(row) {
      if (!this.can('configRolePermission')) return
      if (row.type === 'BUILTIN') {
        toast.error('预设角色由平台模板维护；请复制为自定义角色后再裁剪权限')
        return
      }
      this.perm = { open: true, loading: true, id: row.id, name: row.name, tree: [], menuKeys: [], buttonKeys: [], scopeCode: row.scopeCode, submitting: false }
      const [treeRes, detailRes] = await Promise.all([systemApi.getPermissionTree(), systemApi.getRoleDetail(row.id)])
      this.perm.loading = false
      if (treeRes.code === 0) this.perm.tree = treeRes.data
      if (detailRes.code === 0) {
        this.perm.menuKeys = detailRes.data.menuKeys || []
        this.perm.buttonKeys = detailRes.data.buttonKeys || []
        this.perm.scopeCode = detailRes.data.scopeCode || row.scopeCode
      }
    },
    async submitPermission() {
      this.perm.submitting = true
      const res = await systemApi.saveRolePermissions(this.perm.id, {
        menuKeys: this.perm.menuKeys,
        buttonKeys: this.perm.buttonKeys,
        scopeCode: this.perm.scopeCode
      })
      this.perm.submitting = false
      if (res.code === 0) {
        toast.success('权限配置已保存并留痕（变更已通知复核人）')
        this.perm.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doCopy(row) {
      if (!this.can('copyRole')) return
      const res = await systemApi.copyRole(row.id)
      if (res.code === 0) {
        toast.success('已复制为「' + res.data.name + '」（成员不复制），已留痕')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doExport(row) {
      if (!this.can('exportRoleConfig')) return
      const res = await systemApi.exportRoleConfig(row.id)
      if (res.code === 0) toast.success('导出任务已创建：' + res.data.fileName + '（含水印），已留痕')
      else toast.error(res.message)
    },
    askDeprecate(row) {
      if (!this.can('deprecateRole')) return
      this.deprecateRow = row
      this.confirmDeprecate = true
    },
    async doDeprecate({ reason }) {
      this.deprecateSubmitting = true
      const res = await systemApi.deprecateRole(this.deprecateRow.id, { reason })
      this.deprecateSubmitting = false
      if (res.code === 0) {
        toast.success('角色已作废（逻辑删除），原因已留痕')
        this.confirmDeprecate = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getRoles({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
.rl-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.rl-danger {
  color: var(--danger-600);
}
.rl-select {
  height: 34px;
  width: 100%;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  font: inherit;
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  background: var(--bg-card);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
