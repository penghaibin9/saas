<template>
  <ModulePageShell
    title="教学资源 · 教室字典"
    :subtitle="'共 ' + pagination.total + ' 间教室 · 排课从本字典选择，容量仅作非阻断提示'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建教室</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aacr-filters">
        <AppTextInput v-model="filters.keyword" placeholder="楼栋 / 教室编号 / 名称" clearable @change="search" />
        <AppSelect v-model="filters.roomType" :options="typeOptions" placeholder="全部类型" @change="search" />
        <AppSelect v-model="filters.status" :options="statusOptions" placeholder="全部状态" @change="search" />
        <AppButton variant="ghost" @click="search">查询</AppButton>
        <AppButton variant="ghost" @click="reset">重置</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无教室" description="点击右上角「新建教室」录入第一间教室" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="classroomId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-room="{ row }">
          <div class="mp-cell-main">{{ row.roomName }}</div>
          <div class="mp-cell-sub">{{ row.buildingCode }} · {{ row.roomCode }}</div>
        </template>
        <template #cell-roomType="{ row }">
          <span class="aacr-tag">{{ row.roomTypeLabel }}</span>
        </template>
        <template #cell-capacity="{ row }">{{ row.capacity }} 座</template>
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
        教室字典为租户级基础数据；排课界面从可用（AVAILABLE）教室选择，若所选教室容量小于教学班人数仅提示不拦截。
        删除为逻辑删除，不影响历史课表中已保存的教室文本快照。
      </p>
    </div>

    <!-- 新建 / 编辑抽屉 -->
    <AppDrawer :visible="formVisible" :title="editingId ? '编辑教室' : '新建教室'" mode="modal" size="large" @close="formVisible = false">
      <div class="aacr-form">
        <AppFormItem label="楼栋编码" required>
          <AppTextInput v-model="form.buildingCode" placeholder="如 A / 教1" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="楼栋名称" required>
          <AppTextInput v-model="form.buildingName" placeholder="如 教学A楼" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="教室编号" required>
          <AppTextInput v-model="form.roomCode" placeholder="如 101" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="教室名称">
          <AppTextInput v-model="form.roomName" placeholder="留空默认 楼栋+编号" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="容量（座位）">
          <AppNumberInput v-model="form.capacity" :min="0" :max="1000" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="教室类型">
          <AppSelect v-model="form.roomType" :options="typeOptions.slice(1)" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="备注">
          <AppTextarea ref="remarkInput" v-model="form.remark" placeholder="选填" :disabled="saving" />
          <AppQuickPhrases scene-key="aa.remark" @pick="onPickRemark" />
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
/** 教学资源 · 教室字典（/admin/academic-affairs/classrooms）：楼栋/教室/容量/类型/可用状态 CRUD 最小闭环。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert, AppQuickPhrases } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', roomType: '', status: '' })
const EMPTY_FORM = () => ({ buildingCode: '', buildingName: '', roomCode: '', roomName: '', capacity: 0, roomType: 'LECTURE', remark: '' })

export default {
  name: 'AaClassroomListView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem,
    AppConfirmDialog, AppInlineAlert, AppQuickPhrases
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
        { key: 'room', title: '教室' },
        { key: 'roomType', title: '类型' },
        { key: 'capacity', title: '容量' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作' }
      ],
      typeOptions: [
        { label: '全部类型', value: '' },
        { label: '普通教室', value: 'LECTURE' },
        { label: '多媒体教室', value: 'MULTIMEDIA' },
        { label: '机房', value: 'COMPUTER' },
        { label: '实验室', value: 'LAB' },
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
    onPickRemark(text) {
      const el = this.$refs.remarkInput && this.$refs.remarkInput.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.form.remark, text)
      this.form.remark = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
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
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.listClassrooms({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
      this.editingId = row.classroomId
      this.form = {
        buildingCode: row.buildingCode, buildingName: row.buildingName, roomCode: row.roomCode,
        roomName: row.roomName, capacity: row.capacity, roomType: row.roomType, remark: row.remark
      }
      this.formError = ''
      this.formVisible = true
    },
    async submitForm() {
      if (!this.form.buildingCode || !this.form.buildingName || !this.form.roomCode) {
        this.formError = '楼栋编码、楼栋名称、教室编号均必填'
        return
      }
      this.saving = true
      this.formError = ''
      const res = this.editingId
        ? await academicAffairsApi.updateClassroom(this.editingId, this.form)
        : await academicAffairsApi.createClassroom(this.form)
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
      this.confirmTitle = `${label}教室`
      this.confirmMessage = `确认将「${row.roomName}」${label}？`
      this.confirmType = target === 'AVAILABLE' ? 'primary' : 'warning'
      this.pendingAction = { kind: 'status', id: row.classroomId, target }
      this.confirmVisible = true
    },
    askDelete(row) {
      this.confirmTitle = '删除教室'
      this.confirmMessage = `确认删除「${row.roomName}」？删除为逻辑删除，不影响历史课表快照。`
      this.confirmType = 'danger'
      this.pendingAction = { kind: 'delete', id: row.classroomId }
      this.confirmVisible = true
    },
    async onConfirm() {
      const a = this.pendingAction
      if (!a) return
      const res = a.kind === 'status'
        ? await academicAffairsApi.setClassroomStatus(a.id, a.target)
        : await academicAffairsApi.deleteClassroom(a.id)
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
.aacr-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}
.aacr-filters > * {
  min-width: 140px;
}
.aacr-filters > .app-button {
  min-width: auto;
}
.aacr-tag {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
}
.aacr-form {
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
