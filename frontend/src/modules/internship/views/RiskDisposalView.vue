<template>
  <ModulePageShell :title="complaintMode ? '投诉处置' : '风险处置'" subtitle="选择记录，核对来源与责任人，完成本次跟进。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton v-if="!complaintMode" :export-fn="exportFn" :has-permission="canBtn('internship.risk.export')" @exported="onExported">导出处置台账</AppExportButton>
    </template>

    <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

    <div v-if="!complaintMode" class="bar">
      <AppSearchBox v-model="keyword" placeholder="搜索学生姓名或学号" @search="reload" />
      <AppQuickFilterChips v-model="levelFilter" :options="levelOptions" allow-clear @change="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
    </div>

    <DualPaneWorkspace :aside-title="complaintMode ? '投诉记录' : '风险记录'" :aside-count="total" :aside-width="420">
      <!-- 左栏：风险队列 -->
      <template #aside>
        <div v-if="error" class="state is-err">{{ error }} <button class="mp-link" @click="load">重试</button></div>
        <div v-else-if="loading" class="state">加载中…</div>
        <div v-else-if="!rows.length" class="state">当前筛选条件下暂无风险单</div>
        <ul v-else class="queue">
          <li v-for="row in rows" :key="row.id">
            <button type="button" class="queue__item" :class="{ 'is-active': String(row.id) === selectedId }" @click="select(row)">
            <div class="queue__top">
              <span class="mp-cell-main">{{ row.studentName }}</span>
              <span class="mp-note">{{ row.className }}</span>
              <AppRiskTag :level="row.level" class="queue__lvl" />
            </div>
            <div class="queue__src">{{ sourceText(row.source) }}</div>
            <div class="queue__meta">
              <AppStatusTag :status="row.status" />
              <span class="mp-note">截止 {{ row.deadline || '未设置' }}</span>
            </div>
            <div v-if="row.lastFollow && row.lastFollow !== '—'" class="queue__follow" :title="row.lastFollow">
              最近跟进：{{ row.lastFollow }}
            </div>
            </button>
          </li>
        </ul>
      </template>
      <template #aside-foot>
        <AppPagination :total="total" :page="page" :page-size="pageSize"
          :show-size-changer="false" :disabled="loading" @change="onPageChange" />
      </template>

      <!-- 右栏：处置工作台 -->
      <div class="ws">
        <LoadingState v-if="detailLoading" text="正在加载风险单详情…" />
        <ErrorState v-else-if="detailError" title="风险单详情加载失败" :description="detailError"
          @retry="loadDetail(selectedId)" />
        <EmptyState v-else-if="!selectedId && queueDone" title="已处理到当前列表末尾"
          description="可调整筛选或翻页，核对其他待办记录"><template #actions><AppButton variant="ghost" @click="reload">刷新列表</AppButton></template></EmptyState>
        <EmptyState v-else-if="!selectedId" title="从左侧选择一条记录"
          description="在此核对详情、查看留痕并继续办理"><template #actions><AppButton variant="ghost" @click="reload">刷新列表</AppButton></template></EmptyState>
        <template v-else-if="detail">
          <section class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">{{ complaintMode ? '投诉内容与进度' : '风险概要' }}</span>
              <span class="ws__tags">
                <AppRiskTag :level="complaintMode ? detail.severity : detail.riskLevel" />
                <AppStatusTag :status="detail.status" />
              </span>
            </div>
            <div class="mp-card__body">
              <AppDescriptionList :items="summaryItems" :columns="2" />
              <div v-if="detail.closeBlockers?.length" class="ws__blockers" role="alert">
                <strong>关闭条件未满足</strong>
                <span>{{ detail.closeBlockers.join('；') }}</span>
                <button v-if="detail.sourceId && ['INCIDENT', 'COMPLAINT'].includes(detail.sourceType)" type="button" class="mp-link" @click="goSource">处理来源事项</button>
              </div>
            </div>
          </section>

          <section v-if="complaintMode" class="mp-card">
            <div class="mp-card__head"><span class="mp-card__title">投诉材料</span></div>
            <div class="mp-card__body">
              <p v-if="detail.evidenceMasked" class="mp-note">当前权限不可查看此材料。</p>
              <AppButton v-else-if="detail.evidenceFileId" variant="secondary" :loading="evidenceLoading" @click="previewEvidence">查看投诉材料</AppButton>
              <p v-else class="mp-note">未附投诉材料。</p>
              <p v-if="evidenceError" class="evidence-error" role="alert">{{ evidenceError }}</p>
              <AppButton v-if="detail.riskId" variant="ghost" @click="goLinkedRisk">查看关联风险</AppButton>
            </div>
          </section>

          <section v-if="!complaintMode" class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">学生与企业摘要</span>
              <button v-if="detail.internId" class="mp-link" @click="goStudent">查看实习学生档案</button>
            </div>
            <div class="mp-card__body">
              <AppDescriptionList :items="studentItems" :columns="2" />
            </div>
          </section>

          <section class="mp-card">
            <div class="mp-card__head"><span class="mp-card__title">处置时间线</span></div>
            <div class="mp-card__body">
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无处置记录" />
            </div>
          </section>

          <div class="ws__actions">
            <template v-if="complaintMode">
              <AppPermissionButton v-if="detail.status === 'RECEIVED'" code="internship.complaint.intake" :allowed="canBtn('internship.complaint.intake')" variant="secondary"
                @click="openComplaintAction('ACCEPT')">受理</AppPermissionButton>
              <AppPermissionButton v-if="detail.status === 'ACCEPTED'" code="internship.complaint.intake" :allowed="canBtn('internship.complaint.intake')" variant="secondary"
                @click="openComplaintAction('INVESTIGATE')">转入调查</AppPermissionButton>
              <AppPermissionButton v-if="['ACCEPTED','INVESTIGATING'].includes(detail.status)" code="internship.complaint.intake" :allowed="canBtn('internship.complaint.intake')" variant="secondary"
                @click="openComplaintAction('RESOLVE')">办结</AppPermissionButton>
              <AppPermissionButton v-if="['RECEIVED','ACCEPTED','INVESTIGATING'].includes(detail.status)" code="internship.complaint.intake" :allowed="canBtn('internship.complaint.intake')" variant="ghost" :danger="true"
                @click="openComplaintAction('REJECT')">判定不成立</AppPermissionButton>
              <AppPermissionButton v-if="detail.studentId && !detail.riskId && ['ACCEPTED','INVESTIGATING','RESOLVED'].includes(detail.status)" code="internship.complaint.intake" :allowed="canBtn('internship.complaint.intake')" variant="ghost"
                @click="openComplaintAction('TO_RISK')">转风险单</AppPermissionButton>
              <AppPermissionButton v-if="['RESOLVED','CLOSED'].includes(detail.status) && !detail.followupResult" code="internship.complaint.intake" :allowed="canBtn('internship.complaint.intake')" variant="secondary"
                @click="openComplaintAction('FOLLOWUP')">完成回访</AppPermissionButton>
              <AppPermissionButton v-if="['RESOLVED','REJECTED'].includes(detail.status)" code="internship.complaint.intake" :allowed="canBtn('internship.complaint.intake')" variant="ghost"
                @click="openComplaintAction('CLOSE')">关闭归档</AppPermissionButton>
              <span v-if="['CLOSED','WITHDRAWN'].includes(detail.status)" class="mp-note">该投诉已终结，仅保留留痕。</span>
            </template>
            <template v-else-if="detail.status === 'PENDING_HANDLE'">
              <AppPermissionButton code="internship.risk.handle" :allowed="canBtn('internship.risk.handle')" variant="secondary"
                @click="openAction('handle')">受理</AppPermissionButton>
            </template>
            <template v-else-if="detail.status === 'PROCESSING'">
              <AppPermissionButton code="internship.risk.handle" :allowed="canBtn('internship.risk.handle')" variant="secondary"
                @click="openAction('follow')">跟进</AppPermissionButton>
              <AppPermissionButton code="internship.risk.handle" :allowed="canBtn('internship.risk.handle')" variant="ghost"
                @click="openAction('remind')">催办</AppPermissionButton>
              <AppPermissionButton v-if="detail.riskLevel !== 'HIGH'" code="internship.risk.handle" :allowed="canBtn('internship.risk.handle')" variant="ghost"
                @click="openAction('escalate')">升级</AppPermissionButton>
              <AppPermissionButton v-if="detail.closeAllowed" code="internship.risk.handle" :allowed="canBtn('internship.risk.handle')" variant="ghost" :danger="true"
                @click="openAction('close')">关闭</AppPermissionButton>
            </template>
            <span v-else class="mp-note">该风险单已关闭归档，仅保留处置留痕。</span>
          </div>
        </template>
      </div>
    </DualPaneWorkspace>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-label="cd.reasonLabel" :submitting="cd.submitting" :confirm-disabled="conflict.active" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="记录已更新，本次操作已暂停" description="填写内容已保留。请取消后核对最新详情，再重新选择可用操作。">
        <p v-if="conflict.stale">最新详情暂时无法读取，请关闭后重试加载。</p>
        <AppDescriptionList v-else :items="conflict.latest" :columns="1" />
      </AppInlineAlert>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppRiskTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
  AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppPagination, AppInlineAlert } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ActionReceipt from './components/ActionReceipt.vue'
