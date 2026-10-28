<template>
  <ModulePageShell title="请假与返岗" subtitle="核对请假申请、查看审批结果与销假记录。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" :disabled="exporting || loading || !!error || !batchStore.selectedBatchId || !canExport" :title="canExport ? '生成当前查询条件下全部记录的表格' : '当前身份没有导出权限或授权服务暂不可用'" @click="exportFn">{{ exporting ? '表格生成中…' : '生成当前查询台账' }}</AppButton>
    </template>

    <div class="mp-stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />
      <p v-if="exportFile" class="export-receipt" role="status">{{ exportFile.scope }}表格已生成，共 {{ exportFile.rowCount }} 条，包含生成时的全部查询结果。<a :href="exportFile.url" :download="exportFile.filename">下载已生成台账</a>。记录变更后请重新生成。</p>
      <p v-if="exportError" class="state is-err" role="alert">{{ exportError }}</p>

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

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名或学号搜索" @search="reload" />
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
                <div class="lv-item__sub">实习企业：{{ r.enterpriseName || '未登记' }}</div>
                <div class="lv-item__sub">
                  {{ r.startDate }} ~ {{ r.endDate }}<template v-if="r.days"> · {{ r.days }} 天</template><template v-if="r.leaveTypeLabel"> · {{ r.leaveTypeLabel }}</template>
                </div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination v-model:page="page" :page-size="pageSize" :total="total"
                        :show-total="false" :show-size-changer="false" :disabled="loading" @change="turnPage" />
        </template>

        <!-- 右栏：当前请假单详情与审批操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="本页请假单已全部处理"
              description="可翻页或切换筛选条件，继续处理其他请假单" />
            <EmptyState v-else :title="rows.length ? '请选择一条请假单' : panelPurpose.empty"
              :description="rows.length ? '查看详情后办理。' : '可切换分类查看其他记录。'" />
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
              <section v-if="detail.data.approvalProgress" aria-label="审批进度"><div class="sec-t">{{ detail.data.approvalProgress.label }}</div><ol><li v-for="(step,index) in detail.data.approvalProgress.steps" :key="index">{{ step.label }} · {{ step.assignee }} · {{ step.statusLabel }}<p v-if="step.comment">{{ step.comment }}</p></li></ol></section>

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
                <AppFilePreview :files="attachmentFiles" @preview="previewAtt" @download="downloadAtt" />
                <p v-if="fileError" class="state is-err">{{ fileError }}</p>
                <template v-if="previewFile">
                  <button type="button" @click="clearPreview">收起预览</button>
                  <AppDocumentViewer :descriptor="previewDescriptor" :provider="previewProvider"
                    :versions="[previewFile]" :files="[previewFile]" :active-file-key="previewFile.fileId"
                    :active-version-id="previewFile.fileVersionId ?? previewFile.versionId ?? null"
                    :canonical-version-id="previewFile.fileVersionId ?? previewFile.versionId ?? null"
                    :allow-download="false" :show-version-bar="false" :show-file-switcher="false"
                    @preview-error="previewFailed" />
                </template>
              </template>

              <template v-if="hasReview">
                <div class="sec-t">审批结果</div>
                <AppDescriptionList :items="reviewItems" :columns="2" />
              </template>

              <div class="sec-t">审批留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无审批记录" />
            </div>

            <div v-if="detail.data.status === 'PENDING' && detail.data.approvalProgress?.canReview !== false" class="lv-foot">
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="ghost" :danger="true"
                @click="openReview(detail.data, 'REQUEST_CHANGES')">退回补正</AppPermissionButton>
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="secondary" :disabled="loading || detail.loading || cd.submitting" @click="openReview(detail.data, 'REJECT')">驳回</AppPermissionButton>
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="secondary"
                :disabled="!leaveCanApprove" :native-title="leaveApproveHint"
                @click="openReview(detail.data, 'APPROVE')">通过本级审批</AppPermissionButton>
            </div>
            <div v-else-if="detail.data.returnAcknowledged" class="lv-foot lv-foot--return"><p>返岗已经核实，本次请假已办结；核实说明可在审批留痕中查看。</p></div>
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
      :initial-reason="pending?.reason || ''" :confirm-disabled="conflict.active" :submitting="cd.submitting" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="请核对当前申请，本次办理已暂停" description="意见和原版本已保留；读取最新申请后，由你明确采用，系统不会自动重试。">
        <p v-if="conflict.kept">保留意见：{{ conflict.kept }}</p>
        <p v-for="item in conflict.latest" :key="item.label">{{ item.label }}：{{ item.value }}</p>
        <p v-if="conflict.stale">最新详情读取失败，请重试加载。</p>
        <button type="button" class="mp-link" :disabled="detail.loading" @click="rereadConflict">重新读取当前申请</button>
        <button type="button" class="mp-link" :disabled="conflict.stale || detail.loading || !detail.data" @click="adoptConflict">已核对，采用当前版本继续</button>
      </AppInlineAlert>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { AppInlineAlert } from '@/components/common'
