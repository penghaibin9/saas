<template>
  <ModulePageShell :title="makeupDetail.visible ? '补卡申请' : tabLabel" :subtitle="makeupDetail.visible ? '核对申请事实、材料与历史处理记录后再作决定。' : panelPurpose.description"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton v-if="makeupDetail.visible" variant="ghost" :disabled="dlg.submitting" @click="closeMakeupDetail(false)">返回补卡台账</AppButton>
      <template v-else>
      <AppButton variant="ghost" @click="$router.push({ path: '/admin/internship/leaves', query: batchStore.withBatchQuery() })">请假审批</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">导出 Excel 台账</AppExportButton>
      </template>
    </template>

    <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

    <template v-if="!makeupDetail.visible">
    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <section class="purpose" aria-label="当前办理说明">
      <div>
        <span class="purpose__eyebrow">{{ panelPurpose.step }}</span>
        <strong>{{ panelPurpose.title }}</strong>
        <p>{{ panelPurpose.description }}</p>
      </div>
      <dl>
        <div><dt>当前责任人</dt><dd>{{ panelPurpose.actor }}</dd></div>
        <div><dt>办结结果</dt><dd>{{ panelPurpose.result }}</dd></div>
      </dl>
    </section>

    <div class="tabs" aria-label="出勤业务切换">
      <span class="tabs__caption">出勤处置台</span>
      <div class="tabs__list">
        <button v-for="t in tabs" :key="t.key" class="tabs__btn" :class="{ 'is-active': activePanel === t.key }"
          @click="switchPanel(t.key)">{{ t.label }}</button>
      </div>
    </div>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按姓名搜索" :debounce="0" button @search="search" />
      <AppQuickFilterChips v-if="tab !== 'checkins'" v-model="statusFilter" :options="chipOptions" @change="search" />
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="nextUp" class="nextup">
      <span class="nextup__text">
        处理完了。下一条待处理：<b>{{ nextUp.row.studentName }}</b>
        <span v-if="nextUp.row.checkinDate"> · {{ nextUp.row.checkinDate }}</span>
        （当前筛选下还剩 {{ nextUp.remaining }} 条）
      </span>
      <AppButton variant="secondary" size="sm" @click="openNextUp">继续处理</AppButton>
      <AppButton variant="ghost" size="sm" @click="nextUp = null">先不处理</AppButton>
    </div>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!rows.length" :title="panelPurpose.empty" :description="panelPurpose.emptyHint" />

    <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id"
      :pagination="{ page, pageSize, total }" @page-change="onPageChange">
      <template #cell-status="{ row }">
        <AppStatusTag :status="row.status" />
      </template>
      <template #cell-result="{ row }">
        <AppStatusTag :type="row.tone === 'danger' ? 'danger' : 'success'">{{ row.resultLabel }}</AppStatusTag>
      </template>
      <template #cell-actions="{ row }">
        <div class="tbl__ops">
          <template v-if="tab === 'exceptions' && row.status === 'PENDING_HANDLE'">
            <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')" variant="secondary" size="sm" @click="openExceptionDetail(row)">查看完整证据</AppPermissionButton>
          </template>
          <template v-else-if="tab === 'makeups'">
            <AppPermissionButton code="internship.makeup.view" :allowed="canBtn('internship.makeup.view')" variant="secondary" size="sm" @click="openMakeupDetail(row)">{{ row.status === 'PENDING' ? '核对完整申请' : '查看办理记录' }}</AppPermissionButton>
          </template>
          <span v-else class="tbl__muted">—</span>
        </div>
      </template>
    </DataTable>

    </template>
    <section v-if="makeupDetail.visible" class="makeup-workspace" aria-label="补卡申请与审批证据">
      <LoadingState v-if="makeupDetail.loading" />
      <ErrorState v-else-if="makeupDetail.error" :description="makeupDetail.error" @retry="loadMakeupDetail(makeupDetail.id)" />
      <div v-else-if="makeupDetail.data" class="mk-detail mp-stack">
        <AppDescriptionList :items="makeupSummaryItems" :columns="2" />
        <section class="mk-detail__evidence">
          <div>
            <strong>补卡证据</strong>
            <p>{{ makeupDetail.data.evidenceRequirementLabel }}</p>
          </div>
          <AppStatusTag :type="makeupEvidenceReady ? 'success' : 'warning'">
            {{ makeupEvidenceLabel }}
          </AppStatusTag>
        </section>
        <AppFilePreview v-if="makeupDetail.data.attachment" :files="makeupAttachmentFiles" @download="downloadMakeupEvidence" />
        <p v-else-if="makeupDetail.data.evidenceRequired" class="mk-detail__blocker">按规则必须有证据，当前不可通过。</p>
        <section v-if="makeupDetail.data.previousReviewComment" class="mk-detail__previous">
          <strong>上次退回与本次修正</strong>
          <p>{{ makeupDetail.data.previousReviewComment }} · {{ makeupDetail.data.previousReviewAt || '时间未记录' }}</p>
        </section>
        <section>
          <h3 class="mk-detail__title">审批留痕</h3>
          <AppAuditTrail :records="makeupAuditRecords" :show-ip="false" compact empty-text="暂无审批记录" />
        </section>
      </div>
      <div v-if="!makeupDetail.loading && !makeupDetail.error && makeupDetail.data?.status === 'PENDING'" class="makeup-actions">
        <AppPermissionButton code="internship.makeup.review" :allowed="canBtn('internship.makeup.review')"
          variant="ghost" :danger="true" @click="openReject(makeupDetail.data)">驳回</AppPermissionButton>
        <AppPermissionButton code="internship.makeup.review" :allowed="canBtn('internship.makeup.review')"
          variant="secondary" :disabled="!makeupCanApprove" :native-title="makeupApproveHint"
          @click="openApprove(makeupDetail.data)">通过</AppPermissionButton>
      </div>
    </section>

    <AppConfirmDialog v-model:visible="dlg.visible" :title="dlg.title" :content="dlg.content"
      :danger="dlg.danger" :confirm-text="dlg.confirmText" :require-reason="dlg.requireReason"
      reason-label="处理意见" :submitting="dlg.submitting" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="申请已更新，本次审批已暂停"
        description="请保留需要的审批意见，取消后重新打开补卡申请，核对最新材料再审批。">
        <p v-if="conflict.stale">最新记录读取失败，请重新加载。</p>
      </AppInlineAlert>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppSearchBox,
  AppQuickFilterChips, AppDescriptionList, AppAuditTrail, AppFilePreview, AppInlineAlert } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import ActionReceipt from './components/ActionReceipt.vue'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { pickNextPending, anchorIndexOf, saveReviewQueue } from '@/modules/internship/composables/reviewQueue'
