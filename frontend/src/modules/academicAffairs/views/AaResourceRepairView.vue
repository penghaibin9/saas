<template>
  <ModulePageShell title="资源维修" subtitle="教室 / 实训室 / 设备共用维修工单：登记故障 → 维修中 → 完成，联动资源状态">
    <template #actions>
      <AppButton variant="primary" @click="openReport">登记报修</AppButton>
    </template>
    <div class="mp-stack">
      <div class="aarr-bar">
        <AppSelect v-model="filterKind" :options="kindOptions" placeholder="全部资源类型" @change="load" />
        <AppSelect v-model="filterStatus" :options="statusOptions" placeholder="全部状态" @change="load" />
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无维修工单" description="点击右上角登记故障报修" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="repairId">
        <template #cell-resource="{ row }">
          <div class="mp-cell-main">{{ row.resourceLabel }}</div>
          <div class="mp-cell-sub">{{ kindLabel(row.resourceKind) }}</div>
        </template>
        <template #cell-fault="{ row }">
          <div>{{ row.faultDesc }}</div>
          <div v-if="row.repairNote" class="mp-cell-sub">处理：{{ row.repairNote }}</div>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="sType(row.status)" :label="row.statusLabel" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="row.status === 'REPORTED'" class="mp-link" @click="start(row.repairId)">开始维修</button>
          <button v-if="row.status === 'REPORTED' || row.status === 'IN_REPAIR'" class="mp-link" @click="complete(row.repairId)">完成</button>
          <button v-if="row.status === 'REPORTED' || row.status === 'IN_REPAIR'" class="mp-link is-danger" @click="cancel(row.repairId)">取消</button>
        </template>
      </DataTable>

      <p class="mp-note">
        报修登记后会自动把对应教室/实训室/设备状态置为"维修中"；完成维修且该资源无其它未结工单时，会自动恢复为可用/在用状态。
      </p>
    </div>

    <AppDrawer :visible="reportVisible" title="登记故障报修" mode="modal" size="medium" @close="reportVisible = false">
      <div class="aarr-form">
        <AppFormItem label="资源类型" required>
          <AppSelect v-model="form.resourceKind" :options="kindOptions.slice(1)" :disabled="saving" @change="onKindChange" />
        </AppFormItem>
        <AppFormItem label="资源" required>
          <AppClassroomPicker v-if="form.resourceKind === 'CLASSROOM'" v-model="form.resourceId" placeholder="选择教室" :disabled="saving" />
          <AppLabPicker v-else-if="form.resourceKind === 'LAB'" v-model="form.resourceId" placeholder="选择实训室" :disabled="saving" />
          <AppEquipmentPicker v-else v-model="form.resourceId" placeholder="选择设备" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="故障描述" required>
          <AppTextarea v-model="form.faultDesc" placeholder="如：空调不制冷/投影仪无法开机" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="reportVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitReport">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 维修说明/取消原因均为选填：不设 require-reason，也不挂快捷用语（配置方案未给该场景词条） -->
    <AppConfirmDialog
      v-model:visible="noteDialog.visible" :title="noteDialog.title"
      :type="noteDialog.type" :confirm-text="noteDialog.confirmText"
      :submitting="noteDialog.submitting" @confirm="onNoteConfirm"
    >
      <label class="aarr-note-label">{{ noteDialog.label }}
        <AppTextarea v-model="noteDialog.note" :placeholder="noteDialog.placeholder" :disabled="noteDialog.submitting" />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 资源维修（/admin/academic-affairs/resources/repairs）：教室/实训室/设备共用工单台账。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppSelect, AppTextarea, AppFormItem, AppInlineAlert, AppConfirmDialog, AppClassroomPicker, AppLabPicker, AppEquipmentPicker } from '@/components/common'
import { academicAffairsResourceApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _KIND_LABEL = { CLASSROOM: '教室', LAB: '实训室', EQUIPMENT: '设备' }
const _STATUS_LABEL = { REPORTED: '已报修', IN_REPAIR: '维修中', DONE: '已完成', CANCELLED: '已取消' }

export default {
  name: 'AaResourceRepairView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppSelect, AppTextarea, AppFormItem, AppInlineAlert, AppConfirmDialog, AppClassroomPicker, AppLabPicker, AppEquipmentPicker },
  data() {
    return {
      noteDialog: { visible: false, title: '', label: '', placeholder: '', type: 'primary', confirmText: '确认', note: '', submitting: false, action: null },
      loading: true,
      error: '',
      rows: [],
      filterKind: '',
      filterStatus: '',
      kindOptions: [
        { label: '全部资源类型', value: '' },
        { label: '教室', value: 'CLASSROOM' },
        { label: '实训室', value: 'LAB' },
        { label: '设备', value: 'EQUIPMENT' }
      ],
      statusOptions: [
        { label: '全部状态', value: '' },
        { label: '已报修', value: 'REPORTED' },
        { label: '维修中', value: 'IN_REPAIR' },
        { label: '已完成', value: 'DONE' },
        { label: '已取消', value: 'CANCELLED' }
      ],
      columns: [
        { key: 'resource', title: '资源' },
        { key: 'fault', title: '故障' },
        { key: 'reporterName', title: '报修人' },
        { key: 'status', title: '状态' },
        { key: 'ops', title: '操作' }
      ],
      reportVisible: false,
      form: { resourceKind: 'CLASSROOM', resourceId: '', faultDesc: '' },
      formError: '',
      saving: false
    }
  },
  created() { this.load() },
  methods: {
    kindLabel(k) { return _KIND_LABEL[k] || k },
    sType(s) {
      if (s === 'DONE') return 'success'
      if (s === 'CANCELLED') return 'default'
      if (s === 'IN_REPAIR') return 'warning'
      return 'danger'
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = { pageSize: 100 }
      if (this.filterKind) params.resourceKind = this.filterKind
      if (this.filterStatus) params.status = this.filterStatus
      const res = await academicAffairsResourceApi.repairs(params)
      if (res.code === 0) {
        this.rows = res.data.list
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    onKindChange() {
      this.form.resourceId = ''
    },
    openReport() {
      this.form = { resourceKind: 'CLASSROOM', resourceId: '', faultDesc: '' }
      this.formError = ''
      this.reportVisible = true
    },
    async submitReport() {
      if (!this.form.resourceId || !this.form.faultDesc.trim()) {
        this.formError = '资源与故障描述均必填'
        return
      }
      this.saving = true
      const res = await academicAffairsResourceApi.reportRepair(this.form)
      this.saving = false
      if (res.code === 0) {
        toast.success('已登记报修')
        this.reportVisible = false
        this.load()
      } else {
        this.formError = res.message
      }
    },
    async start(id) {
      const res = await academicAffairsResourceApi.startRepair(id)
      if (res.code === 0) { toast.success('已开始维修'); this.load() } else toast.error(res.message)
    },
    complete(id) {
      this.noteDialog = {
        visible: true, title: '完成维修', label: '维修处理说明（选填）',
        placeholder: '如：已更换灯管并测试正常', type: 'primary', confirmText: '确认完成',
        note: '', submitting: false,
        action: async (note) => {
          const res = await academicAffairsResourceApi.completeRepair(id, note)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已完成'); this.load(); return true
        }
      }
    },
    cancel(id) {
      this.noteDialog = {
        visible: true, title: '取消维修工单', label: '取消原因（选填）',
        placeholder: '如：报修信息有误，重复报修', type: 'danger', confirmText: '确认取消',
        note: '', submitting: false,
        action: async (note) => {
          const res = await academicAffairsResourceApi.cancelRepair(id, note)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已取消'); this.load(); return true
        }
      }
    },
    /** 失败时保留弹窗与已填内容，仅成功才关闭 */
    async onNoteConfirm() {
      const action = this.noteDialog.action
      if (!action) return
      this.noteDialog.submitting = true
      const ok = await action((this.noteDialog.note || '').trim())
      this.noteDialog.submitting = false
      if (ok) this.noteDialog.visible = false
    }
  }
}
</script>

<style scoped>
.aarr-bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
.aarr-form { display: flex; flex-direction: column; gap: 12px; }
.aarr-note-label { display: block; font-size: 13px; color: var(--text-secondary, #64748b); }
.aarr-note-label > * { margin-top: 6px; }
.mp-link.is-danger { color: var(--danger-500); }
.mp-link + .mp-link { margin-left: var(--space-2); }
</style>