import { riskApi, complaintApi } from '@/modules/internship/api/leave-risk.api'
import { canCode } from '@/modules/internship/composables/permission'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { fileSdk } from '@/services/file/fileSdk'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'
import { safeLocalizedText } from '@/utils/presentationSafety'

const LEVEL_OPTIONS = [{ label: '高', value: 'HIGH' }, { label: '中', value: 'MEDIUM' }, { label: '低', value: 'LOW' }]
const STATUS_OPTIONS = [{ label: '待处理', value: 'PENDING_HANDLE' }, { label: '处理中', value: 'PROCESSING' }, { label: '已关闭', value: 'CLOSED' }]
const NEXT_LEVEL = { LOW: 'MEDIUM', MEDIUM: 'HIGH' }
const PANEL_PRESETS = {
  pending: () => ({ levelFilter: '', statusFilter: 'PENDING_HANDLE', riskCode: '' }),
  processing: () => ({ levelFilter: '', statusFilter: 'PROCESSING', riskCode: '' }),
  closed: () => ({ levelFilter: '', statusFilter: 'CLOSED', riskCode: '' }),
  safety: () => ({ levelFilter: '', statusFilter: '', riskCode: 'INT-R16' }),
  interrupt: () => ({ levelFilter: 'HIGH', statusFilter: 'PENDING_HANDLE', riskCode: '' })
}

