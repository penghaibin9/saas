<template>
  <ModulePageShell title="请假与返岗" subtitle="核对请假申请、查看审批结果与销假记录。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">导出 Excel 台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

      <nav class="tabs" aria-label="请假与返岗办理视图">
        <span class="tabs__caption">办理视图</span>
        <div class="tabs__list">
          <button v-for="item in panelOptions" :key="item.key" type="button" class="tabs__btn"
            :class="{ 'is-active': activePanel === item.key }" @click="switchPanel(item.key)">
            {{ item.label }}
          </button>
        </div>
      </nav>

      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

      <section class="purpose" aria-label="当前办理说明">
        <div>
          <span class="purpose__eyebrow">{{ panelPurpose.step }}</span>
          <strong>{{ panelPurpose.title }}</strong>
          <p>{{ panelPurpose.description }}</p>
        </div>
        <dl>
          <div><dt>当前责任人</dt><dd>{{ panelPurpose.actor }}</dd></div>
          <div><dt>完成标准</dt><dd>{{ panelPurpose.done }}</dd></div>
        </dl>
      </section>

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-if="activePanel !== 'return'" v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
      </div>

      <DualPaneWorkspace :aside-title="panelPurpose.queueTitle" :aside-count="total">
        <!-- 左栏：请假单队列（紧凑列表，连续处理） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">{{ panelPurpose.empty }}</div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :status="r.status" :label="leaveStatusLabel(r.status)" :type="leaveStatusType(r.status)" />
                </div>
                <div class="lv-item__sub">{{ r.studentNo }}<template v-if="r.advisorName"> · {{ r.advisorName }}</template></div>
                <div class="lv-item__sub">
                  {{ r.startDate }} ~ {{ r.endDate }}<template v-if="r.days"> · {{ r.days }} 天</template><template v-if="r.leaveTypeLabel"> · {{ r.leaveTypeLabel }}</template>
                </div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination v-model:page="page" :page-size="pageSize" :total="total"
                        :show-total="false" :show-size-changer="false" :disabled="loading" @change="load" />
        </template>

        <!-- 右栏：当前请假单详情与审批操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="本页请假单已全部处理"
              description="可翻页或切换筛选条件，继续处理其他请假单" />
            <EmptyState v-else title="从左侧选择一条请假单开始处理"
              description="点击列表项查看详情，通过或驳回后自动跳到下一条待审批" />
          </template>
          <div v-else-if="detail.loading" class="state lv-main__state">详情加载中…</div>
          <div v-else-if="detail.error" class="state is-err lv-main__state">
            {{ detail.error }} <button type="button" class="mp-link" @click="loadDetail(selectedId)">重试</button>
          </div>
          <template v-else-if="detail.data">
            <div class="lv-main__body">
              <div class="lv-head">
                <span class="lv-head__name">{{ detail.data.studentName }}</span>
                <span class="mp-note">{{ detail.data.studentNo }}</span>
                <AppStatusTag :status="detail.data.status" :label="leaveStatusLabel(detail.data.status)" :type="leaveStatusType(detail.data.status)" />
              </div>

              <div class="sec-t">学生与申请摘要</div>
              <AppDescriptionList :items="summaryItems" :columns="2" />

              <div class="sec-t">请假时间与原因</div>
              <AppDescriptionList :items="leaveItems" :columns="2" />

              <template v-if="hasReturn">
                <div class="sec-t">销假与返岗</div>
                <AppDescriptionList :items="returnItems" :columns="2" />
              </template>

              <div class="lv-evidence">
                <div>
                  <strong>审批证明</strong>
                  <span>{{ detail.data.evidenceRequirementLabel }}</span>
                </div>
                <AppStatusTag :type="leaveCanApprove ? 'success' : 'warning'">
                  {{ leaveCanApprove ? '当前版本可审批' : detail.data.hasEvidence ? '证明待核对' : '缺少必需证明' }}
                </AppStatusTag>
              </div>

              <template v-if="detail.data.attachment">
                <div class="sec-t">证明附件</div>
                <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
              </template>

              <template v-if="hasReview">
                <div class="sec-t">审批结果</div>
                <AppDescriptionList :items="reviewItems" :columns="2" />
              </template>

              <div class="sec-t">审批留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无审批记录" />
            </div>

            <div v-if="detail.data.status === 'PENDING'" class="lv-foot">
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="ghost" :danger="true"
                @click="openReview(detail.data, 'REJECT')">驳回</AppPermissionButton>
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="secondary"
                :disabled="!leaveCanApprove" :native-title="leaveApproveHint"
                @click="openReview(detail.data, 'APPROVE')">通过</AppPermissionButton>
            </div>
            <div v-else-if="activePanel === 'return' && ['RETURNED', 'OVERDUE'].includes(detail.data.status)" class="lv-foot lv-foot--return">
              <p>{{ detail.data.status === 'OVERDUE' ? '学生尚未按期销假，请先核实真实返岗情况。' : '学生已提交销假，请核实返岗并同步关闭关联风险。' }}</p>
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="primary"
                @click="openReturn(detail.data)">确认返岗并办结</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-chips="pending?.action === 'REJECT' ? REJECT_LEAVE : []"
      :reason-label="pending?.action === 'ACK_RETURN' ? '返岗核实说明' : '审批意见'"
      :reason-placeholder="pending?.action === 'ACK_RETURN' ? '说明返岗核实结果，如：已电话联系企业并确认到岗' : '请填写具体审批意见'"
      :reason-min-length="pending?.action === 'ACK_RETURN' ? 2 : 5"
      :submitting="cd.submitting" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="申请已更新，本次审批已暂停" description="请保留需要的审批意见，取消后重新打开当前申请，核对最新内容再审批。">
        <p v-if="conflict.stale">最新详情读取失败，请重试加载。</p>
      </AppInlineAlert>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { AppInlineAlert } from '@/components/common'
