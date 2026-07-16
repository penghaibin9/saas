<template>
  <ModulePageShell
    title="教材管理 · 控制台"
    :subtitle="'目录 · 选用(挂教学任务) · 审核备案 · 征订到货 · 发放签收 · 费用台账'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aatb-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aatb-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div v-if="tab !== 'stats'" class="aatb-bar">
      <AppButton v-if="tab === 'catalog'" variant="primary" size="small" @click="openTextbook">新增教材</AppButton>
      <AppButton v-if="tab === 'review'" variant="primary" size="small" @click="createReview">从已提交选用建审核批次</AppButton>
      <AppButton v-if="tab === 'order'" variant="primary" size="small" @click="createOrder">从已备案选用生成征订</AppButton>
    </div>

    <ErrorState v-if="error" :description="error" @retry="reload" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <!-- 统计 -->
      <div v-if="tab === 'stats'" class="aatb-stats">
        <div class="aatb-stat"><span class="aatb-num">{{ stats.selectionTotal }}</span><span>选用总数</span></div>
        <div class="aatb-stat"><span class="aatb-num">{{ stats.selectionApproved }}</span><span>已备案</span></div>
        <div class="aatb-stat"><span class="aatb-num">{{ stats.orderQty }}</span><span>征订总量</span></div>
        <div class="aatb-stat"><span class="aatb-num">{{ (stats.arrivalRate * 100).toFixed(0) }}%</span><span>到货率</span></div>
        <div class="aatb-stat"><span class="aatb-num">¥{{ stats.unpaidAmount }}</span><span>欠费金额</span></div>
      </div>

      <template v-else>
        <EmptyState v-if="!rows.length" title="暂无数据" :description="emptyHint" />
        <DataTable v-else :columns="columns" :rows="rows" :row-key="rowKey">
          <template #cell-status="{ row }"><StatusTag :type="feeType(row.status)" :label="row.status" dot /></template>
          <template #cell-price="{ row }">¥{{ row.unitPrice != null ? row.unitPrice : '—' }}</template>
          <template #cell-amount="{ row }">¥{{ row.amount }}</template>
          <template #cell-paid="{ row }">¥{{ row.paidAmount != null ? row.paidAmount : 0 }} / ¥{{ row.amount }}</template>
          <template #cell-ops="{ row }">
            <!-- 选用 -->
            <button v-if="tab === 'selection' && row.status === 'DRAFT'" class="mp-link" @click="op('submitSelection', row.selectionId)">提交</button>
            <!-- 审核 -->
            <button v-if="tab === 'review' && canAdvance(row.status)" class="mp-link" @click="advance(row.reviewBatchId, 'APPROVE')">推进</button>
            <button v-if="tab === 'review' && canAdvance(row.status)" class="mp-link is-danger" @click="advanceReturn(row.reviewBatchId)">退回</button>
            <!-- 征订 -->
            <button v-if="tab === 'order' && row.status === 'DRAFT'" class="mp-link" @click="op('submitOrder', row.orderBatchId)">提交征订</button>
            <button v-if="tab === 'order' && ['ORDERED','PARTIALLY_ARRIVED'].includes(row.status)" class="mp-link" @click="openArrival(row)">到货登记</button>
            <button v-if="tab === 'order' && row.status === 'ARRIVED'" class="mp-link" @click="op('archiveOrder', row.orderBatchId)">归档</button>
            <!-- 费用 -->
            <button v-if="tab === 'fee' && ['UNPAID','PARTIAL'].includes(row.status)" class="mp-link" @click="markFee(row.feeId, 'PAID')">全额收款</button>
            <button v-if="tab === 'fee' && ['UNPAID','PARTIAL'].includes(row.status)" class="mp-link" @click="openPartial(row)">部分收款</button>
            <button v-if="tab === 'fee' && ['UNPAID','PARTIAL'].includes(row.status)" class="mp-link" @click="waiveFee(row.feeId)">减免</button>
          </template>
        </DataTable>
      </template>
    </template>

    <AppDrawer :visible="tbVisible" title="新增教材" @close="tbVisible = false">
      <div class="aatb-form">
        <AppFormItem label="教材名称" required><AppTextInput v-model="tbForm.name" :disabled="saving" /></AppFormItem>
        <AppFormItem label="ISBN"><AppTextInput v-model="tbForm.isbn" :disabled="saving" /></AppFormItem>
        <AppFormItem label="出版社"><AppTextInput v-model="tbForm.publisher" :disabled="saving" /></AppFormItem>
        <AppFormItem label="定价"><AppNumberInput v-model="tbForm.unitPrice" :min="0" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="tbVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitTextbook">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="arrivalVisible" title="到货登记" @close="arrivalVisible = false">
      <div class="aatb-form">
        <EmptyState v-if="!arrivalItems.length" title="无征订明细" description="" />
        <ul v-else class="aatb-items">
          <li v-for="it in arrivalItems" :key="it.itemId">
            <span>{{ it.textbookName }}（订 {{ it.orderQty }} / 到 {{ it.arrivedQty }}）</span>
            <span class="aatb-arr">
              <AppNumberInput v-model="arrivalQty[it.itemId]" :min="0" :max="it.orderQty" />
              <AppButton size="small" variant="ghost" @click="submitArrival(it.itemId)">登记</AppButton>
            </span>
          </li>
        </ul>
      </div>
    </AppDrawer>

    <AppDrawer :visible="partialVisible" title="部分收款" @close="partialVisible = false">
      <div class="aatb-form" v-if="partialRow">
        <AppFormItem label="教材"><span>{{ partialRow.textbookName }}</span></AppFormItem>
        <AppFormItem label="应收 / 已收"><span>¥{{ partialRow.amount }} / ¥{{ partialRow.paidAmount != null ? partialRow.paidAmount : 0 }}</span></AppFormItem>
        <AppFormItem label="本次收款" required><AppNumberInput v-model="partialAmount" :min="0" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="partialVisible = false">取消</AppButton>
        <AppButton variant="primary" @click="submitPartial">确认收款</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
    <AppConfirmDialog
      v-model:visible="reasonDialog.visible" :title="reasonDialog.title" type="danger"
      require-reason :phrase-scene-key="reasonDialog.sceneKey" reason-label="原因（≥5字）"
      :submitting="reasonDialog.submitting" @confirm="onReasonConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 教材管理 · 控制台（/admin/academic-affairs/textbooks）：目录/选用/审核/征订/费用/统计 tab。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsTextbookApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTextbookConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'catalog', loading: true, error: '', rows: [], stats: {},
      tabs: [
        { key: 'catalog', label: '教材目录' }, { key: 'selection', label: '选用' },
        { key: 'review', label: '审核备案' }, { key: 'order', label: '征订到货' },
        { key: 'fee', label: '费用台账' }, { key: 'stock', label: '库存' }, { key: 'stats', label: '统计' }
      ],
      partialVisible: false, partialRow: null, partialAmount: 0,
      tbVisible: false, tbForm: { name: '', isbn: '', publisher: '', unitPrice: 0 }, formError: '',
      arrivalVisible: false, arrivalRow: null, arrivalItems: [], arrivalQty: {},
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      reasonDialog: { visible: false, title: '', sceneKey: '', submitting: false, action: null }
    }
  },
  computed: {
    columns() {
      const map = {
        catalog: [{ key: 'name', title: '教材' }, { key: 'isbn', title: 'ISBN' }, { key: 'price', title: '定价' }, { key: 'status', title: '状态' }],
        selection: [{ key: 'courseName', title: '课程' }, { key: 'textbookName', title: '教材' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
        review: [{ key: 'batchName', title: '批次' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
        order: [{ key: 'batchName', title: '批次' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
        fee: [{ key: 'textbookName', title: '教材' }, { key: 'amount', title: '应收' }, { key: 'paid', title: '已收/应收' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
        stock: [{ key: 'textbookName', title: '教材' }, { key: 'arrivedQty', title: '到货量' }, { key: 'distributedQty', title: '已发放' }, { key: 'stockQty', title: '库存' }]
      }
      return map[this.tab] || []
    },
    emptyHint() {
      return { catalog: '点击新增教材', selection: '教材负责人按教学任务申报', review: '从已提交选用建审核批次', order: '从已备案选用生成征订', fee: '发放签收后自动生成', stock: '征订到货并发放后统计' }[this.tab] || ''
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.reload()
  },
  methods: {
    rowKey(row) { return row.textbookId || row.selectionId || row.reviewBatchId || row.orderBatchId || row.feeId },
    openPartial(row) { this.partialRow = row; this.partialAmount = 0; this.partialVisible = true },
    async submitPartial() {
      const amt = Number(this.partialAmount)
      if (!amt || amt <= 0) { toast.error('收款金额须大于0'); return }
      const res = await api.markFee(this.partialRow.feeId, 'PARTIAL', amt)
      if (res.code === 0) { toast.success('已收款'); this.partialVisible = false; this.reload() } else toast.error(res.message)
    },
    canAdvance(s) { return ['DRAFT', 'COLLEGE_REVIEWING', 'COLLEGE_APPROVED', 'ACADEMIC_APPROVED'].includes(s) },
    switchTab(k) { this.tab = k; this.reload() },
    async reload() {
      this.loading = true; this.error = ''
      if (this.tab === 'stats') { const r = await api.stats(); this.stats = r.code === 0 ? r.data : {}; this.loading = false; return }
      if (this.tab === 'stock') { const r = await api.stock(); this.rows = r.code === 0 ? (r.data || []) : []; if (r.code !== 0) this.error = r.message; this.loading = false; return }
      let res
      if (this.tab === 'catalog') res = await api.listTextbooks({ pageSize: 100 })
      else if (this.tab === 'selection') res = await api.listSelections({ pageSize: 100 })
      else if (this.tab === 'review') res = await api.listReviewBatches({ pageSize: 100 })
      else if (this.tab === 'order') res = await api.listOrderBatches({ pageSize: 100 })
      else res = await api.feeLedger({ pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    feeType(s) { return s === 'PAID' ? 'success' : s === 'WAIVED' ? 'info' : s === 'PARTIAL' ? 'warning' : 'primary' },
    openTextbook() { this.tbForm = { name: '', isbn: '', publisher: '', unitPrice: 0 }; this.formError = ''; this.tbVisible = true },
    async submitTextbook() {
      if (!this.tbForm.name) { this.formError = '教材名称必填'; return }
      this.saving = true
      const res = await api.createTextbook(this.tbForm)
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.tbVisible = false; this.reload() } else this.formError = res.message
    },
    async op(fn, id) {
      const res = await api[fn](id)
      if (res.code === 0) { toast.success('已处理'); this.reload() } else toast.error(res.message)
    },
    async advance(id, action) {
      const res = await api.reviewAdvance(id, action)
      if (res.code === 0) { toast.success('已推进'); this.reload() } else toast.error(res.message)
    },
    advanceReturn(id) {
      // sceneKey 留空：配置方案 B3「征订退回」未给词条，不硬套其它场景（AppQuickPhrases 会静默不渲染）
      this.reasonDialog = {
        visible: true, title: '退回教材审核', sceneKey: '', submitting: false,
        action: async (reason) => {
          const res = await api.reviewAdvance(id, 'RETURN', reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已退回'); this.reload(); return true
        }
      }
    },
    async createReview() {
      const sels = await api.listSelections({ status: 'SUBMITTED', pageSize: 200 })
      const ids = sels.code === 0 ? sels.data.list.map(s => s.selectionId) : []
      if (!ids.length) { toast.error('无已提交的选用'); return }
      const res = await api.createReviewBatch({ batchName: '教材审核批次', selectionIds: ids })
      if (res.code === 0) { toast.success('已创建'); this.reload() } else toast.error(res.message)
    },
    async createOrder() {
      const res = await api.createOrderBatch({ batchName: '教材征订批次' })
      if (res.code === 0) { toast.success('已生成征订批次'); this.reload() } else toast.error(res.message)
    },
    async openArrival(row) {
      this.arrivalRow = row; this.arrivalVisible = true; this.arrivalQty = {}
      const res = await api.orderItems(row.orderBatchId)
      this.arrivalItems = res.code === 0 ? (res.data.items || []) : []
      this.arrivalItems.forEach(it => { this.arrivalQty[it.itemId] = it.arrivedQty })
    },
    async submitArrival(itemId) {
      const res = await api.recordArrival(itemId, this.arrivalQty[itemId] || 0)
      if (res.code === 0) { toast.success('已登记'); const r = await api.orderItems(this.arrivalRow.orderBatchId); this.arrivalItems = r.code === 0 ? r.data.items : []; this.reload() }
      else toast.error(res.message)
    },
    async markFee(id, action) {
      const res = await api.markFee(id, action)
      if (res.code === 0) { toast.success('已标记'); this.reload() } else toast.error(res.message)
    },
    waiveFee(id) {
      this.reasonDialog = {
        visible: true, title: '减免教材费', sceneKey: 'aa.textbook.reduce', submitting: false,
        action: async (reason) => {
          const res = await api.markFee(id, 'WAIVE', reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已减免'); this.reload(); return true
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
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aatb-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aatb-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aatb-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aatb-bar { margin-bottom: 12px; }
.aatb-form { display: flex; flex-direction: column; gap: 12px; }
.aatb-stats { display: flex; gap: 16px; flex-wrap: wrap; }
.aatb-stat { display: flex; flex-direction: column; gap: 4px; padding: 16px 24px; background: var(--fill-light, #f8fafc); border-radius: 10px; min-width: 120px; }
.aatb-num { font-size: 24px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aatb-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.aatb-items li { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.aatb-arr { display: flex; gap: 8px; align-items: center; }
</style>
