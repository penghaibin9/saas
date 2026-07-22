<template>
  <ModulePageShell title="实训室预约" subtitle="实训室占用登记 · 同实训室同时段冲突检测 · 审核">
    <template #actions>
      <AppButton variant="primary" @click="openBook">申请预约</AppButton>
    </template>
    <div class="mp-stack">
      <div class="aalb-bar">
        <AppSelect v-model="filterStatus" :options="statusOptions" placeholder="全部状态" @change="load" />
      </div>
      <LoadingState v-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无预约" description="点击右上角申请实训室预约" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="bookingId">
        <template #cell-slot="{ row }">{{ row.bookingDate }} 第{{ row.slotNo }}节</template>
        <template #cell-status="{ row }"><StatusTag :type="sType(row.status)" :label="sLabel(row.status)" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="row.status === 'PENDING'" class="mp-link" @click="review(row.bookingId, 'APPROVE')">通过</button>
          <button v-if="row.status === 'PENDING'" class="mp-link is-danger" @click="reject(row.bookingId)">驳回</button>
        </template>
      </DataTable>
    </div>

    <AppDrawer :visible="bookVisible" title="申请实训室预约" @close="bookVisible = false">
      <div class="aalb-form">
        <AppFormItem label="实训室" required>
          <AppLabPicker v-model="form.labId" placeholder="选择可用实训室" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="日期" required><AppDatePicker v-model="form.bookingDate" :disabled="saving" /></AppFormItem>
        <AppFormItem label="节次" required><AppNumberInput v-model="form.slotNo" :min="1" :max="12" :disabled="saving" /></AppFormItem>
        <AppFormItem label="用途"><AppTextInput v-model="form.purpose" placeholder="如 技能竞赛集训/实训课补课" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="bookVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitBook">提交</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="reasonDialog.visible" title="驳回实训室预约" type="danger"
      require-reason phrase-scene-key="aa.lab.reject" reason-label="驳回原因（≥5字）"
      :submitting="reasonDialog.submitting" @confirm="onReasonConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 实训室预约（/admin/academic-affairs/resources/lab-bookings）：占用登记+冲突检测+审核，与教室预约同一算法。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppSelect, AppFormItem, AppInlineAlert, AppConfirmDialog, AppLabPicker, AppDatePicker } from '@/components/common'
import { academicAffairsLabBookingApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _SL = { PENDING: '待审', APPROVED: '已通过', REJECTED: '已驳回', CANCELLED: '已取消' }

export default {
  name: 'AaLabBookingView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, EmptyState, AppButton, AppDrawer, AppTextInput, AppNumberInput, AppSelect, AppFormItem, AppInlineAlert, AppConfirmDialog, AppLabPicker, AppDatePicker },
  data() {
    return {
      reasonDialog: { visible: false, submitting: false, action: null },
      loading: true, rows: [], filterStatus: '',
      statusOptions: [{ label: '全部状态', value: '' }, { label: '待审', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' }, { label: '已驳回', value: 'REJECTED' }],
      columns: [{ key: 'labText', title: '实训室' }, { key: 'slot', title: '时段' }, { key: 'purpose', title: '用途' }, { key: 'applicantName', title: '申请人' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      bookVisible: false, form: { labId: '', bookingDate: '', slotNo: 1, purpose: '' }, formError: '', saving: false
    }
  },
  created() { this.load() },
  methods: {
    sLabel(s) { return _SL[s] || s },
    sType(s) { return s === 'APPROVED' ? 'success' : s === 'REJECTED' ? 'danger' : 'primary' },
    async load() {
      this.loading = true
      const res = await api.list(this.filterStatus ? { status: this.filterStatus, pageSize: 100 } : { pageSize: 100 })
      this.rows = res.code === 0 ? res.data.list : []
      this.loading = false
    },
    openBook() {
      this.form = { labId: '', bookingDate: '', slotNo: 1, purpose: '' }
      this.formError = ''
      this.bookVisible = true
    },
    async submitBook() {
      if (!this.form.labId || !this.form.bookingDate) { this.formError = '实训室与日期必填'; return }
      this.saving = true
      const res = await api.book(this.form)
      this.saving = false
      if (res.code === 0) { toast.success('已提交'); this.bookVisible = false; this.load() } else this.formError = res.message
    },
    async review(id, action) {
      const res = await api.review(id, action)
      if (res.code === 0) { toast.success('已通过'); this.load() } else toast.error(res.message)
    },
    reject(id) {
      this.reasonDialog = {
        visible: true, submitting: false,
        action: async (reason) => {
          const res = await api.review(id, 'REJECT', reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已驳回'); this.load(); return true
        }
      }
    },
    /** 失败时保留弹窗与已填内容，仅成功才关闭 */
    async onReasonConfirm({ reason }) {
      const action = this.reasonDialog.action
      if (!action) return
      this.reasonDialog.submitting = true
      const ok = await action(reason)
      this.reasonDialog.submitting = false
      if (ok) this.reasonDialog.visible = false
    }
  }
}
</script>

<style scoped>
.aalb-bar { margin-bottom: 12px; }
.aalb-form { display: flex; flex-direction: column; gap: 12px; }
</style>