import { restoreWorkContext, captureWorkContext } from '@/modules/internship/composables/workContext'
import { attendanceApi } from '@/modules/internship/api/attendance.api'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

// U8：页签由 URL 的 panel 承载，这里补上 applyPanel 会重置掉的关键词/状态/页码
const WORK_FIELDS = ['keyword', 'statusFilter', 'page']

const COLS = {
  checkins: [
    { key: 'studentNo', label: '学号' }, { key: 'studentName', label: '姓名' },
    { key: 'advisorName', label: '指导教师' }, { key: 'date', label: '打卡日期' },
    { key: 'at', label: '打卡时间' }, { key: 'result', label: '结果' }, { key: 'address', label: '地址' }
  ],
  exceptions: [
    { key: 'studentName', label: '姓名' }, { key: 'className', label: '班级' },
    { key: 'typeLabel', label: '异常类型' }, { key: 'date', label: '异常时间' },
    { key: 'distance', label: '距离' }, { key: 'status', label: '处理状态' }
  ],
  makeups: [
    { key: 'studentNo', label: '学号' }, { key: 'studentName', label: '姓名' },
    { key: 'advisorName', label: '指导教师' }, { key: 'checkinDate', label: '补卡日期' },
    { key: 'reason', label: '事由' }, { key: 'status', label: '状态' }
  ]
}
const STATUS_OPTS = {
  exceptions: [{ value: 'PENDING_HANDLE', label: '待核实' }, { value: 'COMPLETED', label: '已处理' }],
  makeups: [{ value: 'PENDING', label: '待审核' }, { value: 'APPROVED', label: '已通过' },
    { value: 'REJECTED', label: '已驳回' }, { value: 'WITHDRAWN', label: '已撤回' }]
}
const PANEL_PRESETS = {
  checkins: () => ({ tab: 'checkins', statusFilter: '' }),
  'makeup-apply': () => ({ tab: 'makeups', statusFilter: '' }),
  'makeup-review': () => ({ tab: 'makeups', statusFilter: 'PENDING' }),
  exceptions: () => ({ tab: 'exceptions', statusFilter: '' })
}
export default {
  name: 'AttendanceView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton,
    AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppSearchBox, AppQuickFilterChips,
    AppDescriptionList, AppAuditTrail, AppFilePreview, ModuleSummaryStrip, AppInlineAlert, ActionReceipt },
  data() {
    return {
      tab: 'checkins',
      activePanel: 'checkins',
      tabs: [
        { key: 'checkins', label: '考勤记录' },
        { key: 'exceptions', label: '异常核验' },
        { key: 'makeup-apply', label: '补卡申请台账' },
        { key: 'makeup-review', label: '补卡审批' }
      ],
      loadSeq: 0, rows: [], total: 0, page: 1, pageSize: 50, loading: false, error: '',
      tabTotals: { checkins: null, exceptions: null, makeupsAll: null, makeupsPending: null },
      keyword: '', statusFilter: '',
      dlg: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: true, submitting: false },
      pending: null,
      conflict: emptyConflict(),
      lastReceipt: null,
      makeupDetail: { visible: false, id: '', loading: false, error: '', data: null },
      // 处理完一条后指向下一条待办；不自动弹窗，由老师点「继续处理」再开，
      // 避免刚确认完 A 的手速直接把 B 也点掉。
      nextUp: null,
      workContextReady: false,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    columns() { return COLS[this.tab] },
    statusOptions() { return STATUS_OPTS[this.tab] || [] },
    chipOptions() { return [{ label: '全部状态', value: '' }, ...this.statusOptions] },
    tableColumns() { const columns = this.columns.map((c) => ({ key: c.key, title: c.label })); return this.tab === 'checkins' ? columns : [...columns, { key: 'actions', title: '操作' }] },
    tabLabel() { return this.tabs.find((item) => item.key === this.activePanel)?.label || '考勤记录' },
    panelPurpose() {
      return {
        checkins: { step: '01 · 考勤事实', title: '先看真实打卡结果', description: '按当前批次查询学生打卡时间、结果与地点；异常记录转入独立核验工作区。', actor: '指导教师 / 学校管理员只读核对', result: '确认考勤事实，异常进入核验', empty: '当前没有考勤记录', emptyHint: '学生完成打卡或补卡通过后，记录会出现在这里。' },
        exceptions: { step: '02 · 异常核验', title: '逐条核对异常证据', description: '从薄表进入完整证据页，核对定位、设备和学生说明后再定性。', actor: '有考勤核验权限的教师', result: '合理说明、确认异常或转风险', empty: '当前没有待核验异常', emptyHint: '可切换“已处理”回看历史处置记录。' },
        'makeup-apply': { step: '03 · 申请台账', title: '查看全部补卡申请', description: '按状态回看学生申请、证据和审批结果；该入口保留完整台账口径。', actor: '指导教师 / 学校管理员查询', result: '申请过程可追溯、结果可回读', empty: '当前没有补卡申请', emptyHint: '学生提交补卡后会进入本台账。' },
        'makeup-review': { step: '04 · 补卡审批', title: '集中办理待审补卡', description: '先读完整申请与当前版本证据，再通过补写打卡或驳回给学生修改。', actor: '有补卡审批权限的教师', result: '补写打卡或退回学生', empty: '当前没有待审补卡', emptyHint: '本批次待办已清空，可到申请台账回看结果。' }
      }[this.activePanel] || {}
    },
    makeupSummaryItems() {
      const d = this.makeupDetail.data || {}
      return [
        { label: '学生', value: `${d.studentName || '-'} · ${d.studentNo || '-'}` },
        { label: '指导教师', value: d.advisorName || '-' },
        { label: '补卡日期', value: d.checkinDate || '-' },
        { label: '补卡类型', value: d.makeupTypeLabel || d.makeupType || '-' },
        { label: '申请理由', value: d.reason || '-' },
        { label: '申请时间', value: d.submittedAt || d.createdAt || '-' },
        { label: '当前状态', value: d.statusLabel || d.status || '-' },
        { label: '服务端版本', value: d.version == null ? '-' : `v${d.version}` }
      ]
    },
    makeupAttachmentFiles() {
      const a = this.makeupDetail.data?.attachment
      return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : []
    },
    makeupAuditRecords() {
      return (this.makeupDetail.data?.auditTrail || []).map((item, index) => ({
        id: index, action: item.action, actor: item.operator,
        reason: item.detail?.comment || '', at: item.occurredAt
      }))
    },
    makeupEvidenceReady() {
      const d = this.makeupDetail.data
      if (!d || (d.evidenceRequired && !d.hasEvidence)) return false
      return !d.hasEvidence || !!d.evidenceViewed
    },
    makeupEvidenceLabel() {
      const d = this.makeupDetail.data
      if (!d) return '待读取'
      if (d.evidenceRequired && !d.hasEvidence) return '缺少必需证据'
      if (!d.hasEvidence) return '按规则无需附件'
      return d.evidenceViewed ? '已核对当前版本' : '待核对'
    },
    makeupCanApprove() {
      const d = this.makeupDetail.data
      if (!d) return false
      if (d.evidenceRequired && !d.hasEvidence) return false
      return !d.hasEvidence || !!d.evidenceViewed
    },
    makeupApproveHint() {
      const d = this.makeupDetail.data
      if (!d) return ''
      if (d.evidenceRequired && !d.hasEvidence) return '按规则必须上传证据，当前不可通过'
      if (d.hasEvidence && !d.evidenceViewed) return '请先下载并核对当前版本证据'
      return ''
    },
    summaryMetrics() {
      // 只展示已真实加载过的 Tab 的服务端 total，不触发额外请求，不用分页行数冒充
      const t = this.tabTotals
      const m = []
      if (t.checkins != null) m.push({ label: '打卡记录', value: t.checkins })
      if (t.exceptions != null) m.push({ label: '打卡异常', value: t.exceptions, tone: 'warn' })
      if (t.makeupsPending != null) m.push({ label: '补卡待审批', value: t.makeupsPending })
      else if (t.makeupsAll != null) m.push({ label: '补卡申请', value: t.makeupsAll })
      return m
    }
  },
  created() {
    // immediate watcher 会先按 URL 页签加载默认条件，但首次 load 不得覆盖已有工作上下文。
    // 菜单/待办给出的 panel 与 makeupId 是显式深链，必须优先于上一次筛选缓存。
    const restored = restoreWorkContext(this, WORK_FIELDS, { skipWhenQuery: ['panel', 'makeupId'] })
    this.workContextReady = true
    if (restored) this.load()
  },
  watch: {
    'batchStore.selectedBatchId'(value, previous) {
      if (value === previous) return
      this.resetBatchView()
    },
    '$route.query.makeupId': {
      immediate: true,
      handler(id) {
        this.pending = null; this.dlg.visible = false; this.conflict = emptyConflict()
        if (id != null) { this.lastReceipt = null; this.nextUp = null }
        if (id == null) { this.makeupDetail = { visible: false, id: '', loading: false, error: '', data: null }; return }
        this.makeupDetail = { visible: true, id: String(id), loading: true, error: '', data: null }
        this.loadMakeupDetail(String(id))
      }
    },
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'checkins').toString())
      }
    }
  },
  methods: {
    resetBatchView() {
      this.loadSeq++
      this.makeupDetail = { visible: false, id: '', loading: false, error: '', data: null }
      this.pending = null; this.dlg.visible = false; this.conflict = emptyConflict()
      this.lastReceipt = null; this.nextUp = null
      this.tabTotals = { checkins: null, exceptions: null, makeupsAll: null, makeupsPending: null }
      this.page = 1
      if (this.$route.query.makeupId != null) {
        const query = { ...this.$route.query }; delete query.makeupId
        this.$router.replace({ path: this.$route.path, query })
      }
      this.load()
    },
    canBtn(code) { return canCode(this.ctx, code) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.checkins
      const { tab, statusFilter } = preset()
      this.activePanel = Object.prototype.hasOwnProperty.call(PANEL_PRESETS, panel) ? panel : 'checkins'
      this.tab = tab
      this.keyword = ''
      this.statusFilter = statusFilter
      this.page = 1
      this.load()
    },
    search() { this.nextUp = null; this.page = 1; this.load() },
    onPageChange(p) { this.nextUp = null; this.page = p; this.load() },
    switchPanel(panel) {
      this.nextUp = null
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
      } else {
        this.applyPanel(panel)
      }
    },
    async load() {
      if (this.workContextReady) captureWorkContext(this, WORK_FIELDS)
      const seq = ++this.loadSeq
      const tab = this.tab
      const batchId = this.batchStore.selectedBatchId
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.status = this.statusFilter
      const api = { checkins: 'getCheckins', exceptions: 'getExceptions', makeups: 'getMakeups' }[this.tab]
      const res = await attendanceApi[api](params)
      if (seq !== this.loadSeq || tab !== this.tab || batchId !== this.batchStore.selectedBatchId) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // 无关键词筛选时，缓存该 Tab 的服务端全量计数（补卡区分「全部/待审批」两种口径）
      if (!this.keyword) {
        if (this.tab === 'checkins' && !this.statusFilter) this.tabTotals.checkins = res.data.total
        else if (this.tab === 'exceptions' && !this.statusFilter) this.tabTotals.exceptions = res.data.total
        else if (this.tab === 'makeups' && !this.statusFilter) this.tabTotals.makeupsAll = res.data.total
        else if (this.tab === 'makeups' && this.statusFilter === 'PENDING') this.tabTotals.makeupsPending = res.data.total
      }
    },
    exportFn() {
      const api = { checkins: 'exportCheckins', exceptions: 'exportExceptions', makeups: 'exportMakeups' }[this.tab]
      return attendanceApi[api]({ keyword: this.keyword, status: this.statusFilter, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（脱敏 + 水印，已写审计）`) },
    openExceptionDetail(row) {
      const pendingRows = this.rows.filter((item) => item.status === 'PENDING_HANDLE')
      const query = { ...this.$route.query, batchId: this.batchStore.selectedBatchId }
      saveReviewQueue({
        kind: 'attendance-exception', title: '打卡异常核实', listPath: this.$route.path,
        listQuery: query, ids: (pendingRows.length ? pendingRows : this.rows).map((item) => item.id)
      })
      this.$router.push({ path: `/admin/internship/exceptions/${row.id}`, query })
    },
    openMakeupDetail(row) {
      this.$router.push({ path: this.$route.path, query: { ...this.$route.query, makeupId: String(row.id) } })
    },
    closeMakeupDetail(visible) {
      if (visible !== false || this.dlg.submitting) return
      const query = { ...this.$route.query }; delete query.makeupId
      this.$router.push({ path: this.$route.path, query })
      this.makeupDetail = { visible: false, id: '', loading: false, error: '', data: null }
    },
    async loadMakeupDetail(id) {
      const sid = String(id || this.makeupDetail.id)
      const batchId = this.batchStore.selectedBatchId
      const target = this.makeupDetail
      this.makeupDetail.loading = true; this.makeupDetail.error = ''; this.makeupDetail.data = null
      const res = await attendanceApi.getMakeupDetail(sid)
      if (this.makeupDetail !== target || String(this.makeupDetail.id) !== sid || batchId !== this.batchStore.selectedBatchId) return
      this.makeupDetail.loading = false
      if (res.code !== 0) { this.makeupDetail.error = res.message || '补卡详情加载失败'; return }
      this.makeupDetail.data = res.data
    },
    async downloadMakeupEvidence() {
      const d = this.makeupDetail.data
      const a = d?.attachment
      if (!a) return
      try {
        await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName)
        if (this.makeupDetail.data !== d) return
        const viewed = await attendanceApi.markMakeupEvidenceViewed(d.id)
        if (this.makeupDetail.data !== d) return
        if (viewed.code !== 0) return toast.error(viewed.message || '证据已下载，但查看留痕失败')
        this.makeupDetail.data = { ...d, evidenceViewed: true }
        const row = this.rows.find((item) => String(item.id) === String(d.id))
        if (row) row.evidenceViewed = true
        toast.success('证据已下载，当前版本查看动作已留痕')
      } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openApprove(r) {
      if (!this.canBtn('internship.makeup.review') || !this.makeupCanApprove) return
      this.conflict = emptyConflict()
      this.pending = { kind: 'approve', id: r.id, expectedVersion: r.version, studentName: r.studentName, checkinDate: r.checkinDate }
      this.dlg = { visible: true, title: '补卡 · 通过', content: `通过「${r.studentName}」${r.checkinDate} 的补卡，将真实补写一条打卡留痕并写审计。`,
        danger: false, confirmText: '通过', requireReason: false, submitting: false }
    },
    openReject(r) {
      if (!this.canBtn('internship.makeup.review') || r.status !== 'PENDING') return
      this.conflict = emptyConflict()
      this.pending = { kind: 'reject', id: r.id, expectedVersion: r.version, studentName: r.studentName, checkinDate: r.checkinDate }
      this.dlg = { visible: true, title: '补卡 · 驳回', content: `驳回「${r.studentName}」${r.checkinDate} 的补卡，原因将写入审计。`,
        danger: true, confirmText: '驳回', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      if (this.dlg.submitting || !this.pending || this.conflict.active || !this.canBtn('internship.makeup.review')) return
      const p = this.pending
      const batchId = this.batchStore.selectedBatchId
      const ver = { expectedVersion: p.expectedVersion }
      this.dlg.submitting = true
      let res
      if (p.kind === 'approve') res = await attendanceApi.approveMakeup(p.id, { comment: reason, ...ver })
      else res = await attendanceApi.rejectMakeup(p.id, { comment: reason, ...ver })
      this.dlg.submitting = false
      if (this.pending !== p || batchId !== this.batchStore.selectedBatchId) return
      if (isConflict(res)) {
        // 撞车：处理意见原样留着，只把最新真值摆出来让老师重新决定
        this.conflict = { ...emptyConflict(), active: true }
        const captured = await captureConflict({
          res,
          refresh: () => this.load(),
          latest: () => {
            const fresh = this.rows.find((r) => String(r.id) === String(p.id))
            if (!fresh) throw new Error('这条记录已不在当前列表里')
            return [
              { label: '最新状态', value: fresh.statusLabel || fresh.status || '' },
              { label: '最新版本', value: fresh.version }
            ]
          }
        })
        if (this.pending === p && batchId === this.batchStore.selectedBatchId) this.conflict = captured
        return
      }
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.dlg.visible = false
      this.conflict = emptyConflict()
      this.lastReceipt = {
        id: res.data?.id, status: res.data?.status, statusLabel: res.data?.statusLabel,
        version: res.data?.version, actionLabel: p.kind === 'approve' ? '补卡通过' : '补卡驳回',
        objectLabel: `${p.studentName || '学生'} · ${p.checkinDate || '补卡申请'}`,
        auditText: '补卡更新与审批留痕已同事务提交', nextStep: '可按当前筛选继续办理下一份补卡'
      }
      this.makeupDetail = { visible: false, id: '', loading: false, error: '', data: null }
      this.closeMakeupDetail(false)
      toast.success('操作成功，已写审计')
      await this.advanceAfterHandle(p)
    },
    /** 当前页签里还需要处理的状态：异常是 PENDING_HANDLE，补卡是 PENDING */
    isRowPending(row) {
      if (this.tab === 'exceptions') return row.status === 'PENDING_HANDLE'
      if (this.tab === 'makeups') return row.status === 'PENDING'
      return false
    },
    /**
     * 处理完一条后刷新并指向下一条待办：筛选、页码、页签全部原样不动。
     * 只给入口不自动弹窗——弹窗里换的是另一个学生，自动打开容易误点。
     */
    async advanceAfterHandle(done) {
      const anchor = anchorIndexOf(this.rows, done.id)
      await this.load()
      const next = pickNextPending(this.rows, anchor, done.id, (r) => this.isRowPending(r))
      if (!next) { this.nextUp = null; return }
      const remaining = this.rows.filter((r) => this.isRowPending(r)).length
      this.nextUp = { row: next, kind: done.kind, remaining }
    },
    /** 点「继续处理」先打开下一份完整材料，核对后再选择审批动作 */
    openNextUp() {
      const up = this.nextUp
      if (!up) return
      this.nextUp = null
      this.openMakeupDetail(up.row)
    }
  }
}
</script>

<style scoped>
.makeup-workspace { padding:24px; border:1px solid var(--card-b); border-radius:12px; background:var(--card, white); }
.makeup-actions { display:flex; justify-content:flex-end; gap:12px; padding-top:20px; margin-top:20px; border-top:1px solid var(--card-b); }
.purpose { display:grid; grid-template-columns:minmax(0,1.35fr) minmax(320px,.85fr); gap:24px; margin-bottom:var(--space-3); padding:18px 20px; border:1px solid var(--card-b); border-radius:12px; background:linear-gradient(120deg,var(--card),var(--pri-bg)); }
.purpose__eyebrow { display:block; margin-bottom:5px; color:var(--pri); font-size:11px; font-weight:700; letter-spacing:.04em; }
.purpose strong { display:block; color:var(--t1); font-size:18px; }
.purpose p { margin:7px 0 0; color:var(--t3); font-size:13px; line-height:1.65; }
.purpose dl { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:0; }
.purpose dl div { padding:10px 12px; border:1px solid rgba(80,110,160,.12); border-radius:9px; background:rgba(255,255,255,.76); }
.purpose dt { color:var(--t3); font-size:11px; }
.purpose dd { margin:5px 0 0; color:var(--t1); font-size:13px; font-weight:600; line-height:1.45; }

.mk-detail__evidence { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border: 1px solid var(--card-b); border-radius: 10px; background: var(--fill-2,#f8fafc); }.mk-detail__evidence p,.mk-detail__previous p { margin: 4px 0 0; color: var(--t3); font-size: 12px; }.mk-detail__blocker { margin: 0; padding: 10px 12px; border-radius: 8px; background: var(--danger-50,#fef2f2); color: var(--danger-700,#b91c1c); font-size: 12px; }.mk-detail__previous { padding: 12px; border-left: 3px solid var(--warning-500,#f59e0b); border-radius: 8px; background: var(--warning-50,#fffbeb); }.mk-detail__title { margin: 0 0 8px; color: var(--t2); font-size: 13px; }
.tabs { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 10px 12px; margin-bottom: var(--space-3); border: 1px solid var(--card-b); border-radius: var(--r); background: linear-gradient(100deg, var(--pri-bg), var(--card)); box-shadow: var(--s1); }
.tabs__caption { color: var(--t2); font-size: 12px; font-weight: var(--font-weight-semibold); white-space: nowrap; }
.tabs__list { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: rgba(255, 255, 255, .7); }
.tabs__btn { border: 1px solid transparent; border-radius: 7px; background: transparent; padding: 6px 12px; cursor: pointer; color: var(--text-secondary); font-size: var(--font-size-sm); transition: .16s ease; }
.tabs__btn:hover { color: var(--pri); background: var(--pri-bg); }
.tabs__btn.is-active { color: var(--pri); border-color: var(--pri-100); background: var(--card); font-weight: var(--font-weight-semibold); box-shadow: 0 2px 5px rgba(15, 40, 90, .08); }
.bar { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); padding: 10px 12px; border: 1px solid var(--card-b); border-radius: 12px; background: var(--card); box-shadow: var(--s1); flex-wrap: wrap; }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.tbl__muted { color: var(--text-disabled); }
.nextup { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-3);
  padding: 10px 12px; border: 1px solid var(--success-100, #d1fae5); border-radius: 12px; background: var(--success-50, #ecfdf5); }
.nextup__text { flex: 1 1 auto; font-size: var(--font-size-sm); color: var(--text-secondary); }
.nextup__text b { color: var(--text-primary); }
.tbl__ops { display: flex; gap: var(--space-1); align-items: center; }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
@media (max-width: 900px) { .purpose { grid-template-columns:1fr; } }
@media (max-width: 760px) { .tabs { align-items: flex-start; flex-direction: column; } .tabs__list { width: 100%; overflow-x: auto; } .tabs__btn { flex: 0 0 auto; } .bar__hint { width: 100%; margin-left: 0; } .purpose dl { grid-template-columns:1fr; } }
</style>