import ActionReceipt from './components/ActionReceipt.vue'
import { leaveApi } from '@/modules/internship/api/leave-risk.api'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { REJECT_LEAVE } from '@/modules/internship/constants/presetPrompts'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'

const STATUS_OPTIONS = [
  { label: '待审批', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' },
  { label: '已销假', value: 'RETURNED' }, { label: '已驳回', value: 'REJECTED' },
  { label: '已撤回', value: 'WITHDRAWN' }
]
/* 右栏只渲染 /internship/leaves/{id} 真实返回字段（见 internship_leave_service._row + get_leave） */
const SUMMARY_FIELDS = [
  { key: 'studentName', label: '学生' }, { key: 'studentNo', label: '学号' },
  { key: 'advisorName', label: '指导教师' }, { key: 'applyBy', label: '申请人' },
  { key: 'createdAt', label: '申请时间' }
]
const LEAVE_FIELDS = [
  { key: 'leaveTypeLabel', label: '类型' }, { key: 'days', label: '天数' },
  { key: 'startDate', label: '开始日期' }, { key: 'endDate', label: '结束日期' },
  { key: 'reason', label: '请假事由' }
]
const REVIEW_FIELDS = [
  { key: 'reviewBy', label: '审批人' }, { key: 'reviewAt', label: '审批时间' },
  { key: 'reviewComment', label: '审批意见' }
]
const RETURN_FIELDS = [
  { key: 'returnedAt', label: '学生销假时间' }, { key: 'returnNote', label: '销假说明' },
  { key: 'statusLabel', label: '当前状态' }, { key: 'version', label: '数据版本' }
]
const PANEL_OPTIONS = [
  { key: 'pending', label: '待审批' },
  { key: 'return', label: '返岗确认' },
  { key: 'approved', label: '已批准' },
  { key: 'all', label: '全部台账' }
]
const PANEL_PRESETS = {
  all: () => ({ statusFilter: '' }),
  pending: () => ({ statusFilter: 'PENDING' }),
  approved: () => ({ statusFilter: 'APPROVED' }),
  return: () => ({ statusFilter: '' })
}

export default {
  name: 'LeaveReviewView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, ModuleSummaryStrip, AppStatusTag,
    AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList, AppAuditTrail,
    AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination, AppInlineAlert, ActionReceipt },
  data() {
    return {
      REJECT_LEAVE,
      panelOptions: PANEL_OPTIONS,
      activePanel: 'pending',
      listRequest: 0, rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', statusOptions: STATUS_OPTIONS,
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      conflict: emptyConflict(),
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    summaryMetrics() {
      if (this.loading || this.error) return []
      if (this.activePanel === 'return') return [{ label: '待确认返岗', value: this.total, tone: this.total ? 'warn' : undefined }]
      const cur = this.statusOptions.find((o) => o.value === this.statusFilter)
      return [{ label: '请假单 · ' + (cur ? cur.label : '全部'), value: this.total,
        tone: this.statusFilter === 'PENDING' && this.total ? 'warn' : undefined }]
    },
    panelPurpose() {
      const purposes = {
        pending: { step: '步骤 1 · 教师审批', title: '核对请假时间、事由与证明',
          description: '通过后系统写入请假考勤，驳回时写清学生需要补充或修改的内容。',
          actor: '指导教师 / 管理员', done: '审批结果写入并交给学生', queueTitle: '待审批请假', empty: '当前没有待审批请假' },
        return: { step: '步骤 2 · 返岗确认', title: '核实学生已经返岗',
          description: '同时处理学生已销假与超期未归记录；确认后关闭关联超期风险并留下审计。',
          actor: '指导教师 / 管理员', done: '返岗确认完成，关联风险同步', queueTitle: '待确认返岗', empty: '当前没有待确认返岗记录' },
        approved: { step: '跟进中 · 等待销假', title: '查看已经批准的请假',
          description: '关注请假截止日期；学生返岗后提交销假，记录将进入返岗确认。',
          actor: '学生按期销假，教师关注', done: '学生提交销假或系统标记超期', queueTitle: '已批准请假', empty: '当前没有已批准请假' },
        all: { step: '留痕 · 全部记录', title: '查询请假、审批与销假历史',
          description: '按学生或状态检索完整台账，查看附件、审批结论和办理留痕。',
          actor: '指导教师 / 管理员', done: '记录可查询、可导出、可追溯', queueTitle: '全部请假单', empty: '当前筛选下暂无请假记录' }
      }
      return purposes[this.activePanel] || purposes.pending
    },
    leaveCanApprove() {
      const d = this.detail.data
      if (!d) return false
      if (d.evidenceRequired && !d.hasEvidence) return false
      return !d.hasEvidence || !!d.evidenceViewed
    },
    leaveApproveHint() {
      const d = this.detail.data
      if (!d) return ''
      if (d.evidenceRequired && !d.hasEvidence) return '按规则必须上传证明，当前不可通过'
      if (d.hasEvidence && !d.evidenceViewed) return '请先下载并核对当前版本证明'
      return ''
    },
    summaryItems() { const d = this.detail.data || {}; return SUMMARY_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    leaveItems() { const d = this.detail.data || {}; return LEAVE_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    reviewItems() { const d = this.detail.data || {}; return REVIEW_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    returnItems() { const d = this.detail.data || {}; return RETURN_FIELDS.map((f) => ({ label: f.label, value: f.key === 'version' ? `v${d[f.key] ?? 0}` : d[f.key] })) },
    hasReturn() {
      const d = this.detail.data || {}
      return ['RETURNED', 'OVERDUE'].includes(d.status) || !!(d.returnedAt || d.returnNote)
    },
    // BUG-013：待审批单据不得展示审批人/时间——脏数据里 PENDING 也带审批人时会误导教师
    // 以为已经有人批过。只有已通过、已驳回或已销假的终态才渲染审批结论区。
    hasReview() {
      const d = this.detail.data || {}
      if (!['APPROVED', 'REJECTED', 'RETURNED'].includes(d.status)) return false
      return !!(d.reviewBy || d.reviewAt || d.reviewComment)
    },
    attachmentFiles() { const a = this.detail.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'pending').toString())
      }
    },
    '$route.query.id': {
      immediate: true,
      handler(id) {
        const sid = (id || '').toString()
        if (sid === this.selectedId) return
        this.pending = null; this.cd.visible = false; this.conflict = emptyConflict(); this.lastReceipt = null
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) } else { this.detail = { loading: false, error: '', data: null } }
      }
    },
    'batchStore.selectedBatchId'() {
      this.pending = null; this.cd.visible = false; this.conflict = emptyConflict(); this.lastReceipt = null
      this.page = 1
      this.clearSelection()
      this.load()
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    leaveStatusLabel(status) { return ({ RETURNED: '已销假', OVERDUE: '超期未归' })[status] || '' },
    leaveStatusType(status) { return status === 'RETURNED' ? 'success' : status === 'OVERDUE' ? 'danger' : '' },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.pending
      this.activePanel = Object.prototype.hasOwnProperty.call(PANEL_PRESETS, panel) ? panel : 'pending'
      this.statusFilter = preset().statusFilter
      this.keyword = ''
      this.page = 1
      this.load()
    },
    switchPanel(panel) {
      this.pending = null; this.cd.visible = false; this.conflict = emptyConflict(); this.lastReceipt = null
      const query = { ...this.$route.query, panel }
      delete query.id
      if (String(this.$route.query.panel || 'pending') === panel && !this.$route.query.id) this.applyPanel(panel)
      else this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery(query) })
    },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return leaveApi.exportLeaves({ keyword: this.keyword, status: this.statusFilter, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    async load() {
      const request = ++this.listRequest
      const batchId = this.batchStore.selectedBatchId
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.status = this.statusFilter
      const res = this.activePanel === 'return'
        ? await leaveApi.getReturnQueue(this.batchStore.selectedBatchId)
        : await leaveApi.getLeaves(params)
      if (this.listRequest !== request || batchId !== this.batchStore.selectedBatchId) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      if (this.activePanel === 'return') {
        const keyword = this.keyword.trim().toLowerCase()
        const all = (res.data.list || []).filter((row) => !keyword || `${row.studentName || ''} ${row.studentNo || ''}`.toLowerCase().includes(keyword))
        this.total = all.length
        this.rows = all.slice((this.page - 1) * this.pageSize, this.page * this.pageSize)
      } else {
        this.rows = res.data.list; this.total = res.data.total
      }
      // 处理完当前页最后一条后翻页越界（如筛选=待审批时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; return this.load() }
    },
    select(id) {
      const sid = String(id)
      this.doneHint = false
      if (String(this.$route.query.id || '') === sid) {
        if (this.selectedId !== sid) { this.selectedId = sid; this.loadDetail(sid) }
        return
      }
      this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id: sid }) })
    },
    clearSelection() {
      const query = { ...this.$route.query }
      delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const res = await leaveApi.getLeaveDetail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    async downloadAtt() {
      const current = this.detail.data
      const a = current?.attachment
      if (!a) return
      try {
        await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName)
        if (this.detail.data !== current) return
        const viewed = await leaveApi.markEvidenceViewed(current.id)
        if (this.detail.data !== current) return
        if (viewed.code !== 0) return toast.error(viewed.message || '证明已下载，但查看留痕失败')
        this.detail.data = { ...this.detail.data, evidenceViewed: true }
        const row = this.rows.find((item) => String(item.id) === String(this.detail.data.id))
        if (row) row.evidenceViewed = true
        toast.success('证明已下载，当前版本查看动作已留痕')
      } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openReview(r, action) {
      if (this.cd.submitting || !this.canBtn('internship.leave.review') || r.status !== 'PENDING' || !['APPROVE', 'REJECT'].includes(action) || action === 'APPROVE' && !this.leaveCanApprove) return
      this.conflict = emptyConflict()
      this.pending = { id: r.id, action, expectedVersion: r.version, studentName: r.studentName,
        startDate: r.startDate, endDate: r.endDate }
      const ap = action === 'APPROVE'
      this.cd = { visible: true, title: ap ? '请假 · 通过' : '请假 · 驳回',
        content: `${ap ? '通过' : '驳回'}「${r.studentName}」${r.startDate}~${r.endDate} 的请假，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '驳回', requireReason: !ap, submitting: false }
    },
    openReturn(r) {
      if (this.cd.submitting || !this.canBtn('internship.leave.review') || !['RETURNED', 'OVERDUE'].includes(r.status)) return
      this.conflict = emptyConflict()
      this.pending = { id: r.id, action: 'ACK_RETURN', expectedVersion: r.version, studentName: r.studentName,
        startDate: r.startDate, endDate: r.endDate, status: r.status }
      this.cd = { visible: true, title: '确认返岗并办结',
        content: `确认「${r.studentName}」已经返岗；系统将同步关闭该请假产生的未结风险。`,
        danger: false, confirmText: '确认返岗并办结', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      if (this.cd.submitting || !this.pending || this.conflict.active || !this.canBtn('internship.leave.review')) return
      const pending = this.pending
      const batchId = this.batchStore.selectedBatchId
      this.cd.submitting = true
      const isReturn = this.pending.action === 'ACK_RETURN'
      const res = isReturn
        ? await leaveApi.ackReturn(this.pending.id, { note: reason || '', expectedVersion: this.pending.expectedVersion })
        : await leaveApi.review(this.pending.id, {
          action: this.pending.action, comment: reason || '', expectedVersion: this.pending.expectedVersion
        })
      this.cd.submitting = false
      if (this.pending !== pending || batchId !== this.batchStore.selectedBatchId) return
      if (isConflict(res)) {
        this.conflict = { ...emptyConflict(), active: true }
        const captured = await captureConflict({
          res, kept: reason || '', refresh: async () => { await this.loadDetail(pending.id); if (this.detail.error) throw new Error(this.detail.error) },
          latest: () => {
            const fresh = this.detail.data
            if (!fresh) throw new Error('最新请假详情未拉回')
            return [
              { label: '最新状态', value: fresh.statusLabel || fresh.status || '' },
              { label: '最新版本', value: fresh.version }
            ]
          }
        })
        if (this.pending === pending) this.conflict = captured
        return
      }
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false
      this.conflict = emptyConflict()
      this.lastReceipt = {
        id: res.data?.id, status: res.data?.status, statusLabel: res.data?.statusLabel,
        version: res.data?.version,
        actionLabel: isReturn ? '返岗已确认' : this.pending.action === 'APPROVE' ? '请假通过' : '请假驳回',
        objectLabel: `${this.pending.studentName || '学生'} · ${this.pending.startDate || ''}~${this.pending.endDate || ''}`,
        auditText: isReturn
          ? `返岗确认与风险同步已提交；关闭关联风险 ${res.data?.risksClosed ?? 0} 条`
          : this.pending.action === 'APPROVE'
            ? '请假更新、打卡豁免与审批留痕已同事务提交'
            : '请假驳回与审批留痕已同事务提交',
        nextStep: isReturn ? '本次请假流程已结束，可在全部台账查看记录'
          : this.pending.action === 'APPROVE' ? '等待学生按期销假；超期将进入风险联动' : '等待学生查看原因并修正重交'
      }
      toast.success(isReturn ? '返岗已确认，关联风险已同步' : '审批完成，已写审计')
      await this.advanceAfterAction(this.pending.id)
    },
    /** 动作成功后：刷新当前页并自动选中下一条待审批；无下一条则清空选中并提示本页已处理完 */
    async advanceAfterAction(oldId) {
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      await this.load()
      let after = null, before = null
      this.rows.forEach((r, i) => {
        if (String(r.id) === String(oldId) || this.activePanel !== 'return' && r.status !== 'PENDING') return
        if (i >= oldIndex) { if (!after) after = r } else if (!before) before = r
      })
      const next = after || before
      if (next) { this.select(next.id); return }
      this.clearSelection()
      this.doneHint = true
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }
.tabs { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 10px 12px; border: 1px solid var(--card-b); border-radius: var(--r); background: linear-gradient(100deg, var(--pri-bg), var(--card)); box-shadow: var(--s1); }
.tabs__caption { color: var(--t2); font-size: 12px; font-weight: var(--font-weight-semibold); white-space: nowrap; }
.tabs__list { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: rgba(255,255,255,.72); }
.tabs__btn { min-height: 32px; padding: 0 14px; border: 0; border-radius: 8px; background: transparent; color: var(--t3); font: inherit; font-size: 13px; cursor: pointer; }
.tabs__btn:hover { color: var(--pri); background: rgba(255,255,255,.84); }
.tabs__btn.is-active { color: var(--pri); background: var(--card); box-shadow: 0 2px 8px rgba(31,78,152,.12); font-weight: 600; }
.purpose { display: grid; grid-template-columns: minmax(0,1.35fr) minmax(320px,.85fr); gap: 24px; padding: 18px 20px; border: 1px solid var(--card-b); border-radius: 12px; background: linear-gradient(120deg,var(--card),var(--pri-bg)); }
.purpose__eyebrow { display: block; margin-bottom: 5px; color: var(--pri); font-size: 11px; font-weight: 700; letter-spacing: .04em; }
.purpose strong { display: block; color: var(--t1); font-size: 18px; }
.purpose p { margin: 7px 0 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.purpose dl { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 0; }
.purpose dl div { padding: 10px 12px; border: 1px solid rgba(80,110,160,.12); border-radius: 9px; background: rgba(255,255,255,.76); }
.purpose dt { color: var(--t3); font-size: 11px; }
.purpose dd { margin: 5px 0 0; color: var(--t1); font-size: 13px; font-weight: 600; line-height: 1.45; }

/* 左栏紧凑列表 */
.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 右栏详情与固定操作区 */
.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-main__state { margin: var(--space-4); }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-evidence { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: var(--space-3); padding: 10px 12px; border: 1px solid var(--card-b); border-radius: 9px; background: var(--fill-2,#f8fafc); }.lv-evidence > div { display: grid; gap: 3px; }.lv-evidence span { color: var(--t3); font-size: 12px; }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }
.lv-foot--return { align-items: center; justify-content: space-between; }
.lv-foot--return p { margin: 0; color: var(--t3); font-size: 12px; line-height: 1.55; }
@media (max-width: 900px) { .purpose { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .tabs { align-items: flex-start; flex-direction: column; } .tabs__list { width: 100%; overflow-x: auto; } .tabs__btn { flex: 0 0 auto; } .purpose dl { grid-template-columns: 1fr; } .lv-foot--return { align-items: stretch; flex-direction: column; } }
</style>
