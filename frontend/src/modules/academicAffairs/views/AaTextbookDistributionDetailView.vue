<template>
  <ModulePageShell
    title="教材发放签收工作区"
    :subtitle="subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push(returnPath)">返回来源批次</AppButton>
      <AppButton v-if="batch?.orderBatchId && batch?.classId" :disabled="loading || !!error || !!acting" @click="openAppend">补充未发放学生</AppButton>
      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/textbooks?tab=fee')">处理费用台账</AppButton>
    </template>

    <div class="mp-stack">
      <p class="aa-batch-id">发放批次：{{ batchId }}<span v-if="batch?.orderBatchId"> · 征订批次：{{ batch.orderBatchId }}</span></p>
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
import { currentUserFromToken } from '@/services/http/client'
import { systemConfirm } from '@/services/systemDialog'
import { textbookReturnPath } from '../components/textbooks/textbookNavigation.js'

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
      pagination: { page: 1, pageSize: 20, total: 0 }, loadSeq: 0, actionSeq: 0,
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
    returnPath() { return textbookReturnPath(this.$route.query.returnTo) },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    batchId() { return String(this.$route.params.batchId || '') },
    subtitle() {
      if (!this.batch) return '逐条登记签收、核对费用并处理未实收退领'
      return `${this.batch.orderBatchName || '教材征订'} · ${this.batch.className || '未命名班级'}`
    }
  },
  watch: { batchId: 'resetObject', identityKey: 'resetObject' },
  created() { this.load() },
  beforeUnmount() { this.loadSeq++; this.actionSeq++ },
  methods: {
    openAppend() {
      if (this.loading || this.error || this.acting || !this.batch?.orderBatchId || !this.batch?.classId) return
      this.$router.push({ name: 'aa-textbook-distribution-new', query: { orderBatchId: String(this.batch.orderBatchId), classId: String(this.batch.classId), appendToBatchId: this.batchId, returnTo: this.returnPath } })
    },
    resetObject() {
      this.loadSeq++; this.actionSeq++; this.acting = ''; this.rows = []; this.batch = null
      this.returnDialog.visible = false; this.pagination.page = 1; this.pagination.total = 0; this.load()
    },
    distributionStatusLabel(status) {
      return status === 'RETURNED' ? '已退领' : ''
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async load() {
      const seq = ++this.loadSeq, batchId = this.batchId, identity = this.identityKey, page = this.pagination.page
      const current = () => seq === this.loadSeq && batchId === this.batchId && identity === this.identityKey && page === this.pagination.page
      this.loading = true
      this.error = ''
      try {
      const res = await textbookP0Api.distributionRecords(batchId, { ...this.pagination })
      if (!current()) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.batch = res.data.batch
        this.pagination.total = res.data.total
      } else {
        this.error = res.message || '加载发放明细失败'
      }
      } catch (error) { if (current()) this.error = error?.message || '加载发放明细失败' }
      finally { if (current()) this.loading = false }
    },
    async sign(row) {
      if (this.acting || row.status !== 'PENDING') return
      const id = row.recordId, batchId = this.batchId, identity = this.identityKey, seq = ++this.actionSeq
      const current = () => seq === this.actionSeq && batchId === this.batchId && identity === this.identityKey
      this.acting = id
      try {
      const accepted = await systemConfirm({ title: '确认登记教材签收', message: `${row.studentName || row.studentNo || row.studentId} · ${row.textbookName} · ${row.qty} 册\n请确认已实际发放。登记后将按征订价格快照形成应收，不代表已经收款。`, confirmText: '登记已领用' })
      if (!accepted || !current()) return
      const res = await api.sign(id)
      if (!current()) return
      if (res.code === 0) {
        toast.success('已登记签收并按征订价格快照生成应收')
        this.load()
      } else toast.error(res.message || '签收失败')
      } catch (error) { if (current()) toast.error(error?.message || '签收结果未确认，请刷新当前名单核对') }
      finally { if (current()) this.acting = '' }
    },
    openReturn(row) {
      if (this.acting || row.status !== 'RECEIVED') return
      this.returnDialog = { visible: true, recordId: row.recordId, batchId: this.batchId, identity: this.identityKey }
    },
    async submitReturn({ reason }) {
      const recordId = this.returnDialog.recordId
      if (!recordId || this.acting || !this.returnDialog.visible || this.returnDialog.identity !== this.identityKey || this.returnDialog.batchId !== this.batchId) return
      const batchId = this.batchId, identity = this.identityKey, seq = ++this.actionSeq
      const current = () => seq === this.actionSeq && batchId === this.batchId && identity === this.identityKey
      this.acting = recordId
      try {
      const res = await textbookP0Api.returnDistribution(recordId, reason)
      if (!current()) return
      if (res.code === 0) {
        this.returnDialog.visible = false
        toast.success('教材已退领，未实收费用已收口')
        this.load()
      } else toast.error(res.message || '退领失败')
      } catch (error) { if (current()) toast.error(error?.message || '退领结果未确认，请刷新当前名单核对') }
      finally { if (current()) this.acting = '' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-batch-id { margin: 0; padding: 14px 16px; border-left: 3px solid var(--primary-color, #2b5bb4); background: var(--bg-white, #fff); font-size: 13px; }
.aa-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aa-summary > div { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-summary strong, .aa-summary span { display: block; }
.aa-summary strong { font-size: 18px; color: var(--text-900, #1f2937); }
.aa-summary span { margin-top: 4px; font-size: 12px; color: var(--text-500, #64748b); }
@media (max-width: 760px) { .aa-summary { grid-template-columns: 1fr; } }
</style>
