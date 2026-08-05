<template>
  <ModulePageShell
    title="教学资源 · 实训室资源"
    :subtitle="'共 ' + pagination.total + ' 间实训室 · 按管理责任人负责制维护'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建实训室</AppButton>
    </template>

    <div class="mp-stack">
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
          <span class="aalr-tag">{{ row.labTypeLabel }}</span>
        </template>
        <template #cell-capacity="{ row }">{{ row.capacity }} 工位</template>
        <template #cell-responsible="{ row }">{{ row.responsibleName || '未指定' }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusType(row.status)" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openEdit(row)">编辑</button>
          <button v-if="row.status !== 'AVAILABLE'" class="mp-link" @click="askStatus(row, 'AVAILABLE')">启用</button>
          <button v-if="row.status !== 'DISABLED'" class="mp-link" @click="askStatus(row, 'DISABLED')">停用</button>
          <button v-if="row.status !== 'MAINTENANCE'" class="mp-link" @click="askStatus(row, 'MAINTENANCE')">报修</button>
          <button class="mp-link is-danger" @click="askDelete(row)">删除</button>
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
          <AppSelect v-model="form.labType" :options="typeOptions.slice(1)" :disabled="saving" />
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
/** 教学资源续卡 · 实训室资源（/admin/academic-affairs/resources/labs）：结构对齐教室字典，另加责任人字段。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsLabApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', labType: '', status: '' })
const EMPTY_FORM = () => ({ labCode: '', labName: '', buildingName: '', capacity: 0, labType: 'SKILL', responsibleName: '', remark: '' })

export default {
  name: 'AaLabResourceListView',
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
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
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
      this.loading = true
      this.error = ''
      const res = await academicAffairsLabApi.list({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
      this.editingId = row.labId
      this.form = {
        labCode: row.labCode, labName: row.labName, buildingName: row.buildingName,
        capacity: row.capacity, labType: row.labType, responsibleName: row.responsibleName, remark: row.remark
      }
      this.formError = ''
      this.formVisible = true
    },
    async submitForm() {
      if (!this.form.labCode || !this.form.labName) {
        this.formError = '实训室编号、名称均必填'
        return
      }
      this.saving = true
      this.formError = ''
      const res = this.editingId
        ? await academicAffairsLabApi.update(this.editingId, this.form)
        : await academicAffairsLabApi.create(this.form)
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
      const label = { AVAILABLE: '启用', DISABLED: '停用', MAINTENANCE: '报修' }[target]
      this.confirmTitle = `${label}实训室`
      this.confirmMessage = `确认将「${row.labName}」${label}？`
      this.confirmType = target === 'AVAILABLE' ? 'primary' : 'warning'
      this.pendingAction = { kind: 'status', id: row.labId, target }
      this.confirmVisible = true
    },
    askDelete(row) {
      this.confirmTitle = '删除实训室'
      this.confirmMessage = `确认删除「${row.labName}」？删除为逻辑删除，历史记录不受影响。`
      this.confirmType = 'danger'
      this.pendingAction = { kind: 'delete', id: row.labId }
      this.confirmVisible = true
    },
    async onConfirm() {
      const a = this.pendingAction
      if (!a) return
      const res = a.kind === 'status'
        ? await academicAffairsLabApi.setStatus(a.id, a.target)
        : await academicAffairsLabApi.remove(a.id)
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
