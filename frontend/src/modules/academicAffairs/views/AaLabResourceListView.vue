<template>
  <ModulePageShell
    title="教学资源 · 实训室资源"
    :subtitle="'共 ' + pagination.total + ' 间实训室 · 按管理责任人负责制维护'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="can('create')" variant="primary" :disabled="saving || acting || Boolean(pendingResult)" @click="openCreate">新建实训室</AppButton>
    </template>

    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pendingResult" :disabled="saving || acting" @click="queryResult">查询办理结果</AppButton>
      <div class="aalr-filters">
        <AppTextInput v-model="filters.keyword" placeholder="实训室编号 / 名称 / 楼栋" clearable @change="search" />
        <AppSelect v-model="filters.labType" :options="typeOptions" placeholder="全部类型" @change="search" />
        <AppSelect v-model="filters.status" :options="statusOptions" placeholder="全部状态" @change="search" />
        <AppButton variant="ghost" @click="search">查询</AppButton>
        <AppButton variant="ghost" @click="reset">重置</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无实训室" description="点击右上角「新建实训室」录入第一间实训室" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="labId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-lab="{ row }">
          <div class="mp-cell-main">{{ row.labName }}</div>
          <div class="mp-cell-sub">{{ row.labCode }}<span v-if="row.buildingName"> · {{ row.buildingName }}</span></div>
        </template>
        <template #cell-labType="{ row }">
          <span :class="['aalr-tag', { 'is-pending': !isSupportedType(row.labType) }]">{{ labTypeLabel(row) }}</span>
        </template>
        <template #cell-capacity="{ row }">{{ row.capacity }} 工位</template>
        <template #cell-responsible="{ row }">{{ row.responsibleName || '未指定' }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusType(row.status)" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="can('update')" class="mp-link" :disabled="saving || acting || Boolean(pendingResult)" @click="openEdit(row)">编辑</button>
          <button v-if="can('update')" class="mp-link" :disabled="saving || acting || Boolean(pendingResult)" @click="bindingLabId=String(row.labId)">关联排课场地</button>
          <button v-if="can('update') && row.status !== 'AVAILABLE'" class="mp-link" @click="askStatus(row, 'AVAILABLE')">启用</button>
          <button v-if="can('update') && row.status !== 'DISABLED'" class="mp-link" @click="askStatus(row, 'DISABLED')">停用</button>
          <button v-if="can('update') && row.status !== 'MAINTENANCE'" class="mp-link" @click="askStatus(row, 'MAINTENANCE')">标记维修中</button>
          <button v-if="can('delete')" class="mp-link is-danger" :disabled="acting || saving || Boolean(pendingResult)" @click="askDelete(row)">删除</button>
        </template>
      </DataTable>

      <p class="mp-note">
        实训室按管理责任人负责制维护（可指定专兼职责任人）；预约选择器仅列出可用（AVAILABLE）实训室。
        删除为逻辑删除，历史预约与维修记录不受影响。
      </p>
    </div>

    <AppDrawer :visible="formVisible" :title="editingId ? '编辑实训室' : '新建实训室'" mode="modal" size="large" @close="formVisible = false">
      <div class="aalr-form">
        <AppFormItem label="实训室编号" required>
          <AppTextInput v-model="form.labCode" placeholder="如 SX-101" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="实训室名称" required>
          <AppTextInput v-model="form.labName" placeholder="如 机械加工实训室" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="所在楼栋">
          <AppTextInput v-model="form.buildingName" placeholder="选填，如独立实训楼" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="容量（工位）">
          <AppNumberInput v-model="form.capacity" :min="0" :max="1000" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="实训室类型">
          <AppSelect v-model="form.labType" :options="formTypeOptions" :disabled="saving" />
          <div v-if="form.labType && !isSupportedType(form.labType)" class="aalr-field-note">
            该历史类型不在当前正式字典中；保存前请选择受支持的类型，避免原值被误写。
          </div>
        </AppFormItem>
        <AppFormItem label="责任人（管理员）">
          <AppTextInput v-model="form.responsibleName" placeholder="选填，实训室责任人姓名" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="备注">
          <AppTextarea v-model="form.remark" placeholder="选填" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="formVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" :disabled="Boolean(pendingResult) || !can(editingId ? 'update' : 'create')" @click="submitForm">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :type="confirmType"
      :submitting="acting"
      @confirm="onConfirm"
    ><AppInlineAlert v-if="actionError" type="danger" :description="actionError" /></AppConfirmDialog>
  <LabScheduleResourceBinding v-if="bindingLabId" :key="bindingLabId" :lab-id="bindingLabId" :ctx="ctx" @close="bindingLabId=null" @saved="load()" />
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 实训室资源（/admin/academic-affairs/resources/labs）：结构对齐教室字典，另加责任人字段。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsLabApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import LabScheduleResourceBinding from '../components/parallel-a/LabScheduleResourceBinding.vue'
import { isDeniedResult, isConflictResult, isMissingResult } from '../components/parallel-a/resultState'

