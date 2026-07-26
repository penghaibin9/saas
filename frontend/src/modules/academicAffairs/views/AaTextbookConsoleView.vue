<template>
  <ModulePageShell
    title="教材管理 · 控制台"
    :subtitle="`目录 · 选用 · 审核备案 · 征订到货 · 发放签收 · 费用台账${currentTermName ? ` · 当前学期：${currentTermName}` : ''}`"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aatb-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aatb-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <AppInlineAlert
      v-if="!currentTermId"
      type="warning"
      title="尚未设置当前学期"
      description="教材目录和库存仍可查看；审核、征订、发放和费用写操作必须先在学年学期中设置当前学期。"
    />

    <div v-if="tab !== 'stats'" class="aatb-bar">
      <AppButton v-if="tab === 'catalog'" variant="primary" size="small" @click="openTextbook">新增教材</AppButton>
      <AppButton v-if="tab === 'review'" variant="primary" size="small" :disabled="!currentTermId" @click="createReview">从当前学期已提交选用建审核批次</AppButton>
      <AppButton v-if="tab === 'order'" variant="primary" size="small" :disabled="!currentTermId" @click="createOrder">生成当前学期征订 / 补订</AppButton>
    </div>

    <ErrorState v-if="error" :description="error" @retry="reload" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <div v-if="tab === 'stats'" class="aatb-stats">
        <div class="aatb-stat"><span class="aatb-num">{{ stats.selectionTotal }}</span><span>选用总数</span></div>
        <div class="aatb-stat"><span class="aatb-num">{{ stats.selectionApproved }}</span><span>已备案</span></div>
        <div class="aatb-stat"><span class="aatb-num">{{ stats.orderQty }}</span><span>征订总量</span></div>
        <div class="aatb-stat"><span class="aatb-num">{{ ((stats.arrivalRate || 0) * 100).toFixed(0) }}%</span><span>到货率</span></div>
        <div class="aatb-stat"><span class="aatb-num">¥{{ stats.unpaidAmount || 0 }}</span><span>欠费金额</span></div>
      </div>

      <template v-else>
        <EmptyState v-if="!rows.length" title="暂无数据" :description="emptyHint" />
        <DataTable v-else :columns="columns" :rows="rows" :row-key="rowKey">
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot /></template>
          <template #cell-price="{ row }">¥{{ row.unitPrice != null ? row.unitPrice : '—' }}</template>
          <template #cell-amount="{ row }">¥{{ row.amount }}</template>
          <template #cell-paid="{ row }">¥{{ row.paidAmount != null ? row.paidAmount : 0 }} / ¥{{ row.amount }}</template>
          <template #cell-progress="{ row }">
            <div class="mp-cell-main">待签收 {{ row.pendingCount || 0 }} · 已签收 {{ row.receivedCount || 0 }}</div>
            <div class="mp-cell-sub">退领 {{ row.returnedCount || 0 }} · 未结费用 {{ row.unsettledFeeCount || 0 }}</div>
          </template>
          <template #cell-next="{ row }">{{ row.nextAction || '—' }}</template>
          <template #cell-ops="{ row }">
            <button v-if="tab === 'selection' && row.status === 'DRAFT'" class="mp-link" @click="op('submitSelection', row.selectionId)">提交</button>

            <button v-if="tab === 'review' && canAdvance(row.status)" class="mp-link" @click="advance(row.reviewBatchId, 'APPROVE')">推进</button>
            <button v-if="tab === 'review' && canAdvance(row.status)" class="mp-link is-danger" @click="advanceReturn(row.reviewBatchId)">退回</button>

            <button v-if="tab === 'order' && row.status === 'DRAFT'" class="mp-link" @click="op('submitOrder', row.orderBatchId)">提交征订</button>
            <button v-if="tab === 'order' && ['DRAFT','ORDERED'].includes(row.status)" class="mp-link is-danger" @click="cancelOrder(row)">取消</button>
            <button v-if="tab === 'order' && ['ORDERED','PARTIALLY_ARRIVED'].includes(row.status)" class="mp-link" @click="openArrival(row)">到货登记</button>
            <button v-if="tab === 'order' && ['PARTIALLY_ARRIVED','ARRIVED','ARCHIVED'].includes(row.status)" class="mp-link" @click="openDistributionGenerate(row)">生成发放名单</button>
            <button v-if="tab === 'order' && row.status === 'ARRIVED'" class="mp-link" @click="op('archiveOrder', row.orderBatchId)">归档征订</button>

            <button v-if="tab === 'distribution'" class="mp-link" @click="openDistribution(row)">发放明细</button>

            <button v-if="tab === 'fee' && ['UNPAID','PARTIAL'].includes(row.status)" class="mp-link" @click="markFee(row.feeId, 'PAID')">全额收款</button>
            <button v-if="tab === 'fee' && ['UNPAID','PARTIAL'].includes(row.status)" class="mp-link" @click="openPartial(row)">部分收款</button>
            <button v-if="tab === 'fee' && row.status === 'UNPAID'" class="mp-link" @click="waiveFee(row.feeId)">减免</button>
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
        <AppInlineAlert type="info" description="到货数量是累计值，只能增加且不能超过征订数量。" />
        <EmptyState v-if="!arrivalItems.length" title="无征订明细" description="" />
        <ul v-else class="aatb-items">
          <li v-for="it in arrivalItems" :key="it.itemId">
            <span>{{ it.textbookName }}（订 {{ it.orderQty }} / 到 {{ it.arrivedQty }}）</span>
            <span class="aatb-arr">
              <AppNumberInput v-model="arrivalQty[it.itemId]" :min="it.arrivedQty || 0" :max="it.orderQty" />
              <AppButton size="small" variant="ghost" @click="submitArrival(it.itemId)">登记</AppButton>
            </span>
          </li>
        </ul>
      </div>
    </AppDrawer>

    <AppDrawer :visible="partialVisible" title="部分收款" @close="partialVisible = false">
      <div v-if="partialRow" class="aatb-form">
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
      v-model:visible="reasonDialog.visible"
      :title="reasonDialog.title"
      type="danger"
      require-reason
      :phrase-scene-key="reasonDialog.sceneKey"
      reason-label="原因（≥5字）"
      :submitting="reasonDialog.submitting"
      @confirm="onReasonConfirm"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsTextbookApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { textbookP0Api } from '@/modules/academicAffairs/api/textbook-p0.api'
