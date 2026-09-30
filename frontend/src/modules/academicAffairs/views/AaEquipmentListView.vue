<template>
  <ModulePageShell
    title="教学资源 · 设备资源"
    :subtitle="'共 ' + pagination.total + ' 项设备台账'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="can('create')" variant="primary" :disabled="saving || acting || Boolean(pendingResult)" @click="openCreate">新建设备</AppButton>
    </template>

    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pendingResult" :disabled="saving || acting" @click="queryResult">查询办理结果</AppButton>
      <div class="aaeq-filters">
        <AppTextInput v-model="filters.keyword" placeholder="资产编号 / 设备名称 / 规格型号" clearable @change="search" />
        <AppSelect v-model="filters.ownerKind" :options="ownerOptions" placeholder="全部位置类型" @change="search" />
        <AppSelect v-model="filters.status" :options="statusOptions" placeholder="全部状态" @change="search" />
        <AppButton variant="ghost" @click="search">查询</AppButton>
        <AppButton variant="ghost" @click="reset">重置</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无设备" description="点击右上角「新建设备」录入第一项设备" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="equipmentId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-equipment="{ row }">
          <div class="mp-cell-main">{{ row.equipmentName }}</div>
          <div class="mp-cell-sub">{{ row.equipmentCode }}<span v-if="row.specModel"> · {{ row.specModel }}</span></div>
        </template>
        <template #cell-owner="{ row }">{{ row.ownerLabel || '未分配（中心库存）' }}</template>
        <template #cell-quantity="{ row }">{{ row.quantity }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusType(row.status)" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="can('update')" class="mp-link" :disabled="saving || acting || Boolean(pendingResult)" @click="openEdit(row)">编辑</button>
          <button v-if="can('update') && row.status !== 'IN_USE'" class="mp-link" @click="askStatus(row, 'IN_USE')">在用</button>
          <button v-if="can('update') && row.status !== 'IDLE'" class="mp-link" @click="askStatus(row, 'IDLE')">闲置</button>
          <button v-if="can('update') && row.status !== 'MAINTENANCE'" class="mp-link" @click="askStatus(row, 'MAINTENANCE')">标记维修中</button>
          <button v-if="can('update') && row.status !== 'SCRAPPED'" class="mp-link is-danger" @click="askStatus(row, 'SCRAPPED')">报废</button>
          <button v-if="can('delete')" class="mp-link is-danger" :disabled="acting || saving || Boolean(pendingResult)" @click="askDelete(row)">删除</button>
        </template>
      </DataTable>

      <p class="mp-note">
        设备可归属于某教室或实训室（用于查看该场地的设备清单），也可保持"未分配"作为中心库存。
        报修请前往「资源维修」登记工单，处理完成后设备状态会自动联动恢复。
      </p>
    </div>

    <AppDrawer :visible="formVisible" :title="editingId ? '编辑设备' : '新建设备'" mode="modal" size="large" @close="formVisible = false">
      <div class="aaeq-form">
        <AppFormItem label="资产编号" required>
          <AppTextInput v-model="form.equipmentCode" placeholder="如 SB-2026-001" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="设备名称" required>
          <AppTextInput v-model="form.equipmentName" placeholder="如 数控车床" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="规格型号">
          <AppTextInput v-model="form.specModel" placeholder="选填" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="数量">
          <AppNumberInput v-model="form.quantity" :min="1" :max="9999" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="所在位置类型">
          <AppSelect v-model="form.ownerKind" :options="ownerOptions.slice(1)" :disabled="saving" @change="onOwnerKindChange" />
        </AppFormItem>
        <AppFormItem v-if="form.ownerKind !== 'NONE'" label="所在位置">
          <AppClassroomPicker
            v-if="form.ownerKind === 'CLASSROOM'"
            v-model="form.ownerId"
            placeholder="选择教室"
            :disabled="saving"
          />
          <AppLabPicker
            v-else
            v-model="form.ownerId"
            placeholder="选择实训室"
            :disabled="saving"
          />
        </AppFormItem>
        <AppFormItem label="责任人">
          <AppTextInput v-model="form.responsibleName" placeholder="选填" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="购置日期">
          <AppDatePicker v-model="form.purchaseDate" :disabled="saving" />
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
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 设备资源（/admin/academic-affairs/resources/equipment）：教学/实训设备台账。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert, AppDatePicker, AppClassroomPicker, AppLabPicker } from '@/components/common'
import { academicAffairsEquipmentApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult, isMissingResult } from '../components/parallel-a/resultState'

const EMPTY_FILTERS = () => ({ keyword: '', ownerKind: '', status: '' })
const EMPTY_FORM = () => ({ equipmentCode: '', equipmentName: '', specModel: '', quantity: 1, ownerKind: 'NONE', ownerId: '', responsibleName: '', purchaseDate: '', remark: '' })