import ActionReceipt from './components/ActionReceipt.vue'
import { leaveApi } from '@/modules/internship/api/leave-risk.api'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import { buildPreviewDescriptorFromFile } from '@/components/file/viewer/viewer-contract'
import { fileSdk } from '@/services/file/fileSdk'
import { currentSessionGeneration } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'
import { formatDateTime } from '@/utils/dateUtils'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { REJECT_LEAVE } from '@/modules/internship/constants/presetPrompts'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { AppButton } from '@/components/ui'
import { prepareXlsxDownload } from '@/utils/xlsxDownload'

const STATUS_OPTIONS = [
  { label: '待审批', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' },
  { label: '已销假', value: 'RETURNED' }, { label: '已驳回', value: 'REJECTED' },
  { label: '待学生补正', value: 'NEEDS_REVISION' },
  { label: '已撤回', value: 'WITHDRAWN' }, { label: '超期未销假', value: 'OVERDUE' }
]
/* 右栏只渲染 /internship/leaves/{id} 真实返回字段（见 internship_leave_service._row + get_leave） */
const SUMMARY_FIELDS = [
  { key: 'studentName', label: '学生' }, { key: 'studentNo', label: '学号' },
  { key: 'enterpriseName', label: '实习企业' },
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
  { key: 'statusLabel', label: '当前状态' }
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
    AppConfirmDialog, AppButton, AppPermissionButton, AppDescriptionList, AppAuditTrail,
    AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination, AppInlineAlert, ActionReceipt, AppDocumentViewer },
  data() {
    return {
      REJECT_LEAVE,
      panelOptions: PANEL_OPTIONS,
      activePanel: 'pending',
      listRequest: 0, rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', statusOptions: STATUS_OPTIONS,
      appliedFilters: { keyword: '', status: '' }, exportFile: null, exportError: '', exporting: false, exportRequest: 0,
      selectedId: '', doneHint: false,
      detailRequest: 0, operation: 0, epoch: 0, disposed: false, fileRequest: 0, previewFile: null, previewProvider: null, fileError: '',
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      conflict: emptyConflict(),
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    canExport() { return this.ctx.moduleAccessHealthy !== false && !this.ctx.permissionServiceError && this.canBtn('internship.leave.export') },
    previewDescriptor() { return this.previewFile ? buildPreviewDescriptorFromFile(this.previewFile) : null },
    batchStore() { return useInternshipBatchStore() },
    summaryMetrics() {
      if (this.loading || this.error) return []
      if (this.activePanel === 'return') return [{ label: '待确认返岗', value: this.total, tone: this.total ? 'warn' : undefined }]
      const cur = this.statusOptions.find((o) => o.value === this.appliedFilters.status)
      return [{ label: '请假单 · ' + (cur ? cur.label : '全部'), value: this.total,
        tone: this.appliedFilters.status === 'PENDING' && this.total ? 'warn' : undefined }]
    },
    panelPurpose() {
      const purposes = {
        pending: { step: '步骤 1 · 教师审批', title: '核对请假时间、事由与证明',
          description: '所有必需节点通过后才写入请假考勤；驳回时写清学生需要补充或修改的内容。',
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
    summaryItems() { const d = this.detail.data || {}; return SUMMARY_FIELDS.map((f) => ({ label: f.label, value: f.key.endsWith('At') ? formatDateTime(d[f.key]) : d[f.key] })) },
    leaveItems() { const d = this.detail.data || {}; return LEAVE_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    reviewItems() { const d = this.detail.data || {}; return REVIEW_FIELDS.map((f) => ({ label: f.label, value: f.key.endsWith('At') ? formatDateTime(d[f.key]) : d[f.key] })) },
    returnItems() { const d = this.detail.data || {}; return RETURN_FIELDS.map((f) => ({ label: f.label, value: f.key === 'version' ? `第${d[f.key]}版` : f.key.endsWith('At') ? formatDateTime(d[f.key]) : d[f.key] })) },
    hasReturn() {
      const d = this.detail.data || {}
      return ['RETURNED', 'OVERDUE'].includes(d.status) || !!(d.returnedAt || d.returnNote)
    },
    // BUG-013：待审批单据不得展示审批人/时间——脏数据里 PENDING 也带审批人时会误导教师
    // 以为已经有人批过。只有已通过、已驳回或已销假的终态才渲染审批结论区。
    hasReview() {
      const d = this.detail.data || {}
      if (!['APPROVED', 'REJECTED', 'NEEDS_REVISION', 'RETURNED', 'OVERDUE'].includes(d.status)) return false
      return !!(d.reviewBy || d.reviewAt || d.reviewComment)
    },
    attachmentFiles() { const a = this.detail.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || t.detail.note || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    canExport(allowed) { if (!allowed) this.clearExport() },
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
        this.operation++; this.detailRequest++; this.clearPreview()
        this.pending = null; this.cd.visible = false; this.cd.submitting = false; this.conflict = emptyConflict()
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) } else { this.detail = { loading: false, error: '', data: null } }
      }
    },
    'batchStore.selectedBatchId'() {
      this.resetContext()
      this.page = 1
      this.clearSelection()
      this.load()
    },
    'ctx.ctxKey'() { this.resetContext(); this.selectedId = String(this.$route.query.id || ''); this.load() },
    '$route.query'(query, previous) {
      if (query.panel !== previous?.panel) return
      if (String(query.keyword || '') === this.appliedFilters.keyword && String(query.status ?? PANEL_PRESETS[this.activePanel]().statusFilter) === this.appliedFilters.status && Number(query.page || 1) === this.page) return
      this.resetContext(); this.selectedId = String(query.id || ''); this.restoreQuery(); this.load()
    }
  },
  mounted() { document.addEventListener('visibilitychange', this.visibilityChanged) },
  beforeUnmount() { this.disposed = true; this.resetContext(); document.removeEventListener('visibilitychange', this.visibilityChanged) },
  methods: {
    captureContext() {
      const epoch = this.epoch, generation = currentSessionGeneration(), batchId = String(this.batchStore.selectedBatchId || ''), ctxKey = this.ctx.ctxKey, panel = this.activePanel
      return () => !this.disposed && !document.hidden && epoch === this.epoch && generation === currentSessionGeneration() && batchId === String(this.batchStore.selectedBatchId || '') && ctxKey === this.ctx.ctxKey && panel === this.activePanel
    },
    clearPreview() { this.fileRequest++; this.previewFile = null; this.previewProvider = null; this.fileError = '' },
    clearExport() { this.exportRequest++; if (this.exportFile?.url) URL.revokeObjectURL(this.exportFile.url); this.exportFile = null; this.exportError = ''; this.exporting = false },
    resetContext() {
      this.clearExport()
      this.epoch++; this.listRequest++; this.detailRequest++; this.operation++; this.clearPreview()
      this.rows = []; this.total = 0; this.loading = false; this.error = ''; this.doneHint = false
      this.detail = { loading: false, error: '', data: null }; this.selectedId = ''
      this.pending = null; this.cd.visible = false; this.cd.submitting = false; this.conflict = emptyConflict(); this.lastReceipt = null
    },
    visibilityChanged() {
      if (document.hidden) {
        this.clearExport()
        this.epoch++; this.listRequest++; this.detailRequest++; this.operation++; this.clearPreview()
        this.loading = false; this.detail.loading = false; this.cd.submitting = false
        if (this.pending) this.conflict = { ...emptyConflict(), active: true, stale: true, kept: this.pending.reason || '' }
      } else this.load()
    },
    canBtn(code) { return canCode(this.ctx, code) },
    leaveStatusLabel(status) { return this.statusOptions.find(item => item.value === status)?.label || '状态待核对' },
    leaveStatusType(status) { return status === 'RETURNED' ? 'success' : status === 'OVERDUE' ? 'danger' : '' },
    applyPanel(panel) {
      this.resetContext(); this.selectedId = String(this.$route.query.id || '')
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.pending
      this.activePanel = Object.prototype.hasOwnProperty.call(PANEL_PRESETS, panel) ? panel : 'pending'
      this.statusFilter = preset().statusFilter
      this.restoreQuery()
      this.load()
    },
    restoreQuery() {
      const query = this.$route.query
      this.keyword = String(query.keyword || '')
      const status = String(query.status ?? PANEL_PRESETS[this.activePanel]().statusFilter)
      this.statusFilter = this.activePanel === 'return' ? '' : this.statusOptions.some(item => item.value === status) ? status : ''
      this.appliedFilters = { keyword: this.keyword.trim(), status: this.statusFilter }
      this.page = Number.isSafeInteger(Number(query.page)) && Number(query.page) > 0 ? Number(query.page) : 1
    },
    queryParams() { return { batchId: String(this.batchStore.selectedBatchId || ''), keyword: this.appliedFilters.keyword, status: this.appliedFilters.status, returnPending: this.activePanel === 'return' } },
    updateQuery(clearSelection = false) {
      const query = { ...this.$route.query, panel: this.activePanel, page: String(this.page), keyword: this.appliedFilters.keyword, status: this.appliedFilters.status }
      if (clearSelection) delete query.id
      return this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    switchPanel(panel) {
      this.pending = null; this.cd.visible = false; this.conflict = emptyConflict(); this.lastReceipt = null
      const query = { ...this.$route.query, panel }
      delete query.id
      delete query.keyword; delete query.status; delete query.page
      if (String(this.$route.query.panel || 'pending') === panel && !this.$route.query.id) this.applyPanel(panel)
      else this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery(query) })
    },
    async exportFn() {
      if (this.exporting || this.loading || this.error || !this.batchStore.selectedBatchId || !this.canExport) return false
      this.clearExport()
      const request = this.exportRequest, context = this.captureContext(), params = this.queryParams(), snapshot = JSON.stringify(params)
      const current = () => context() && request === this.exportRequest && snapshot === JSON.stringify(this.queryParams()) && this.canExport
      this.exporting = true
      try {
        const res = await leaveApi.exportLeaves(params)
        if (!current()) return false
        if (res.code !== 0) throw res
        if (!Number.isSafeInteger(res.data?.rowCount) || res.data.rowCount < 0 || res.data.truncated || res.data.rowCount !== res.data.totalRows || res.data.rowCount !== res.data.exportedRows) throw { message: '台账数量不完整，请重新查询并生成' }
        this.exportFile = { ...prepareXlsxDownload(res.data), scope: this.panelOptions.find(item => item.key === this.activePanel)?.label || '请假台账' }
        return true
      } catch (error) { if (current()) this.exportError = normalizeUiError(error, { fallback: '台账生成失败，请重试' }).userMessage; return false }
      finally { if (context() && request === this.exportRequest) this.exporting = false }
    },
    reload() { this.appliedFilters = { keyword: this.keyword.trim(), status: this.activePanel === 'return' ? '' : this.statusFilter }; this.resetContext(); this.page = 1; this.updateQuery(true); return this.load() },
    turnPage() { this.updateQuery(); return this.load() },
    async load() {
      if (this.disposed || document.hidden) return false
      const request = ++this.listRequest
      const current = this.captureContext()
      this.detailRequest++; this.detail.loading = false; this.clearPreview()
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return false
      }
      this.loading = true; this.error = ''
      const params = { ...this.queryParams(), page: this.page, pageSize: this.pageSize }
      let res
      try { res = await leaveApi.getLeaves(params) }
      catch (error) { if (current() && request === this.listRequest) { this.loading = false; this.error = normalizeUiError(error).userMessage }; return false }
      if (!current() || this.listRequest !== request) return false
      this.loading = false
      if (res.code !== 0) { this.error = normalizeUiError(res, { fallback: '加载失败' }).userMessage; this.rows = []; this.total = 0; return false }
      this.rows = res.data.list; this.total = res.data.total
      // 处理完当前页最后一条后翻页越界（如筛选=待审批时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.page > pc) { this.page = pc; await this.updateQuery(); if (!current() || this.listRequest !== request) return false; return this.load() }
      if (this.selectedId && !await this.loadDetail(this.selectedId)) return false
      return current() && request === this.listRequest
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
      if (this.disposed || document.hidden) return false
      const batchId = this.batchStore.selectedBatchId
      const request = ++this.detailRequest, current = this.captureContext()
      this.clearPreview()
      this.detail = { loading: true, error: '', data: null }
      try {
        const res = await leaveApi.getLeaveDetail(id, batchId)
        if (!current() || request !== this.detailRequest || String(this.selectedId) !== String(id)) return false
        if (res.code !== 0) throw res
        if (String(res.data?.id) !== String(id) || String(res.data?.batchId) !== String(batchId) || !Number.isInteger(res.data?.version) || res.data.version < 0) throw { message: '申请不属于当前批次或版本无效，请重新选择' }
        this.detail.data = res.data
        return true
      } catch (error) { if (current() && request === this.detailRequest) this.detail.error = normalizeUiError(error, { fallback: '详情加载失败' }).userMessage; return false }
      finally { if (current() && request === this.detailRequest) this.detail.loading = false }
    },
    async markViewed(row, attachment, current) {
      if (!current()) return false
      const body = { batchId: row.batchId, expectedVersion: row.version, evidenceFileId: attachment.fileId }
      const viewed = await leaveApi.markEvidenceViewed(row.id, body)
      if (!current()) return false
      if (viewed.code !== 0) throw viewed
      if (String(viewed.data?.id) !== String(row.id) || viewed.data?.version !== body.expectedVersion || String(viewed.data?.evidenceFileId) !== String(body.evidenceFileId)) throw { message: '材料版本已变化，请重新核对' }
      this.detail.data.evidenceViewed = true
      const item = this.rows.find(item => String(item.id) === String(row.id))
      if (item && item.version === row.version) item.evidenceViewed = true
      return true
    },
    async previewAtt() {
      const row = this.detail.data, attachment = row?.attachment
      if (!attachment || this.detail.loading || this.cd.submitting) return
      this.clearPreview()
      const sequence = this.fileRequest, context = this.captureContext()
      const current = () => context() && sequence === this.fileRequest && this.detail.data === row
      try {
        const file = await fileSdk.metadata(attachment.fileId)
        if (!current()) return
        if (String(file.fileId) !== String(attachment.fileId) || !file.canPreview) throw { message: '当前证明尚不能安全预览，请核对文件状态' }
        this.previewProvider = { fetchBytes: async (descriptor, { signal } = {}) => {
          const previewCurrent = () => current() && !signal?.aborted
          if (!previewCurrent() || String(descriptor.fileId) !== String(attachment.fileId)) throw { message: '当前申请已变化，请重新打开证明' }
          const bytes = await fileSdk.blob(attachment.fileId)
          if (!previewCurrent() || !await this.markViewed(row, attachment, previewCurrent)) throw { message: '证明读取已失效，请重新打开' }
          return bytes
        }, dispose() {} }
        this.previewFile = file
      } catch (error) { if (current()) this.fileError = normalizeUiError(error).userMessage }
    },
    previewFailed(error) { this.fileError = normalizeUiError(error).userMessage },
    async downloadAtt() {
      const current = this.detail.data
      const a = current?.attachment
      if (!a || this.detail.loading || this.cd.submitting) return
      const context = this.captureContext(), sequence = this.fileRequest
      const stillCurrent = () => context() && sequence === this.fileRequest && this.detail.data === current
      try {
        const saved = await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName, stillCurrent)
        if (saved && await this.markViewed(current, a, stillCurrent)) toast.success('证明已下载，当前版本查看动作已留痕')
      } catch (error) { if (stillCurrent()) toast.error(normalizeUiError(error, { fallback: '证明读取失败，请重试' }).userMessage) }
    },
    openReview(r, action) {
      if (this.loading || this.detail.loading || this.disposed || document.hidden || this.cd.submitting || r !== this.detail.data || String(r.batchId) !== String(this.batchStore.selectedBatchId) || !Number.isInteger(r.version) || r.version < 0 || !this.canBtn('internship.leave.review') || r.status !== 'PENDING' || !['APPROVE', 'REJECT', 'REQUEST_CHANGES'].includes(action) || action === 'APPROVE' && !this.leaveCanApprove) return
      const reason = this.pending?.id === r.id && this.pending?.action === action ? this.pending.reason || '' : ''
      this.conflict = emptyConflict()
      this.pending = { id: r.id, action, expectedVersion: r.version, batchId: r.batchId, reason, current: this.captureContext(), studentName: r.studentName,
        startDate: r.startDate, endDate: r.endDate }
      const ap = action === 'APPROVE'
      const label = ap ? '通过本级审批' : action === 'REQUEST_CHANGES' ? '退回补正' : '驳回'
      this.cd = { visible: true, title: `请假 · ${label}`,
        content: `${label}「${r.studentName}」${r.startDate}~${r.endDate} 的请假，意见将写入审计。${action === 'REQUEST_CHANGES' ? '学生修改后从首级重新审批。' : ''}`,
        danger: !ap, confirmText: label, requireReason: !ap, submitting: false }
    },
    openReturn(r) {
      if (this.loading || this.detail.loading || this.disposed || document.hidden || this.cd.submitting || r !== this.detail.data || String(r.batchId) !== String(this.batchStore.selectedBatchId) || !Number.isInteger(r.version) || r.version < 0 || r.returnAcknowledged || !this.canBtn('internship.leave.review') || !['RETURNED', 'OVERDUE'].includes(r.status)) return
      const reason = this.pending?.id === r.id && this.pending?.action === 'ACK_RETURN' ? this.pending.reason || '' : ''
      this.conflict = emptyConflict()
      this.pending = { id: r.id, action: 'ACK_RETURN', expectedVersion: r.version, batchId: r.batchId, reason, current: this.captureContext(), studentName: r.studentName,
        startDate: r.startDate, endDate: r.endDate, status: r.status }
      this.cd = { visible: true, title: '确认返岗并办结',
        content: `确认「${r.studentName}」已经返岗；系统将同步关闭该请假产生的未结风险。`,
        danger: false, confirmText: '确认返岗并办结', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      if (this.cd.submitting || !this.cd.visible || !this.pending || !this.pending.current() || this.conflict.active || !this.canBtn('internship.leave.review')) return
      const pending = this.pending
      const dialog = this.cd, operation = ++this.operation
      const current = () => pending.current() && operation === this.operation && this.pending === pending && this.cd === dialog && String(this.selectedId) === String(pending.id)
      pending.reason = reason || ''; dialog.submitting = true
      const isReturn = pending.action === 'ACK_RETURN'
      try {
        const body = { expectedVersion: pending.expectedVersion, batchId: pending.batchId }
        const res = isReturn ? await leaveApi.ackReturn(pending.id, { ...body, note: pending.reason })
          : await leaveApi.review(pending.id, { ...body, action: pending.action, comment: pending.reason })
        if (!current()) return
        dialog.submitting = false
        if (isConflict(res)) { this.conflict = { ...emptyConflict(), active: true, kept: pending.reason }; await this.rereadConflict(res); return }
        if (res.code !== 0) throw res
        if (String(res.data?.id) !== String(pending.id) || !Number.isInteger(res.data?.version) || res.data.version < 0) throw { message: '办理结果对象或版本无效，请回读核对' }
        dialog.visible = false; this.conflict = emptyConflict()
        this.clearExport()
        this.lastReceipt = { id: res.data.id, status: res.data.status, statusLabel: res.data.statusLabel, version: res.data.version,
          actionLabel: isReturn ? '返岗已确认' : pending.action === 'APPROVE' ? (res.data.status === 'PENDING' ? '本级通过，已交下一级' : '请假审批全部通过') : pending.action === 'REQUEST_CHANGES' ? '已退回补正' : '请假驳回',
          objectLabel: `${pending.studentName || '学生'} · ${pending.startDate || ''}~${pending.endDate || ''}`,
          auditText: isReturn ? `返岗确认与风险同步已提交；关闭关联风险 ${res.data.risksClosed ?? 0} 条` : pending.action === 'APPROVE' ? (res.data.status === 'PENDING' ? '本级审批留痕与下一级待办已保存；请假尚未最终生效' : '请假更新、打卡豁免与审批留痕已同事务提交') : '处理结果与审批留痕已同事务提交',
          nextStep: isReturn ? '本次请假流程已结束，可在全部台账查看记录' : pending.action === 'APPROVE' ? (res.data.status === 'PENDING' ? '等待下一责任人办理，可查看相同申请的审批进度' : '等待学生按期销假；超期将进入风险联动') : '等待学生查看原因并修正重交' }
        toast.success(isReturn ? '返岗已确认，关联风险已同步' : '审批完成，已写审计')
        await this.advanceAfterAction(pending.id, current)
      } catch (error) { if (current()) toast.error(normalizeUiError(error).userMessage) }
      finally { if (current()) dialog.submitting = false }
    },
    async rereadConflict(res = { code: 409001 }) {
      const pending = this.pending, current = this.captureContext()
      if (!pending) return
      const captured = await captureConflict({ res, kept: pending.reason || this.conflict.kept, refresh: async () => {
        if (!await this.loadDetail(pending.id)) throw { message: '最新申请未读取，请重试' }
      }, latest: () => {
        const fresh = this.detail.data
        if (!fresh) throw { message: '最新申请未读取，请重试' }
        return [{ label: '最新状态', value: fresh.statusLabel || '状态待确认' }, { label: '最新版本', value: `第${fresh.version}版` }, { label: '证明核对', value: this.leaveApproveHint || '当前证明已核对' }]
      } })
      if (current() && this.pending === pending) this.conflict = captured
    },
    adoptConflict() {
      const row = this.detail.data, pending = this.pending
      if (!pending || !this.conflict.active || this.conflict.stale || this.detail.loading || !row || String(row.id) !== String(pending.id) || String(row.batchId) !== String(this.batchStore.selectedBatchId) || !Number.isInteger(row.version) || row.version < 0) return
      const canContinue = pending.action === 'ACK_RETURN' ? ['RETURNED', 'OVERDUE'].includes(row.status) && !row.returnAcknowledged : row.status === 'PENDING' && (pending.action !== 'APPROVE' || this.leaveCanApprove)
      if (!canContinue) return toast.error('当前申请已不能按原动作办理，请取消并核对详情与证明')
      this.pending = { ...pending, expectedVersion: row.version, batchId: row.batchId, current: this.captureContext() }; this.conflict = emptyConflict()
    },
    /** 动作成功后：刷新当前页并自动选中下一条待审批；无下一条则清空选中并提示本页已处理完 */
    async advanceAfterAction(oldId, current = this.captureContext()) {
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      if (!await this.load() || !current()) return
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
