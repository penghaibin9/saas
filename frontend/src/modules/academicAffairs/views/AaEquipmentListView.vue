<template>
  <ModulePageShell
    title="教学资源 · 设备资源"
    :subtitle="'共 ' + pagination.total + ' 项设备台账'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建设备</AppButton>
    </template>

    <div class="mp-stack">
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
          <button class="mp-link" @click="openEdit(row)">编辑</button>
          <button v-if="row.status !== 'IN_USE'" class="mp-link" @click="askStatus(row, 'IN_USE')">在用</button>
          <button v-if="row.status !== 'IDLE'" class="mp-link" @click="askStatus(row, 'IDLE')">闲置</button>
          <button v-if="row.status !== 'MAINTENANCE'" class="mp-link" @click="askStatus(row, 'MAINTENANCE')">报修</button>
          <button v-if="row.status !== 'SCRAPPED'" class="mp-link is-danger" @click="askStatus(row, 'SCRAPPED')">报废</button>
          <button class="mp-link is-danger" @click="askDelete(row)">删除</button>
        </template>
      </DataTable>

      <p class="mp-note">
        设备可归属于某教室或实训室（用于查看该场地的设备清单），也可保持"未分配"作为中心库存。
        报修请前往「资源维修」登记工单，处理完成后设备状态会自动联动恢复。
      </p>
    </div>

    <AppDrawer :visible="formVisible" :title="editingId ? '编辑设备' : '新建设备'" @close="formVisible = false">
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
          <AppSelect v-model="form.ownerId" :options="ownerLocationOptions" placeholder="选择教室/实训室" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="责任人">
          <AppTextInput v-model="form.responsibleName" placeholder="选填" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="购置日期">
          <AppTextInput v-model="form.purchaseDate" placeholder="选填，YYYY-MM-DD" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="备注">
          <AppTextarea v-model="form.remark" placeholder="选填" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="formVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitForm">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :type="confirmType"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 设备资源（/admin/academic-affairs/resources/equipment）：教学/实训设备台账。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsEquipmentApi, academicAffairsLabApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', ownerKind: '', status: '' })
const EMPTY_FORM = () => ({ equipmentCode: '', equipmentName: '', specModel: '', quantity: 1, ownerKind: 'NONE', ownerId: '', responsibleName: '', purchaseDate: '', remark: '' })

export default {
  name: 'AaEquipmentListView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem,
    AppConfirmDialog, AppInlineAlert
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
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
      classroomOptions: [],
      labOptions: [],
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
    ownerLocationOptions() {
      const list = this.form.ownerKind === 'LAB' ? this.labOptions : this.classroomOptions
      return list.map((x) => ({ label: x.label, value: x.classroomId || x.labId }))
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    statusType(s) {
      if (s === 'IN_USE') return 'success'
      if (s === 'MAINTENANCE') return 'warning'
      if (s === 'SCRAPPED') return 'danger'
      return 'default'
    },
    async onOwnerKindChange() {
      this.form.ownerId = ''
      if (this.form.ownerKind === 'CLASSROOM' && !this.classroomOptions.length) {
        const r = await academicAffairsApi.getClassroomOptions()
        if (r.code === 0) this.classroomOptions = r.data.items
      } else if (this.form.ownerKind === 'LAB' && !this.labOptions.length) {
        const r = await academicAffairsLabApi.options()
        if (r.code === 0) this.labOptions = r.data.items
      }
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
      const res = await academicAffairsEquipmentApi.list({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.items
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    openCreate() {
      this.editingId = ''
      this.form = EMPTY_FORM()
      this.formError = ''
      this.formVisible = true
    },
    openEdit(row) {
      this.editingId = row.equipmentId
      this.form = {
        equipmentCode: row.equipmentCode, equipmentName: row.equipmentName, specModel: row.specModel,
        quantity: row.quantity, ownerKind: row.ownerKind, ownerId: row.ownerId,
        responsibleName: row.responsibleName, purchaseDate: row.purchaseDate, remark: row.remark
      }
      this.formError = ''
      this.formVisible = true
      if (row.ownerKind === 'CLASSROOM' && !this.classroomOptions.length) this.onOwnerKindChange()
      if (row.ownerKind === 'LAB' && !this.labOptions.length) this.onOwnerKindChange()
    },
    async submitForm() {
      if (!this.form.equipmentCode || !this.form.equipmentName) {
        this.formError = '资产编号、设备名称均必填'
        return
      }
      this.saving = true
      this.formError = ''
      const res = this.editingId
        ? await academicAffairsEquipmentApi.update(this.editingId, this.form)
        : await academicAffairsEquipmentApi.create(this.form)
      this.saving = false
      if (res.code === 0) {
        toast.success(this.editingId ? '已保存' : '已创建')
        this.formVisible = false
        this.load()
      } else {
        this.formError = res.message
      }
    },
    askStatus(row, target) {
      const label = { IN_USE: '设为在用', IDLE: '设为闲置', MAINTENANCE: '报修', SCRAPPED: '报废' }[target]
      this.confirmTitle = `${label}`
      this.confirmMessage = `确认将「${row.equipmentName}」${label}？`
      this.confirmType = target === 'SCRAPPED' ? 'danger' : target === 'IN_USE' ? 'primary' : 'warning'
      this.pendingAction = { kind: 'status', id: row.equipmentId, target }
      this.confirmVisible = true
    },
    askDelete(row) {
      this.confirmTitle = '删除设备'
      this.confirmMessage = `确认删除「${row.equipmentName}」？删除为逻辑删除。`
      this.confirmType = 'danger'
      this.pendingAction = { kind: 'delete', id: row.equipmentId }
      this.confirmVisible = true
    },
    async onConfirm() {
      const a = this.pendingAction
      if (!a) return
      const res = a.kind === 'status'
        ? await academicAffairsEquipmentApi.setStatus(a.id, a.target)
        : await academicAffairsEquipmentApi.remove(a.id)
      this.confirmVisible = false
      this.pendingAction = null
      if (res.code === 0) {
        toast.success('操作成功')
        this.load()
      } else {
        toast.error(res.message)
      }
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