export default {
  name: 'AaEquipmentListView',
  props: { ctx: { type: Object, required: true } },
  components: { AaOperationReceipt,
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem,
    AppConfirmDialog, AppInlineAlert, AppDatePicker, AppClassroomPicker, AppLabPicker
  },
  data() {
    return {
      revision: 0, disposed: false, acting: false, actionError: '', receipt: null, pendingResult: null,
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'equipment', title: '设备' },
        { key: 'owner', title: '所在位置' },
        { key: 'quantity', title: '数量' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作' }
      ],
      ownerOptions: [
        { label: '全部位置类型', value: '' },
        { label: '教室', value: 'CLASSROOM' },
        { label: '实训室', value: 'LAB' },
        { label: '未分配', value: 'NONE' }
      ],
      statusOptions: [
        { label: '全部状态', value: '' },
        { label: '在用', value: 'IN_USE' },
        { label: '闲置', value: 'IDLE' },
        { label: '维修中', value: 'MAINTENANCE' },
        { label: '已报废', value: 'SCRAPPED' }
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
  created() { this.load() },
  watch: { ctx() { this.clearPrivate(); this.load() } },
  beforeUnmount() { this.disposed = true; this.revision++ },
  methods: {
    statusType(s) {
      if (s === 'IN_USE') return 'success'
      if (s === 'MAINTENANCE') return 'warning'
      if (s === 'SCRAPPED') return 'danger'
      return 'default'
    },
    onOwnerKindChange() {
      this.form.ownerId = ''
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
        const res = await academicAffairsEquipmentApi.list({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
      this.editingId = row.equipmentId
      this.form = {
        equipmentCode: row.equipmentCode, equipmentName: row.equipmentName, specModel: row.specModel,
        quantity: row.quantity, ownerKind: row.ownerKind, ownerId: row.ownerId,
        responsibleName: row.responsibleName, purchaseDate: row.purchaseDate, remark: row.remark
      }
      this.formError = ''
      this.formVisible = true
    },
    async submitForm() {
      if (this.saving || this.acting || this.pendingResult || !this.can(this.editingId ? 'update' : 'create')) return
      if (!this.form.equipmentCode?.trim() || !this.form.equipmentName?.trim()) { this.formError = '编号和名称均必填'; return }
      const body = Object.fromEntries(Object.entries(this.form).map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value]))
      if (body.ownerKind === 'NONE') body.ownerId = ''
      const context = this.ctx; this.saving = true; this.formError = ''
      await this.execute(() => this.editingId ? academicAffairsEquipmentApi.update(this.editingId, body) : academicAffairsEquipmentApi.create(body), this.editingId, body, 'formError')
      if (!this.disposed && context === this.ctx) this.saving = false
    },
    askStatus(row, target) {
      if (!this.can('update') || this.saving || this.acting || this.pendingResult) return
      const label = { IN_USE: '设为在用', IDLE: '设为闲置', MAINTENANCE: '标记为维修中', SCRAPPED: '报废' }[target]
      this.confirmTitle = `${label}`
      this.confirmMessage = `确认将「${row.equipmentName}」${label}？` + (target === 'MAINTENANCE' ? '本操作只修改资源状态。需要登记故障和跟进维修时，请前往「资源维修」创建工单。' : '')
      this.confirmType = target === 'SCRAPPED' ? 'danger' : target === 'IN_USE' ? 'primary' : 'warning'
      this.pendingAction = { kind: 'status', id: row.equipmentId, target }
      this.actionError = ''; this.confirmVisible = true
    },
    askDelete(row) {
      if (!this.can('delete') || this.saving || this.acting || this.pendingResult) return
      this.confirmTitle = '删除设备'
      this.confirmMessage = `确认删除「${row.equipmentName}」？删除为逻辑删除。`
      this.confirmType = 'danger'
      this.pendingAction = { kind: 'delete', id: row.equipmentId }
      this.actionError = ''; this.confirmVisible = true
    },
    async onConfirm() {
      const action = this.pendingAction
      if (!action || this.acting || this.saving || this.pendingResult || !this.can(action.kind === 'delete' ? 'delete' : 'update')) return
      const context = this.ctx; this.acting = true; this.actionError = ''
      await this.execute(() => action.kind === 'status' ? academicAffairsEquipmentApi.setStatus(action.id, action.target) : academicAffairsEquipmentApi.remove(action.id), action.id, action.kind === 'status' ? { status: action.target } : { deleted: true }, 'actionError')
      if (!this.disposed && context === this.ctx) this.acting = false
    },
    can(action) { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.equipment.' + action) },
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
          const before = await academicAffairsEquipmentApi.get(id); if (!current()) return
          if (before.code !== 0) throw before
          if (String(before.data?.equipmentId) !== String(id)) throw new Error('资源身份不一致，尚未提交。')
        }
        this.pendingResult = { id, expected, accepted: false }
        this.receipt = { title: '办理回执', object: '设备 #' + (id || '待取得编号'), status: '结果待确认', pending: true, next: '正在读取正式资源资料，请勿重复提交。' }
        const res = await command(); if (!current()) return
        if (res.code !== 0) { if (isDeniedResult(res) || isConflictResult(res) || String(res.code || '').startsWith('400')) this.pendingResult = null; throw res }
        this.pendingResult.id = res.data?.equipmentId || id
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
      const res = await academicAffairsEquipmentApi.get(pending.id); if (!current()) return
      if (isDeniedResult(res)) throw res
      const missing = isMissingResult(res)
      const confirmed = pending.expected.deleted ? pending.accepted && missing : res.code === 0 && String(res.data?.equipmentId) === String(pending.id) && Object.entries(pending.expected).every(([key, value]) => String(res.data[key] ?? '') === String(value ?? ''))
      if (!missing && res.code !== 0) throw res
      this.receipt = { title: '办理回执', object: '设备 #' + pending.id, status: confirmed ? pending.expected.deleted ? '已从目录移除' : res.data.statusLabel || res.data.status : '结果待确认', pending: !confirmed, time: res.data?.updatedAt, next: confirmed ? '已重新读取正式目录。相关预约、设备与维修记录请在对应工作区核对。' : '尚未读到与本次操作一致的正式结果，请继续查询。' }
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
.aaeq-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}
.aaeq-filters > * {
  min-width: 140px;
}
.aaeq-filters > .app-button {
  min-width: auto;
}
.aaeq-form {
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