const EMPTY_FILTERS = () => ({ keyword: '', labType: '', status: '' })
const EMPTY_FORM = () => ({ labCode: '', labName: '', buildingName: '', capacity: 0, labType: 'SKILL', responsibleName: '', remark: '' })

export default {
  name: 'AaLabResourceListView',
  props: { ctx: { type: Object, required: true } },
  components: { AaOperationReceipt, LabScheduleResourceBinding,
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem,
    AppConfirmDialog, AppInlineAlert
  },
  data() {
    return {
      bindingLabId: null, revision: 0, disposed: false, acting: false, actionError: '', receipt: null, pendingResult: null,
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'lab', title: '实训室' },
        { key: 'labType', title: '类型' },
        { key: 'capacity', title: '容量' },
        { key: 'responsible', title: '责任人' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作' }
      ],
      typeOptions: [
        { label: '全部类型', value: '' },
        { label: '技能实训室', value: 'SKILL' },
        { label: '计算机实训室', value: 'COMPUTER' },
        { label: '机械实训室', value: 'MECHANICAL' },
        { label: '电气实训室', value: 'ELECTRICAL' },
        { label: '其他', value: 'OTHER' }
      ],
      statusOptions: [
        { label: '全部状态', value: '' },
        { label: '可用', value: 'AVAILABLE' },
        { label: '停用', value: 'DISABLED' },
        { label: '维修中', value: 'MAINTENANCE' }
      ],
      formVisible: false,
      editingId: '',
      form: EMPTY_FORM(),
      saving: false,
      formError: '',
      confirmVisible: false,
      confirmTitle: '',
      confirmMessage: '',
      confirmType: 'primary',
      pendingAction: null
    }
  },
  computed: {
    formTypeOptions() {
      const options = this.typeOptions.slice(1)
      if (!this.form.labType || this.isSupportedType(this.form.labType)) return options
      return [{ label: `历史类型待核对（${this.form.labType}）`, value: this.form.labType, disabled: true }, ...options]
    }
  },
  created() { this.load() },
  watch: { ctx() { this.clearPrivate(); this.load() } },
  beforeUnmount() { this.disposed = true; this.revision++ },
  methods: {
    isSupportedType(value) { return this.typeOptions.slice(1).some(option => option.value === value) },
    labTypeLabel(row) {
      const option = this.typeOptions.find(item => item.value === row.labType)
      return option?.label || (row.labType ? `历史类型待核对（${row.labType}）` : '类型待核对')
    },
    statusType(s) {
      return s === 'AVAILABLE' ? 'success' : s === 'MAINTENANCE' ? 'warning' : 'default'
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
      const revision = ++this.revision, context = this.ctx
      const current = () => !this.disposed && revision === this.revision && context === this.ctx
      this.loading = true; this.error = ''; this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsLabApi.list({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (!current()) return
        if (res.code !== 0) throw res
        if (!Array.isArray(res.data?.items)) throw new Error('资源列表未完整返回。')
        this.rows = res.data.items; this.pagination.total = res.data.total
      } catch (e) { if (current()) this.failure(e, 'error') }
      finally { if (current()) this.loading = false }
    },
    openCreate() {
      if (!this.can('create') || this.saving || this.acting || this.pendingResult) return
      this.editingId = ''
      this.form = EMPTY_FORM()
      this.formError = ''
      this.formVisible = true
    },
    openEdit(row) {
      if (!this.can('update') || this.saving || this.acting || this.pendingResult) return
      this.editingId = row.labId
      this.form = {
        labCode: row.labCode, labName: row.labName, buildingName: row.buildingName,
        capacity: row.capacity, labType: row.labType, responsibleName: row.responsibleName, remark: row.remark
      }
      this.formError = ''
      this.formVisible = true
    },
    async submitForm() {
      if (this.saving || this.acting || this.pendingResult || !this.can(this.editingId ? 'update' : 'create')) return
      if (!this.form.labCode?.trim() || !this.form.labName?.trim()) { this.formError = '编号和名称均必填'; return }
      if (!this.isSupportedType(this.form.labType)) { this.formError = '请选择当前正式字典支持的实训室类型'; return }
      const body = Object.fromEntries(Object.entries(this.form).map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value]))
      if (body.ownerKind === 'NONE') body.ownerId = ''
      const context = this.ctx; this.saving = true; this.formError = ''
      await this.execute(() => this.editingId ? academicAffairsLabApi.update(this.editingId, body) : academicAffairsLabApi.create(body), this.editingId, body, 'formError')
      if (!this.disposed && context === this.ctx) this.saving = false
    },
    askStatus(row, target) {
      if (!this.can('update') || this.saving || this.acting || this.pendingResult) return
      const label = { AVAILABLE: '启用', DISABLED: '停用', MAINTENANCE: '标记为维修中' }[target]
      this.confirmTitle = `${label}实训室`
      this.confirmMessage = `确认将「${row.labName}」${label}？` + (target === 'MAINTENANCE' ? '本操作只修改资源状态。需要登记故障和跟进维修时，请前往「资源维修」创建工单。' : '')
      this.confirmType = target === 'AVAILABLE' ? 'primary' : 'warning'
      this.pendingAction = { kind: 'status', id: row.labId, target }
      this.actionError = ''; this.confirmVisible = true
    },
    askDelete(row) {
      if (!this.can('delete') || this.saving || this.acting || this.pendingResult) return
      this.confirmTitle = '删除实训室'
      this.confirmMessage = `确认删除「${row.labName}」？删除为逻辑删除，历史记录不受影响。`
      this.confirmType = 'danger'
      this.pendingAction = { kind: 'delete', id: row.labId }
      this.actionError = ''; this.confirmVisible = true
    },
    async onConfirm() {
      const action = this.pendingAction
      if (!action || this.acting || this.saving || this.pendingResult || !this.can(action.kind === 'delete' ? 'delete' : 'update')) return
      const context = this.ctx; this.acting = true; this.actionError = ''
      await this.execute(() => action.kind === 'status' ? academicAffairsLabApi.setStatus(action.id, action.target) : academicAffairsLabApi.remove(action.id), action.id, action.kind === 'status' ? { status: action.target } : { deleted: true }, 'actionError')
      if (!this.disposed && context === this.ctx) this.acting = false
    },
    can(action) { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.lab.' + action) },
    clearPrivate() { this.revision++; this.rows = []; this.pagination.total = 0; this.form = EMPTY_FORM(); this.formVisible = false; this.confirmVisible = false; this.pendingAction = null; this.pendingResult = null; this.receipt = null; this.saving = false; this.acting = false },
    failure(e, field) {
      if (isDeniedResult(e)) { this.clearPrivate(); this.loading = false; this.error = (e.message || '无权访问') + '；已清除旧资源内容。'; return }
      this[field] = (isConflictResult(e) ? '事实已变化，保留填写内容，请重新核对。' : '') + (e?.message || '读取失败，请重试。')
      if (isConflictResult(e)) this.receipt = { title: '办理回执', status: '事实已变化', pending: true, next: this[field] }
    },
    async execute(command, id, expected, field) {
      const context = this.ctx, current = () => !this.disposed && context === this.ctx
      try {
        if (id) {
          const before = await academicAffairsLabApi.get(id); if (!current()) return
          if (before.code !== 0) throw before
          if (String(before.data?.labId) !== String(id)) throw new Error('资源身份不一致，尚未提交。')
        }
        this.pendingResult = { id, expected, accepted: false }
        this.receipt = { title: '办理回执', object: '实训室 #' + (id || '待取得编号'), status: '结果待确认', pending: true, next: '正在读取正式资源资料，请勿重复提交。' }
        const res = await command(); if (!current()) return
        if (res.code !== 0) { if (isDeniedResult(res) || isConflictResult(res) || String(res.code || '').startsWith('400')) this.pendingResult = null; throw res }
        this.pendingResult.id = res.data?.labId || id
        this.pendingResult.accepted = !expected.deleted || res.data?.deleted === true
        this.formVisible = false; this.confirmVisible = false
        await this.readResult(current)
      } catch (e) {
        if (!current()) return
        this.failure(e, field)
        if (this.pendingResult && !isDeniedResult(e) && !isConflictResult(e)) { try { await this.readResult(current) } catch (readError) { if (current()) this.failure(readError, field) } }
      }
    },
    async readResult(current) {
      const pending = this.pendingResult
      if (!pending?.id) { this.receipt = { ...this.receipt, next: '未取得正式资源编号，请查询目录核对本次结果，不会自动再次创建。' }; await this.load(); return }
      const res = await academicAffairsLabApi.get(pending.id); if (!current()) return
      if (isDeniedResult(res)) throw res
      const missing = isMissingResult(res)
      const confirmed = pending.expected.deleted ? pending.accepted && missing : res.code === 0 && String(res.data?.labId) === String(pending.id) && Object.entries(pending.expected).every(([key, value]) => String(res.data[key] ?? '') === String(value ?? ''))
      if (!missing && res.code !== 0) throw res
      this.receipt = { title: '办理回执', object: '实训室 #' + pending.id, status: confirmed ? pending.expected.deleted ? '已从目录移除' : res.data.statusLabel || res.data.status : '结果待确认', pending: !confirmed, time: res.data?.updatedAt, next: confirmed ? '已重新读取正式目录。相关预约、设备与维修记录请在对应工作区核对。' : '尚未读到与本次操作一致的正式结果，请继续查询。' }
      if (confirmed) { this.pendingResult = null; this.pendingAction = null }
      await this.load()
    },
    async queryResult() {
      if (!this.pendingResult || this.saving || this.acting) return
      const context = this.ctx, current = () => !this.disposed && context === this.ctx
      this.acting = true
      try { await this.readResult(current) } catch (e) { if (current()) this.failure(e, 'error') } finally { if (current()) this.acting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aalr-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}
.aalr-filters > * {
  min-width: 140px;
}
.aalr-filters > .app-button {
  min-width: auto;
}
.aalr-tag {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
}
.aalr-tag.is-pending {
  color: var(--warning-700, #b45309);
  background: var(--warning-50, #fff7ed);
}
.aalr-field-note {
  margin-top: var(--space-1);
  color: var(--warning-700, #b45309);
  font-size: var(--font-size-xs);
}
.aalr-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.mp-link.is-danger {
  color: var(--danger-500);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