export default {
  name: 'RiskDisposalView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { AppButton, ModulePageShell, DualPaneWorkspace, LoadingState, ErrorState, EmptyState,
    AppStatusTag, AppRiskTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
    AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppPagination,
    ActionReceipt, AppInlineAlert },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '', listSequence: 0, detailSequence: 0,
      keyword: '', levelFilter: '', statusFilter: '', riskCode: '',
      complaintMode: false,
      levelOptions: LEVEL_OPTIONS, statusOptions: STATUS_OPTIONS,
      evidenceLoading: false, evidenceError: '',
      selectedId: '', detail: null, detailLoading: false, detailError: '', queueDone: false,
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', requireReason: true, submitting: false },
      pending: null,
      lastReceipt: null,
      conflict: emptyConflict(),
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    /** 只渲染 getRiskDetail 真实返回字段（internship_risk_service._row） */
    summaryItems() {
      const d = this.detail || {}
      if (this.complaintMode) return [
        { label: '投诉编号', value: d.complaintNo }, { label: '关联学生', value: d.studentName },
        { label: '当前状态', value: d.statusLabel }, { label: '责任人', value: d.ownerName || d.acceptedByName || '未指派' },
        { label: '投诉内容', value: d.contentMasked ? '当前权限不可查看' : d.content },
        { label: '处理结论', value: d.contentMasked ? '当前权限不可查看' : d.conclusion },
        { label: '回访结果', value: d.contentMasked ? '当前权限不可查看' : d.followupResult },
        { label: '受理期限', value: d.acceptDeadline }, { label: '办结期限', value: d.resolveDeadline },
        { label: '登记时间', value: d.createdAt }
      ]
      return [
        { label: '风险编码', value: d.riskCode },
        { label: '风险标题', value: d.riskTitle },
        { label: '风险等级', value: d.riskLevelLabel },
        { label: '来源模块', value: this.sourceModuleLabel(d.sourceModule) },
        { label: '来源身份', value: d.sourceType && d.sourceId ? `${this.sourceTypeLabel(d.sourceType)} #${d.sourceId}` : '历史未结构化来源' },
        { label: '来源状态', value: d.sourceStatusLabel || (d.sourceStatus ? '状态待确认' : '—') },
        { label: '当前状态', value: d.statusLabel },
        { label: '最近事件', value: d.latestEvent || '—' },
        { label: '当前动作', value: d.currentAction || '—' },
        { label: '当前责任人', value: d.ownerName || '未指派' },
        { label: '创建时间', value: d.createdAt },
        { label: '截止时间', value: d.deadlineAt || '未设置' },
        { label: '最近跟进时间', value: d.lastFollowAt },
        { label: '最近跟进说明', value: d.lastFollowNote }
      ]
    },
    studentItems() {
      const d = this.detail || {}
      return [
        { label: '学生姓名', value: d.studentName },
        { label: '学号', value: d.studentNo },
        { label: '指导教师', value: d.advisorName },
        { label: '实习企业', value: d.enterpriseName || '未关联' }
      ]
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator,
        reason: t.detail && (t.detail.note || t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query': {
      immediate: true,
      deep: true,
      handler(query, previous) {
        const keys = ['panel', 'stage', 'caseType', 'batchId', 'page', 'keyword', 'level', 'status', 'riskCode']
        if (!previous || keys.some(key => String(query[key] ?? '') !== String(previous[key] ?? ''))) this.syncRouteFilters()
        const sid = String(query.id || '')
        if (sid === this.selectedId) return
        this.resetDecision()
        this.selectedId = sid
        if (sid) { this.queueDone = false; this.loadDetail(sid) }
        else { this.detailSequence++; this.detail = null; this.detailLoading = false; this.detailError = '' }
      }
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.clearSelection()
      this.lastReceipt = null
      this.load()
    }
  },
  methods: {
    sourceText(value) { return safeLocalizedText({ value, unknownLabel: '其他风险来源' }) },
    sourceModuleLabel(value) { return safeLocalizedText({ value, dictionary: { INTERNSHIP: '实习管理', ATTENDANCE: '考勤打卡', AGREEMENT: '实习协议', ENTERPRISE: '实习企业', WEEKLY_REPORT: '实习周报', COMPLAINT: '投诉反馈' }, unknownLabel: '其他业务模块' }) },
    sourceTypeLabel(value) { return safeLocalizedText({ value, dictionary: { ATTENDANCE: '考勤记录', AGREEMENT: '实习协议', ENTERPRISE: '实习企业', WEEKLY_REPORT: '实习周报', COMPLAINT: '投诉记录', MANUAL: '人工登记' }, unknownLabel: '业务记录' }) },
    canBtn(code) { return canCode(this.ctx, code) },
    /** navPlan 使用 stage=pending|processing|closed；部分入口仍用 panel= */
    syncRouteFilters() {
      const q = this.$route.query || {}
      const modeChanged = this.complaintMode !== (String(q.caseType || '') === 'complaint')
      if (modeChanged) { this.resetDecision(); this.detail = null; this.detailSequence++ }
      if (String(q.caseType || '') === 'complaint') {
        this.complaintMode = true
        if (modeChanged && q.id) { this.selectedId = String(q.id); this.loadDetail(this.selectedId) }
        this.keyword = ''
        this.page = Math.max(1, Number.parseInt(q.page, 10) || 1)
        this.loadComplaints()
        return
      }
      this.complaintMode = false
      if (modeChanged && q.id) { this.selectedId = String(q.id); this.loadDetail(this.selectedId) }
      const key = (q.panel || q.stage || 'pending').toString()
      this.applyPanel(key)
    },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.pending
      const { levelFilter, statusFilter, riskCode } = preset()
      const q = this.$route.query || {}
      this.levelFilter = q.level != null ? String(q.level) : levelFilter
      this.statusFilter = q.status != null ? String(q.status) : statusFilter
      this.riskCode = q.riskCode != null ? String(q.riskCode) : riskCode
      this.keyword = String(q.keyword || '')
      this.page = Math.max(1, Number.parseInt(q.page, 10) || 1)
      this.queueDone = false
      this.load()
    },
    exportFn() {
      if (!this.batchStore.selectedBatchId || this.complaintMode) return Promise.resolve({ code: 1, message: '请在当前批次风险列表导出' })
      return riskApi.exportRisks({
        keyword: this.keyword, level: this.levelFilter, status: this.statusFilter, riskCode: this.riskCode,
        batchId: this.batchStore.selectedBatchId
      })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    syncListQuery() {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, page: String(this.page) })
      if (!this.complaintMode) Object.assign(query, { keyword: this.keyword, level: this.levelFilter, status: this.statusFilter, riskCode: this.riskCode })
      const current = this.$route.query || {}
      const keys = new Set([...Object.keys(query), ...Object.keys(current)])
      if ([...keys].every(key => Object.hasOwn(query, key) === Object.hasOwn(current, key) && String(query[key] ?? '') === String(current[key] ?? ''))) this.load()
      else this.$router.replace({ query })
    },
    reload() { this.page = 1; this.queueDone = false; this.syncListQuery() },
    onPageChange({ page }) { this.page = page; this.syncListQuery() },
    async load() {
      if (this.complaintMode) return this.loadComplaints()
      const sequence = ++this.listSequence
      const batchId = this.batchStore.selectedBatchId
      this.rows = []; this.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.rows = []
        this.total = 0
        this.error = '请先选择实习批次'
        return
      }
      this.loading = true; this.error = ''
      const params = {
        page: this.page, pageSize: this.pageSize, keyword: this.keyword,
        batchId: this.batchStore.selectedBatchId
      }
      if (this.levelFilter) params.level = this.levelFilter
      if (this.statusFilter) params.status = this.statusFilter
      if (this.riskCode) params.riskCode = this.riskCode
      const res = await riskApi.getRisks(params)
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId || this.complaintMode) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // URL 带 id 时，确保左侧队列也选中该项
      const want = String(this.$route.query.id || this.selectedId || '')
      if (want && this.rows.some((r) => String(r.id) === want)) {
        this.selectedId = want
      }
    },
    async loadComplaints() {
      const sequence = ++this.listSequence
      const batchId = this.batchStore.selectedBatchId
      this.rows = []; this.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.rows = []
        this.total = 0
        this.error = '请先选择实习批次'
        return
      }
      this.loading = true; this.error = ''
      const res = await complaintApi.getComplaints({
        page: this.page, pageSize: this.pageSize, batchId: this.batchStore.selectedBatchId
      })
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId || !this.complaintMode) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '投诉加载失败'; this.rows = []; this.total = 0; return }
      this.rows = (res.data.list || []).map((c) => ({
        ...c,
        studentName: c.studentName || (c.studentId ? `学生#${c.studentId}` : '企业投诉'),
        studentNo: c.complaintNo || '',
        riskCode: c.category || 'COMPLAINT',
        riskTitle: (c.content || '').slice(0, 40),
        riskLevel: c.severity,
        level: c.severity,
        ownerName: c.ownerName || c.acceptedByName || '',
        statusLabel: c.statusLabel,
        deadline: c.resolveDeadline || c.acceptDeadline || '',
        deadlineAt: c.resolveDeadline || c.acceptDeadline || '',
        source: c.category || '企业投诉',
        lastFollow: c.conclusion || '—'
      }))
      this.total = res.data.total || 0
    },
    async loadDetail(id) {
      const sequence = ++this.detailSequence
      const batchId = this.batchStore.selectedBatchId
      const complaintMode = this.complaintMode
      const rid = String(id || '')
      if (!rid) return
      this.evidenceLoading = false; this.evidenceError = ''
      this.detailLoading = true; this.detailError = ''; this.detail = null
      const res = this.complaintMode
        ? await complaintApi.getComplaintDetail(rid)
        : await riskApi.getRiskDetail(rid)
      if (sequence !== this.detailSequence || batchId !== this.batchStore.selectedBatchId || complaintMode !== this.complaintMode || String(this.selectedId) !== rid) return
      this.detailLoading = false
      if (res.code !== 0) { this.detailError = res.message || '加载失败'; return }
      this.detail = res.data
    },
    select(row) {
      if (!row || row.id == null || row.id === '') return
      const id = String(row.id)
      if (id === String(this.selectedId || '')) return
      this.resetDecision()
      this.selectedId = id
      this.queueDone = false
      this.detailError = ''
      this.loadDetail(id)
      if (String(this.$route.query.id || '') !== id) {
        this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id }) })
      }
    },
    resetDecision() {
      this.evidenceLoading = false; this.evidenceError = ''
      this.pending = null; this.cd = { ...this.cd, visible: false, submitting: false }; this.conflict = emptyConflict()
    },
    clearSelection() {
      this.resetDecision(); this.detailSequence++
      this.selectedId = ''; this.detail = null; this.detailLoading = false; this.detailError = ''
      const query = { ...this.$route.query, page: String(this.page) }
      delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    async previewEvidence() {
      const current = this.detail
      if (!this.complaintMode || this.detailLoading || this.detailError || this.evidenceLoading || current?.evidenceMasked || !current?.evidenceFileId) return
      this.evidenceLoading = true; this.evidenceError = ''
      try {
        const result = await fileSdk.preview(String(current.evidenceFileId))
        if (this.detail === current && result?.opened === false) this.evidenceError = '浏览器未打开预览窗口，请允许弹出窗口后重试。'
      } catch (error) {
        if (this.detail === current) this.evidenceError = error.message || '材料暂时无法预览，请重试'
      } finally {
        if (this.detail === current) this.evidenceLoading = false
      }
    },
    goLinkedRisk() {
      if (!this.complaintMode || !this.detail?.riskId) return
      this.$router.push({ path: '/admin/internship/risk-disposal', query: this.batchStore.withBatchQuery({ id: String(this.detail.riskId) }) })
    },
    goStudent() {
      if (this.detail?.internId) {
        this.$router.push({
          path: `/admin/internship/students/${this.detail.internId}`,
          query: this.batchStore.withBatchQuery({})
        })
      }
    },
    goSource() {
      const d = this.detail || {}
      if (d.sourceType === 'INCIDENT') {
        this.$router.push({
          path: '/admin/internship/compliance',
          query: this.batchStore.withBatchQuery({ tab: 'incidents', id: d.sourceId })
        })
      } else if (d.sourceType === 'COMPLAINT') {
        this.$router.push({
          path: '/admin/internship/risk-disposal',
          query: this.batchStore.withBatchQuery({ caseType: 'complaint', id: d.sourceId })
        })
      }
    },
    openAction(kind) {
      if (this.complaintMode) return
      const d = this.detail
      if (!d || this.detailLoading || this.detailError || this.cd.submitting || !this.canBtn('internship.risk.handle') || !d.allowedActions?.includes(kind.toUpperCase())) return
      const map = {
        handle: { title: '受理风险', content: `受理「${d.studentName}」的风险并转入处理中，受理意见将写审计。`, danger: false, confirmText: '受理', reasonLabel: '受理意见（≥5字）', requireReason: true },
        follow: { title: '风险跟进', content: `为「${d.studentName}」追加一条跟进记录。`, danger: false, confirmText: '跟进', reasonLabel: '跟进说明', requireReason: true },
        remind: { title: '催办跟进', content: `向责任人「${d.ownerName || '责任人'}」发送站内催办提醒，催办将写审计。`, danger: false, confirmText: '发送催办', reasonLabel: '', requireReason: false },
        escalate: { title: '风险升级', content: `将「${d.studentName}」风险等级升级为「${d.riskLevel === 'LOW' ? '中' : '高'}」，升级原因将写审计。`, danger: true, confirmText: '升级', reasonLabel: '升级原因', requireReason: true },
        close: { title: '风险关闭', content: `将「${d.studentName}」的风险化解并关闭归档，关闭说明将写审计。`, danger: true, confirmText: '关闭', reasonLabel: '关闭说明（≥5字）', requireReason: true }
      }[kind]
      this.pending = { id: d.id, kind, level: d.riskLevel, mode: 'risk', expectedVersion: d.version }
      this.conflict = emptyConflict()
      this.cd = { visible: true, ...map, submitting: false }
    },
    openComplaintAction(action) {
      const d = this.detail
      if (!d || this.detailLoading || this.detailError || this.cd.submitting || !this.canBtn('internship.complaint.intake')) return
      const map = {
        ACCEPT: { title: '受理投诉', content: `受理投诉「${d.complaintNo || d.id}」，转入已受理。`, danger: false, confirmText: '受理', reasonLabel: '责任人（可空）', requireReason: false },
        INVESTIGATE: { title: '转入调查', content: '将投诉转入调查中。', danger: false, confirmText: '转入调查', reasonLabel: '', requireReason: false },
        RESOLVE: { title: '办结投诉', content: '填写办结结论（不少于 5 字）。', danger: false, confirmText: '办结', reasonLabel: '结论（≥5字）', requireReason: true },
        REJECT: { title: '判定不成立', content: '填写不成立理由（不少于 5 字）。', danger: true, confirmText: '不成立', reasonLabel: '理由（≥5字）', requireReason: true },
        CLOSE: { title: '关闭归档', content: '关闭该投诉并归档。', danger: false, confirmText: '关闭', reasonLabel: '', requireReason: false },
        FOLLOWUP: { title: '投诉回访', content: '记录对投诉人的真实回访结果，完成关闭前的跟进事实。', danger: false, confirmText: '保存回访', reasonLabel: '回访结果', requireReason: true },
        TO_RISK: { title: '转风险单', content: '将本投诉转为实习风险单，保留双向链接。', danger: true, confirmText: '转风险', reasonLabel: '', requireReason: false }
      }[action]
      this.pending = { id: d.id, kind: action, mode: 'complaint', expectedVersion: d.version }
      this.conflict = emptyConflict()
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      if (!p || this.cd.submitting || this.conflict.active || this.detailLoading || this.detailError || String(p.id) !== String(this.selectedId)) return
      if (!this.canBtn(p.mode === 'complaint' ? 'internship.complaint.intake' : 'internship.risk.handle')) return
      const dialog = this.cd
      this.cd.submitting = true
      let res
      try {
        if (p.mode === 'complaint') {
          if (p.kind === 'TO_RISK') res = await complaintApi.toRisk(p.id, p.expectedVersion)
          else if (p.kind === 'FOLLOWUP') res = await complaintApi.followup(p.id, reason, p.expectedVersion)
          else {
            const body = { expectedVersion: p.expectedVersion }
            if (p.kind === 'ACCEPT' && reason) body.ownerName = reason
            if (['RESOLVE', 'REJECT'].includes(p.kind)) body.conclusion = reason
            res = await complaintApi.transition(p.id, p.kind, body)
          }
        } else if (p.kind === 'handle') res = await riskApi.handle(p.id, { comment: reason, expectedVersion: p.expectedVersion })
        else if (p.kind === 'follow') res = await riskApi.follow(p.id, { note: reason, expectedVersion: p.expectedVersion })
        else if (p.kind === 'remind') res = await riskApi.remind(p.id, {})
        else if (p.kind === 'escalate') res = await riskApi.escalate(p.id, { level: NEXT_LEVEL[p.level], note: reason, expectedVersion: p.expectedVersion })
        else res = await riskApi.close(p.id, { result: 'RESOLVED', comment: reason, expectedVersion: p.expectedVersion })
      } finally {
        if (this.cd === dialog) this.cd.submitting = false
      }
      if (this.pending !== p || this.cd !== dialog) return
      if (isConflict(res)) return this.onConflict(res, reason)
      if (!res || res.code !== 0) return toast.error((res && res.message) || '操作失败')
      this.conflict = emptyConflict()
      this.cd.visible = false
      const data = res.data || {}
      this.lastReceipt = {
        id: data.id || p.id, version: data.version,
        actionLabel: this.cd.confirmText || '处置完成',
        objectLabel: p.mode === 'complaint' ? `投诉 ${this.detail?.complaintNo || p.id}` : `风险 ${this.detail?.riskCode || p.id}`,
        status: data.status, statusLabel: data.statusLabel || data.status || '已提交',
        auditText: '业务事实与审计 outbox 已在同一事务提交',
        nextStep: data.nextStep || (data.status === 'CLOSED' ? '生成监管证据包或处理下一条' : '继续处理当前责任链')
      }
      toast.success('操作成功，已写审计')
      if (p.kind === 'close' || p.kind === 'CLOSE') {
        await this.afterClose(p.id)
      } else {
        await this.load()
        if (this.selectedId) this.loadDetail(this.selectedId)
      }
    },
    async onConflict(res, reason) {
      const pending = this.pending
      const dialog = this.cd
      this.conflict = { ...emptyConflict(), active: true, kept: reason || '' }
      const captured = await captureConflict({
        res, kept: reason || '',
        refresh: async () => {
          await this.loadDetail(pending.id)
          if (this.detailError) throw new Error(this.detailError)
        },
        latest: () => {
          const d = this.detail
          if (!d || this.pending !== pending) throw new Error('当前记录已切换或详情未加载')
          return [
            { label: '最新状态', value: d.statusLabel || d.status || '' },
            { label: '当前责任人', value: d.ownerName || d.acceptedByName || '未指派' },
            { label: '最新结论', value: d.conclusion || d.lastFollowNote || '' }
          ]
        }
      })
      if (this.pending === pending && this.cd === dialog) this.conflict = captured
    },
    /** 关闭成功：刷新列表后自动选中下一条未关闭风险；没有则清空选中并提示队列已清 */
    async afterClose(closedId) {
      const batchId = this.batchStore.selectedBatchId
      const complaintMode = this.complaintMode
      const prevIdx = this.rows.findIndex((r) => String(r.id) === String(closedId))
      await this.load()
      if (batchId !== this.batchStore.selectedBatchId || complaintMode !== this.complaintMode || String(this.selectedId) !== String(closedId) || this.error) return
      const terminal = complaintMode ? ['CLOSED', 'WITHDRAWN'] : ['CLOSED', 'RESOLVED']
      const open = this.rows.filter((r) => !terminal.includes(r.status))
      if (!open.length) {
        this.queueDone = true
        this.clearSelection()
        return
      }
      const anchor = prevIdx >= 0 ? prevIdx : 0
      const next = open.find((r) => this.rows.indexOf(r) >= anchor) || open[0]
      this.select(next)
    }
  }
}
</script>

