<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar">
        <template #right>
          <span class="mp-note">操作均写入审计日志</span>
          <div class="su-cols">
            <button class="mp-link" @click="colsOpen = !colsOpen">▥ 列设置</button>
            <div v-if="colsOpen" class="su-cols__pop">
              <label v-for="c in columnsConfig" :key="c.key" class="su-cols__item">
                <input type="checkbox" :checked="c.visible" :disabled="c.locked" @change="toggleColumn(c, $event.target.checked)" />
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
      <EmptyState
        v-else-if="!rows.length"
        title="没有符合条件的账号"
        :description="emptyDescription"
      />
      <DataTable
        v-else
        :columns="visibleColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button class="mp-link" :class="{ 'is-disabled': !can('assignRole') }" :title="reason('assignRole')" @click="openBatchAssign">批量分配角色</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('batchDisableUsers') }" :title="reason('batchDisableUsers')" @click="confirm.batchDisable = can('batchDisableUsers')">批量停用</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('exportUsers') }" :title="reason('exportUsers')" @click="openExport('SELECTED')">导出所选</button>
        </template>
        <template #cell-user="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ maskNo(row.userNo) }}</div>
        </template>
        <template #cell-org="{ row }">{{ row.orgName }}</template>
        <template #cell-roles="{ row }">
          <span v-for="r in row.roleNames" :key="r" class="su-role">{{ r }}</span>
          <span v-if="!row.roleNames.length" class="mp-note">未分配</span>
        </template>
        <template #cell-phone="{ row }">
          <span class="mp-cell-sub">{{ maskPhone(row.phone) }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTone(row.status)" :label="row.statusLabel" dot />
        </template>
        <template #cell-lastLoginAt="{ row }">
          <span class="mp-cell-sub">{{ row.lastLoginAt || '从未登录' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('editUser') }" :title="reason('editUser')" @click="openEdit(row)">编辑</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('resetPassword') }" :title="reason('resetPassword')" @click="askResetPassword(row)">重置密码</button>
          <button
            v-if="row.status === 'DISABLED'"
            class="mp-link"
            :class="{ 'is-disabled': !can('disableUser') }"
            @click="askEnable(row)"
          >启用</button>
          <button
            v-else
            class="mp-link mp-link--danger"
            :class="{ 'is-disabled': !can('disableUser') }"
            :title="reason('disableUser')"
            @click="askDisable(row)"
          >停用</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑抽屉 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑账号' : '新增用户'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">
        新账号初始状态为「待激活」，首次登录强制修改密码；工号 / 账号创建后不可修改。
      </p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">{{ form.id ? '保存修改' : '创建账号' }}</AppButton>
      </template>
    </AppDrawer>

    <!-- 账号详情抽屉 -->
    <AppDrawer v-model:visible="detail.open" :title="'账号详情 · ' + (detail.data ? detail.data.name : '')">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <div class="mp-kv"><span class="mp-kv__k">工号 / 账号</span><span class="mp-kv__v">{{ maskNo(detail.data.userNo) }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">所属组织</span><span class="mp-kv__v">{{ detail.data.orgName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">手机号</span><span class="mp-kv__v">{{ maskPhone(detail.data.phone) }} <span class="mp-note" :title="reason('viewSensitiveFull')">（完整号码需审计授权）</span></span></div>
        <div class="mp-kv"><span class="mp-kv__k">邮箱</span><span class="mp-kv__v">{{ maskEmail(detail.data.email) }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v"><StatusTag :type="statusTone(detail.data.status)" :label="detail.data.statusLabel" dot /></span></div>
        <div class="mp-kv"><span class="mp-kv__k">账号来源</span><span class="mp-kv__v">{{ detail.data.source }}</span></div>

        <h4 class="su-sec">角色与数据范围</h4>
        <div v-for="r in detail.data.roles" :key="r.code" class="mp-kv">
          <span class="mp-kv__k">{{ r.name }}</span><span class="mp-kv__v">{{ r.scopeName }}</span>
        </div>
        <AppButton variant="secondary" :disabled="!can('assignRole')" :title="reason('assignRole')" style="margin-top: var(--space-2)" @click="openAssign(detail.data)">调整角色分配</AppButton>

        <h4 class="su-sec">最近登录</h4>
        <EmptyState v-if="!detail.data.loginHistory.length" title="暂无登录记录" description="该账号尚未登录过系统" />
        <ul v-else class="mp-timeline">
          <li v-for="(l, i) in detail.data.loginHistory" :key="i" class="mp-timeline__item" :class="l.result === 'SUCCESS' ? 'is-success' : 'is-danger'">
            <div class="mp-timeline__title">{{ l.resultLabel }} · {{ l.device }}</div>
            <div class="mp-timeline__desc">{{ l.detail || 'IP ' + l.ip }}</div>
            <div class="mp-timeline__time">{{ l.time }}</div>
          </li>
        </ul>

        <h4 class="su-sec">操作留痕</h4>
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

    <!-- 分配角色抽屉 -->
    <AppDrawer v-model:visible="assign.open" :title="assign.batch ? '批量分配角色（' + selected.length + ' 人）' : '分配角色 · ' + assign.name">
      <label v-for="r in ctx.filterOptions.roles" :key="r.value" class="su-assign">
        <input v-model="assign.roles" type="checkbox" :value="r.value" />
        <span>{{ r.label }}</span>
      </label>
      <p class="mp-note">角色对应的数据范围在「角色权限管理」中配置；变更即时生效并写入审计日志。</p>
      <template #footer>
        <AppButton variant="ghost" @click="assign.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="assign.submitting" @click="submitAssign">保存分配</AppButton>
      </template>
    </AppDrawer>

    <!-- 停用（逻辑删除）确认：原因必填留痕 -->
    <AppConfirmDialog
      v-model:visible="confirm.disable"
      type="danger"
      title="停用该账号？"
      :message="'停用后 ' + (confirm.row ? confirm.row.name : '') + ' 将无法登录，历史数据与操作记录完整保留（逻辑删除，可恢复）。'"
      confirm-text="确认停用并留痕"
      require-reason
      reason-label="停用原因"
      reason-placeholder="如：离职交接 / 长期未使用 / 安全风险，至少 5 个字"
      :submitting="confirm.submitting"
      @confirm="doDisable"
    />
    <AppConfirmDialog
      v-model:visible="confirm.batchDisable"
      type="danger"
      :title="'批量停用所选 ' + selected.length + ' 个账号？'"
      message="停用为逻辑删除，可逐个恢复；本次操作将整体写入一条审计日志。"
      confirm-text="确认批量停用"
      require-reason
      reason-label="停用原因"
      :submitting="confirm.submitting"
      @confirm="doBatchDisable"
    />
    <AppConfirmDialog
      v-model:visible="confirm.reset"
      type="warning"
      title="重置该账号密码？"
      :message="'将为 ' + (confirm.row ? confirm.row.name : '') + ' 生成一次性临时密码，本账号首次登录须强制改密。临时密码仅本次在本页显示一次，请立即转交本人。'"
      confirm-text="确认重置密码"
      :submitting="confirm.submitting"
      @confirm="doResetPassword"
    />
    <AppConfirmDialog
      v-model:visible="resetResult.visible"
      type="primary"
      title="临时密码已生成（仅本次显示）"
      :message="resetResult.name + ' 的一次性临时密码为：' + resetResult.password + '。请立即转交本人，关闭后不再显示；该账号首次登录须强制改密。'"
      confirm-text="我已记录并转交"
      cancel-text="关闭"
      @confirm="resetResult.visible = false"
    />
    <AppConfirmDialog
      v-model:visible="confirm.enable"
      type="primary"
      title="恢复启用该账号？"
      :message="(confirm.row ? confirm.row.name : '') + ' 将恢复登录能力，原角色与数据范围保持不变。'"
      confirm-text="确认启用"
      :submitting="confirm.submitting"
      @confirm="doEnable"
    />

    <ImportDialog
      v-model:visible="importOpen"
      :template="ctx.importTemplates.users"
      :run-validate="api.validateIdentityImportFile"
      :run-import="api.confirmIdentityImportBatch"
      :run-download-template="api.downloadIdentityImportTemplate"
      :run-download-errors="api.downloadIdentityImportErrors"
      @done="load"
    />
    <ExportDialog
      v-model:visible="exportOpen"
      title="导出用户账号"
      :options="ctx.exportOptions.users"
      :selected-count="selected.length"
      :data-scope-name="ctx.dataScope.scopeName"
      :run-export="api.exportUsers"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 用户账号管理（/admin/system/users）：
 * 新增 / 查看 / 编辑 / 停用启用（逻辑删除+原因留痕）/ 重置密码 / 分配角色 /
 * 师生 .xlsx 批量开户（固定菜单+预检+整批事务+错误回执）/
 * 批量导出（脱敏+水印+审计）/ 批量停用 / 高级筛选 / 列设置。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import ImportDialog from '@/modules/system/components/ImportDialog.vue'
import ExportDialog from '@/modules/system/components/ExportDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', orgId: '', role: '', status: '' })
const EMPTY_FORM = () => ({ userNo: '', name: '', orgId: '', phone: '', email: '', roles: [] })

export default {
  name: 'SystemUserListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog,
    FormFields, ImportDialog, ExportDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      api: systemApi,
      loading: true,
      error: '',
      rows: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      colsOpen: false,
      columnsConfig: this.ctx.fieldColumns.users.map((c) => ({ ...c, visible: c.defaultVisible })),
      form: { open: false, id: '', value: EMPTY_FORM(), errors: {}, submitting: false },
      detail: { open: false, loading: false, data: null },
      assign: { open: false, batch: false, id: '', name: '', roles: [], submitting: false },
      confirm: { disable: false, batchDisable: false, reset: false, enable: false, row: null, submitting: false },
      resetResult: { visible: false, name: '', password: '' },
      importOpen: false,
      exportOpen: false
    }
  },
  computed: {
    isIdentityImport() {
      return this.$route.name === 'system-identity-import'
    },
    pageTitle() {
      return this.isIdentityImport ? '导入老师和学生' : '师生账号管理'
    },
    pageSubtitle() {
      if (this.isIdentityImport) return '批量创建登录账号并绑定预设角色；其他业务中心导入不会创建账号'
      return '共 ' + this.pagination.total + ' 个账号 · 手机号 / 邮箱默认脱敏展示'
    },
    emptyDescription() {
      return this.isIdentityImport
        ? '请使用本页唯一导入入口批量创建老师或学生账号'
        : '可调整筛选条件；批量开户请前往「学生导入与账号开通」或「教师导入」菜单'
    },
    visibleColumns() {
      return this.columnsConfig.filter((c) => c.visible).map((c) => ({ key: c.key, title: c.title }))
    },
    filterFields() {
      const o = this.ctx
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 工号 / 组织' },
        { key: 'orgId', label: '所属组织', type: 'select', options: o.filterOptions.colleges },
        { key: 'role', label: '角色', type: 'select', options: o.filterOptions.roles },
        { key: 'status', label: '账号状态', type: 'select', options: o.statusOptions.userStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createUser', label: '＋ 新增', variant: 'primary' },
        { key: 'importUsers', label: '⇪ 导入老师/学生' },
        { key: 'exportUsers', label: '⇩ 批量导出' }
      ]
        .filter((a) => {
          if (a.key === 'importUsers') return this.isIdentityImport
          if (this.isIdentityImport) return false
          if (a.key === 'createUser') return !!(pa.createUser && pa.createUser.visible)
          return true
        })
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'userNo', label: '工号 / 账号', required: true, disabled: !!this.form.id, lockNote: this.form.id ? '（创建后不可修改）' : '', placeholder: '如 T2026001' },
        { key: 'name', label: '姓名', required: true },
        { key: 'phone', label: '手机号', hint: '仅用于找回密码，列表默认脱敏展示' },
        { key: 'roles', label: '初始角色', type: 'checkbox-group', full: true, options: this.ctx.filterOptions.roles, hint: '数据范围随角色配置生效；新建账号请走统一导入' }
      ]
    }
  },
  created() {
    this.load()
    const action = this.$route.query.action
    if (action === 'importUsers') {
      this.$router.replace('/admin/system/identity-import')
      return
    }
    if (this.$route.meta.openImport && this.can('importUsers')) this.importOpen = true
    if (this.$route.query.status) this.filters.status = this.$route.query.status
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
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
    },
    maskNo(v) {
      return v && v.length > 4 ? v.slice(0, 4) + '****' + v.slice(-2) : v
    },
    maskEmail(v) {
      if (!v) return '未登记'
      const [name, domain] = v.split('@')
      return name.slice(0, 2) + '***@' + domain
    },
    statusTone(s) {
      return { ACTIVE: 'success', DISABLED: 'default', LOCKED: 'danger', PENDING: 'warning' }[s] || 'default'
    },
    toggleColumn(col, checked) {
      col.visible = checked
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
    onToolbar(key) {
      if (key === 'createUser') {
        toast.error(this.reason('createUser') || '师生账号只能通过统一导入入口创建')
        return
      }
      if (key === 'importUsers') this.importOpen = true
      if (key === 'exportUsers') this.openExport('FILTERED')
    },
    openExport() {
      if (!this.can('exportUsers')) return
      this.exportOpen = true
    },
    openEdit(row) {
      if (!row) {
        toast.error(this.reason('createUser') || '师生账号只能通过统一导入入口创建')
        return
      }
      if (!this.can('editUser')) return
      this.form = {
        open: true,
        id: row.id,
        value: { userNo: row.userNo, name: row.name, phone: row.phone, roles: [...(row.roles || [])] },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      if (!this.form.id) {
        toast.error('师生账号只能通过统一导入入口创建')
        return
      }
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await systemApi.updateUser(this.form.id, this.form.value)
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('账号已更新，已写入审计日志')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openDetail(row) {
      this.detail = { open: true, loading: true, data: null }
      const res = await systemApi.getUserDetail(row.id)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
      else {
        toast.error(res.message)
        this.detail.open = false
      }
    },
    openAssign(user) {
      if (!this.can('assignRole')) return
      this.assign = { open: true, batch: false, id: user.id, name: user.name, roles: (user.roles || []).map((r) => r.code || r), submitting: false }
    },
    openBatchAssign() {
      if (!this.can('assignRole') || !this.selected.length) return
      this.assign = { open: true, batch: true, id: '', name: '', roles: [], submitting: false }
    },
    async submitAssign() {
      this.assign.submitting = true
      if (this.assign.batch) {
        for (const id of this.selected) await systemApi.assignUserRoles(id, this.assign.roles)
        toast.success('已为 ' + this.selected.length + ' 个账号调整角色，均已留痕')
        this.selected = []
      } else {
        const res = await systemApi.assignUserRoles(this.assign.id, this.assign.roles)
        if (res.code === 0) toast.success('角色分配已更新，已写入审计日志')
        else toast.error(res.message)
        if (this.detail.open) this.openDetail({ id: this.assign.id })
      }
      this.assign.submitting = false
      this.assign.open = false
      this.load()
    },
    askDisable(row) {
      if (!this.can('disableUser')) return
      this.confirm.row = row
      this.confirm.disable = true
    },
    askEnable(row) {
      if (!this.can('disableUser')) return
      this.confirm.row = row
      this.confirm.enable = true
    },
    askResetPassword(row) {
      if (!this.can('resetPassword')) return
      this.confirm.row = row
      this.confirm.reset = true
    },
    async doDisable({ reason }) {
      this.confirm.submitting = true
      const res = await systemApi.setUserStatus(this.confirm.row.id, { action: 'DISABLE', reason })
      this.confirm.submitting = false
      if (res.code === 0) {
        toast.success('账号已停用（逻辑删除），原因已留痕')
        this.confirm.disable = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doEnable() {
      this.confirm.submitting = true
      const action = this.confirm.row.status === 'LOCKED' ? 'UNLOCK' : 'ENABLE'
      const res = await systemApi.setUserStatus(this.confirm.row.id, { action })
      this.confirm.submitting = false
      if (res.code === 0) {
        toast.success('账号已恢复启用，已留痕')
        this.confirm.enable = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doResetPassword() {
      const name = this.confirm.row ? this.confirm.row.name : ''
      this.confirm.submitting = true
      const res = await systemApi.resetUserPassword(this.confirm.row.id)
      this.confirm.submitting = false
      if (res.code === 0) {
        this.confirm.reset = false
        // 临时密码仅本次随响应返回，用持久弹窗展示给管理员转交（不用一闪而过的 toast，也不谎称短信下发）
        this.resetResult = { visible: true, name, password: res.data.tempPassword || '' }
      } else {
        toast.error(res.message)
      }
    },
    async doBatchDisable({ reason }) {
      this.confirm.submitting = true
      const res = await systemApi.batchDisableUsers(this.selected, { reason })
      this.confirm.submitting = false
      if (res.code === 0) {
        toast.success('已批量停用 ' + res.data.count + ' 个账号，原因已留痕')
        this.confirm.batchDisable = false
        this.selected = []
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getUsers({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
.su-role {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
  margin: 1px var(--space-1) 1px 0;
  white-space: nowrap;
}
.su-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.su-assign {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border-light);
  font-size: var(--font-size-sm);
}
.su-cols {
  position: relative;
}
.su-cols__pop {
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
.su-cols__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  padding: var(--space-1) 0;
  white-space: nowrap;
}
.mp-link--danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