import { toast } from '@/utils/toast'

const LABELS = {
  DRAFT: '草稿', SUBMITTED: '已提交', REVIEWING: '审核中', APPROVED: '已备案', RETURNED: '已退回', ORDERED: '已征订',
  PARTIALLY_ARRIVED: '部分到货', ARRIVED: '已到货', ARCHIVED: '已归档', CANCELLED: '已取消',
  DISTRIBUTING: '发放中', COMPLETED: '已完成', UNPAID: '未收款', PARTIAL: '部分收款', PAID: '已结清', WAIVED: '已减免'
}

export default {
  name: 'AaTextbookConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      currentTermId: '', currentTermName: '',
      tab: 'catalog', loading: true, error: '', rows: [], stats: {},
      tabs: [
        { key: 'catalog', label: '教材目录' }, { key: 'selection', label: '选用' },
        { key: 'review', label: '审核备案' }, { key: 'order', label: '征订到货' },
        { key: 'distribution', label: '发放签收' }, { key: 'fee', label: '费用台账' },
        { key: 'stock', label: '库存' }, { key: 'stats', label: '统计' }
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
        order: [{ key: 'batchName', title: '批次' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '280px' }],
        distribution: [
          { key: 'orderBatchName', title: '征订批次' }, { key: 'className', title: '班级' },
          { key: 'progress', title: '发放 / 费用' }, { key: 'status', title: '状态' },
          { key: 'next', title: '下一步' }, { key: 'ops', title: '操作' }
        ],
        fee: [{ key: 'textbookName', title: '教材' }, { key: 'amount', title: '应收' }, { key: 'paid', title: '已收/应收' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
        stock: [{ key: 'textbookName', title: '教材' }, { key: 'arrivedQty', title: '到货量' }, { key: 'distributedQty', title: '已发放' }, { key: 'stockQty', title: '库存' }]
      }
      return map[this.tab] || []
    },
    emptyHint() {
      return {
        catalog: '点击新增教材', selection: '教材负责人按教学任务申报',
        review: '当前学期暂无已提交教材选用', order: '当前学期暂无已备案选用可征订',
        distribution: '征订到货后，从征订页生成班级发放名单', fee: '学生签收后按征订价格快照自动生成',
        stock: '征订到货并发放后统计'
      }[this.tab] || ''
    }
  },
  async created() {
    const [contextRes, termRes] = await Promise.all([
      academicAffairsApi.getContext(),
      academicAffairsApi.getCurrentTerm()
    ])
    if (contextRes.code === 0) this.ctx = contextRes.data
    if (termRes.code === 0 && termRes.data) {
      this.currentTermId = String(termRes.data.termId || termRes.data.id || '')
      this.currentTermName = termRes.data.termName || termRes.data.name || termRes.data.termCode || ''
    }
    const q = this.$route?.query?.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.reload()
  },
  methods: {
    rowKey(row) {
      return row.textbookId || row.selectionId || row.reviewBatchId || row.orderBatchId || row.distributionBatchId || row.feeId
    },
    statusLabel(status) { return LABELS[status] || status || '—' },
    statusType(status) {
      if (['PAID', 'APPROVED', 'ARRIVED', 'ARCHIVED', 'COMPLETED'].includes(status)) return 'success'
      if (['CANCELLED', 'RETURNED', 'WAIVED'].includes(status)) return 'info'
      if (['PARTIAL', 'PARTIALLY_ARRIVED', 'REVIEWING', 'DISTRIBUTING'].includes(status)) return 'warning'
      return 'primary'
    },
    openPartial(row) { this.partialRow = row; this.partialAmount = 0; this.partialVisible = true },
    async submitPartial() {
      const amt = Number(this.partialAmount)
      if (!amt || amt <= 0) { toast.error('收款金额须大于0'); return }
      const res = await api.markFee(this.partialRow.feeId, 'PARTIAL', amt)
      if (res.code === 0) { toast.success('已收款'); this.partialVisible = false; this.reload() } else toast.error(res.message)
    },
    canAdvance(status) { return ['DRAFT', 'COLLEGE_REVIEWING', 'COLLEGE_APPROVED', 'ACADEMIC_APPROVED'].includes(status) },
    switchTab(key) {
      this.tab = key
      this.$router.replace({ query: { ...this.$route.query, tab: key } })
      this.reload()
    },
    async reload() {
      this.loading = true
      this.error = ''
      if (this.tab === 'stats') {
        const res = await api.stats(); this.stats = res.code === 0 ? res.data : {}; if (res.code !== 0) this.error = res.message; this.loading = false; return
      }
      if (this.tab === 'stock') {
        const res = await api.stock(); this.rows = res.code === 0 ? (res.data || []) : []; if (res.code !== 0) this.error = res.message; this.loading = false; return
      }
      let res
      if (this.tab === 'catalog') res = await api.listTextbooks({ pageSize: 100 })
      else if (this.tab === 'selection') res = await api.listSelections({ pageSize: 100 })
      else if (this.tab === 'review') res = await api.listReviewBatches({ pageSize: 100 })
      else if (this.tab === 'order') res = await api.listOrderBatches({ pageSize: 100 })
      else if (this.tab === 'distribution') res = await textbookP0Api.listDistributionBatches({ termId: this.currentTermId || undefined, pageSize: 100 })
      else res = await api.feeLedger({ pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
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
      this.reasonDialog = {
        visible: true, title: '退回教材审核', sceneKey: '', submitting: false,
        action: async (reason) => {
          const res = await api.reviewAdvance(id, 'RETURN', reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已退回'); this.reload(); return true
        }
      }
    },
    cancelOrder(row) {
      this.reasonDialog = {
        visible: true, title: '取消教材征订批次', sceneKey: '', submitting: false,
        action: async (reason) => {
          const res = await textbookP0Api.cancelOrder(row.orderBatchId, reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('征订批次已取消，来源选用已恢复'); this.reload(); return true
        }
      }
    },
    async createReview() {
      if (!this.currentTermId) { toast.error('请先设置当前学期'); return }
      const candidates = await textbookP0Api.reviewCandidates(this.currentTermId)
      const items = candidates.code === 0 ? (candidates.data.items || []) : []
      const ids = items.map((item) => item.selectionId)
      if (!ids.length) { toast.error(candidates.message || '当前学期无已提交的教材选用'); return }
      const res = await api.createReviewBatch({
        batchName: `${this.currentTermName || '当前学期'}教材审核批次`,
        termId: this.currentTermId,
        selectionIds: ids
      })
      if (res.code === 0) { toast.success('当前学期审核批次已创建'); this.reload() } else toast.error(res.message)
    },
    async createOrder() {
      if (!this.currentTermId) { toast.error('请先设置当前学期'); return }
      const res = await api.createOrderBatch({ termId: this.currentTermId })
      if (res.code === 0) {
        toast.success(res.data?.supplemental ? '教材补订批次已生成' : '教材征订批次已生成')
        this.reload()
      } else toast.error(res.message)
    },
    openDistributionGenerate(row) {
      this.$router.push({
        name: 'aa-textbook-distribution-new',
        query: { orderBatchId: row.orderBatchId }
      })
    },
    openDistribution(row) {
      this.$router.push({ name: 'aa-textbook-distribution-detail', params: { batchId: row.distributionBatchId } })
    },
    async openArrival(row) {
      this.arrivalRow = row; this.arrivalVisible = true; this.arrivalQty = {}
      const res = await api.orderItems(row.orderBatchId)
      this.arrivalItems = res.code === 0 ? (res.data.items || []) : []
      this.arrivalItems.forEach((item) => { this.arrivalQty[item.itemId] = item.arrivedQty })
    },
    async submitArrival(itemId) {
      const res = await api.recordArrival(itemId, this.arrivalQty[itemId] || 0)
      if (res.code === 0) {
        toast.success('到货累计量已登记')
        const itemsRes = await api.orderItems(this.arrivalRow.orderBatchId)
        this.arrivalItems = itemsRes.code === 0 ? itemsRes.data.items : []
        this.reload()
      } else toast.error(res.message)
    },
    async markFee(id, action) {
      const res = await api.markFee(id, action)
      if (res.code === 0) { toast.success(res.data?.idempotent ? '费用已处于终态' : '费用已结清'); this.reload() } else toast.error(res.message)
    },
    waiveFee(id) {
      this.reasonDialog = {
        visible: true, title: '减免教材费', sceneKey: 'aa.textbook.reduce', submitting: false,
        action: async (reason) => {
          const res = await api.markFee(id, 'WAIVE', undefined, reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success(res.data?.idempotent ? '费用已减免' : '已完成减免'); this.reload(); return true
        }
      }
    },
    async onReasonConfirm({ reason }) {
      const action = this.reasonDialog.action
      if (!action) return
      this.reasonDialog.submitting = true
      const success = await action(reason)
      this.reasonDialog.submitting = false
      if (success) this.reasonDialog.visible = false
    },
    onConfirm() { const action = this.pendingAction; this.pendingAction = null; if (action) action() }
  }
}
</script>

<style scoped>
.aatb-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aatb-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aatb-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aatb-bar { margin: 12px 0; }
.aatb-form { display: flex; flex-direction: column; gap: 12px; }
.aatb-stats { display: flex; gap: 16px; flex-wrap: wrap; }
.aatb-stat { display: flex; flex-direction: column; gap: 4px; padding: 16px 24px; background: var(--fill-light, #f8fafc); border-radius: 10px; min-width: 120px; }
.aatb-num { font-size: 24px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aatb-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.aatb-items li { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.aatb-arr { display: flex; gap: 8px; align-items: center; }
</style>
