<template>
  <ModulePageShell
    title="教材发放签收工作区"
    :subtitle="subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/textbooks?tab=distribution')">返回发放批次</AppButton>
      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/textbooks?tab=fee')">处理费用台账</AppButton>
    </template>

    <div class="mp-stack">
      <div v-if="batch" class="aa-summary">
        <div><strong>{{ batch.orderBatchName }}</strong><span>征订批次</span></div>
        <div><strong>{{ batch.className || '—' }}</strong><span>发放班级</span></div>
        <div><strong>{{ pagination.total }}</strong><span>教材记录</span></div>
      </div>
      <AppInlineAlert
        type="info"
        title="退领规则"
        description="未实收教材可退领并减免应收；已发生实收时必须先完成正式退款/冲正，系统不会直接改写财务事实。"
      />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无发放明细" description="请返回征订页生成发放名单" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="recordId"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" :label="distributionStatusLabel(row.status)" dot />
        </template>
        <template #cell-fee="{ row }">
          <AppStatusTag v-if="row.feeStatus" :status="row.feeStatus" />
          <span v-else class="mp-cell-sub">未生成</span>
          <div v-if="row.amount != null" class="mp-cell-sub">¥{{ row.paidAmount || 0 }} / ¥{{ row.amount }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'PENDING'" class="mp-link" :disabled="acting === row.recordId" @click="sign(row)">登记签收</button>
          <button v-if="row.status === 'RECEIVED'" class="mp-link is-danger" :disabled="acting === row.recordId" @click="openReturn(row)">办理退领</button>
          <span v-if="!['PENDING','RECEIVED'].includes(row.status)" class="mp-cell-sub">—</span>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="returnDialog.visible"
      title="办理教材退领"
      type="danger"
      require-reason
      reason-label="退领原因（≥5字）"
      :submitting="acting === returnDialog.recordId"
      @confirm="submitReturn"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert, AppStatusTag } from '@/components/common'
import { academicAffairsTextbookApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { textbookP0Api } from '@/modules/academicAffairs/api/textbook-p0.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTextbookDistributionDetailView',
  components: {
    ModulePageShell,
    DataTable,
    LoadingState,
    ErrorState,
    EmptyState,
    AppButton,
    AppConfirmDialog,
    AppInlineAlert,
    AppStatusTag
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      batch: null,
      acting: '',
      pagination: { page: 1, pageSize: 100, total: 0 },
      returnDialog: { visible: false, recordId: '' },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'textbookName', title: '教材' },
        { key: 'qty', title: '数量', width: '80px' },
        { key: 'status', title: '发放状态', width: '120px' },
        { key: 'fee', title: '费用状态', width: '150px' },
        { key: 'actions', title: '操作', width: '150px' }
      ]
    }
  },
  computed: {
    batchId() { return String(this.$route.params.batchId || '') },
    subtitle() {
      if (!this.batch) return '逐条登记签收、核对费用并处理未实收退领'
      return `${this.batch.orderBatchName || '教材征订'} · ${this.batch.className || '未命名班级'}`
    }
  },
  created() { this.load() },
  methods: {
    distributionStatusLabel(status) {
      return status === 'RETURNED' ? '已退领' : ''
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await textbookP0Api.distributionRecords(this.batchId, this.pagination)
      if (res.code === 0) {
        this.rows = res.data.list
        this.batch = res.data.batch
        this.pagination.total = res.data.total
      } else {
        this.error = res.message || '加载发放明细失败'
      }
      this.loading = false
    },
    async sign(row) {
      if (this.acting) return
      this.acting = row.recordId
      const res = await api.sign(row.recordId)
      this.acting = ''
      if (res.code === 0) {
        toast.success('已登记签收并按征订价格快照生成应收')
        this.load()
      } else toast.error(res.message || '签收失败')
    },
    openReturn(row) {
      this.returnDialog = { visible: true, recordId: row.recordId }
    },
    async submitReturn({ reason }) {
      const recordId = this.returnDialog.recordId
      if (!recordId || this.acting) return
      this.acting = recordId
      const res = await textbookP0Api.returnDistribution(recordId, reason)
      this.acting = ''
      if (res.code === 0) {
        this.returnDialog.visible = false
        toast.success('教材已退领，未实收费用已收口')
        this.load()
      } else toast.error(res.message || '退领失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aa-summary > div { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-summary strong, .aa-summary span { display: block; }
.aa-summary strong { font-size: 18px; color: var(--text-900, #1f2937); }
.aa-summary span { margin-top: 4px; font-size: 12px; color: var(--text-500, #64748b); }
@media (max-width: 760px) { .aa-summary { grid-template-columns: 1fr; } }
</style>