<style scoped>
.evidence-error { color: var(--danger-700, #b42318); font-size: 13px; }
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.state.is-err { color: var(--danger-600); }

/* 左栏：紧凑风险队列 */
.queue { list-style: none; margin: 0; padding: 0; }
.queue__item { display: block; width: 100%; text-align: left; font: inherit; background: transparent; border: 0; padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-light); border-left: 3px solid transparent; cursor: pointer; transition: background 0.12s ease, border-color 0.12s ease; }
.queue__item:hover { background: var(--primary-50); }
.queue__item.is-active { background: var(--primary-50); border-left-color: var(--primary-600); }
.queue__top { display: flex; align-items: center; gap: var(--space-2); }
.queue__lvl { margin-left: auto; }
.queue__src { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue__meta { margin-top: var(--space-1); display: flex; align-items: center; gap: var(--space-2); }
.queue__follow { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 右栏：处置工作台 */
.ws { display: flex; flex-direction: column; gap: var(--space-3); min-height: 320px; }
.ws__tags { display: inline-flex; align-items: center; gap: var(--space-2); }
.ws__actions { position: sticky; bottom: 0; z-index: 1; display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; padding: var(--space-3) var(--space-4); background: var(--bg-card); border: 1px solid var(--border-light); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.ws__blockers { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; padding: 10px 12px; border: 1px solid var(--danger-200, #fecaca); border-radius: 9px; background: var(--danger-50, #fef2f2); color: var(--danger-700, #b91c1c); font-size: 12px; }
</style>
