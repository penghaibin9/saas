<template>
  <ModulePageShell title="打卡请假处理" subtitle="查看学生出勤情况，集中处理缺卡、定位异常、请假和超期未归 · 打卡台账 · 打卡异常 · 补卡审批 · 实习请假"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/leaves')">请假审批</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

    <section v-if="!error" class="att-now" aria-label="当前考勤办理对象">
      <header class="att-now__head">
        <div>
          <span>ATTENDANCE NOW</span>
          <h2>{{ nowTitle }}</h2>
          <p>{{ nowDescription }}</p>
        </div>
        <b>{{ tabLabel }}</b>
      </header>
      <div v-if="loading" class="att-now__state">正在读取当前考勤对象…</div>
      <div v-else-if="priorityRows.length" class="att-now__list">
        <article v-for="row in priorityRows" :key="row.id" class="att-now__item">
          <div class="att-now__identity">
            <small>{{ row.studentNo || row.className || '当前数据范围' }} · v{{ row.version ?? '-' }}</small>
            <strong>{{ row.studentName }} · {{ row.checkinDate || row.date }}</strong>
            <span>{{ attendanceObjectLabel(row) }}</span>
          </div>
          <dl>
            <div><dt>为什么到这里</dt><dd>{{ attendanceWhy(row) }}</dd></div>
            <div><dt>判定事实</dt><dd>{{ attendanceFacts(row) }}</dd></div>
            <div><dt>下一责任人</dt><dd>{{ attendanceNextActor(row) }}</dd></div>
          </dl>
          <AppButton v-if="tab === 'exceptions'" variant="primary" size="sm" @click="openExceptionDetail(row)">查看完整证据 →</AppButton>
          <AppButton v-else-if="tab === 'makeups'" variant="primary" size="sm" @click="openMakeupDetail(row)">核对完整申请 →</AppButton>
          <span v-else class="att-now__readonly">事实只读</span>
        </article>
      </div>
      <div v-else class="att-now__state">当前筛选没有可办理对象，可切换状态或业务页签。</div>
    </section>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div class="tabs" aria-label="出勤业务切换">
      <span class="tabs__caption">出勤处置台</span>
      <div class="tabs__list">
        <button v-for="t in tabs" :key="t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }"
          @click="switchTab(t.key)">{{ t.label }}</button>
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
    <EmptyState v-else-if="!rows.length" title="暂无数据" />

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
          <template v-else-if="tab === 'makeups' && row.status === 'PENDING'">
            <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')" variant="secondary" size="sm" @click="openMakeupDetail(row)">核对完整申请</AppPermissionButton>
          </template>
          <span v-else class="tbl__muted">—</span>
        </div>
      </template>
    </DataTable>

    <AppDrawer :visible="makeupDetail.visible" title="补卡申请 · 完整证据" mode="modal" size="large"
      @update:visible="closeMakeupDetail">
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
      <template v-if="makeupDetail.data?.status === 'PENDING'" #footer>
        <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')"
          variant="ghost" :danger="true" @click="openReject(makeupDetail.data)">驳回</AppPermissionButton>
        <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')"
          variant="secondary" :disabled="!makeupCanApprove" :native-title="makeupApproveHint"
          @click="openApprove(makeupDetail.data)">通过</AppPermissionButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="dlg.visible" :title="dlg.title" :content="dlg.content"
      :danger="dlg.danger" :confirm-text="dlg.confirmText" :require-reason="dlg.requireReason"
      reason-label="处理意见" :submitting="dlg.submitting" @confirm="onConfirm">
      <ConflictNotice :state="conflict" />
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppSearchBox,
  AppQuickFilterChips, AppDescriptionList, AppAuditTrail, AppFilePreview } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import ConflictNotice from './components/ConflictNotice.vue'
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
const TAB_PANEL = { checkins: 'checkins', exceptions: 'exceptions', makeups: 'makeup-review' }

export default {
  name: 'AttendanceView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer,
    AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppSearchBox, AppQuickFilterChips,
    AppDescriptionList, AppAuditTrail, AppFilePreview, ModuleSummaryStrip, ConflictNotice, ActionReceipt },
  data() {
    return {
      tab: 'checkins',
      tabs: [{ key: 'checkins', label: '打卡台账' }, { key: 'exceptions', label: '打卡异常' }, { key: 'makeups', label: '补卡审批' }],
      rows: [], total: 0, page: 1, pageSize: 50, loading: false, error: '',
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
    tableColumns() { return [...this.columns.map((c) => ({ key: c.key, title: c.label })), { key: 'actions', title: '操作' }] },
    priorityRows() {
      const pending = this.rows.filter((row) => this.isRowPending(row))
      return (pending.length ? pending : this.rows).slice(0, 3)
    },
    tabLabel() { return this.tabs.find((item) => item.key === this.tab)?.label || '考勤工作台' },
    nowTitle() {
      return this.tab === 'exceptions' ? `先核对这 ${this.priorityRows.length} 条真实异常`
        : this.tab === 'makeups' ? `先办理这 ${this.priorityRows.length} 份补卡申请`
          : `最近 ${this.priorityRows.length} 条打卡事实`
    },
    nowDescription() {
      return this.tab === 'exceptions' ? '薄表不做最终判定；进入完整详情核对定位、设备、学生说明与审计后再处理。'
        : this.tab === 'makeups' ? '先核对日期、理由、当前版本、历史退回与证据，再决定通过或驳回。'
          : '按当前服务端结果只读展示；异常与补卡分别进入各自命令主页面。'
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
    const restored = restoreWorkContext(this, WORK_FIELDS)
    this.workContextReady = true
    if (restored) this.load()
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'checkins').toString())
      }
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.checkins
      const { tab, statusFilter } = preset()
      this.tab = tab
      this.keyword = ''
      this.statusFilter = statusFilter
      this.page = 1
      this.load()
    },
    search() { this.nextUp = null; this.page = 1; this.load() },
    onPageChange(p) { this.nextUp = null; this.page = p; this.load() },
    switchTab(k) {
      this.nextUp = null
      const panel = TAB_PANEL[k] || k
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
      } else {
        this.applyPanel(panel)
      }
    },
    async load() {
      if (this.workContextReady) captureWorkContext(this, WORK_FIELDS)
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.status = this.statusFilter
      const api = { checkins: 'getCheckins', exceptions: 'getExceptions', makeups: 'getMakeups' }[this.tab]
      const res = await attendanceApi[api](params)
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
    attendanceObjectLabel(row) {
      if (this.tab === 'exceptions') return `${row.typeLabel || '打卡异常'} · ${row.statusLabel || row.status || '待核实'}`
      if (this.tab === 'makeups') return `${row.makeupTypeLabel || '补卡'} · ${row.statusLabel || row.status || '待审核'}`
      return `${row.resultLabel || row.result || '打卡记录'} · ${row.address || '地址未记录'}`
    },
    attendanceWhy(row) {
      if (this.tab === 'exceptions') return row.status === 'PENDING_HANDLE' ? '该异常等待完整证据核实，薄表不可直接定性' : '该异常已处理，可回看完整留痕'
      if (this.tab === 'makeups') return row.status === 'PENDING' ? '学生补卡申请等待指导教师审核' : '该补卡已有终态，可核对历史审批'
      return '这是当前筛选下最近一条服务端打卡事实'
    },
    attendanceFacts(row) {
      if (this.tab === 'exceptions') return [row.distance, row.typeLabel, row.className].filter(Boolean).join(' · ') || '需进入详情读取定位与设备事实'
      if (this.tab === 'makeups') {
        const evidence = row.hasEvidence ? (row.evidenceViewed ? '证据已核对' : '证据待核对') : (row.evidenceRequired ? '缺必需证据' : '无附件')
        return `${row.reason || '未填写理由'} · ${evidence}`
      }
      return [row.at, row.resultLabel || row.result, row.address].filter(Boolean).join(' · ') || '打卡事实待核对'
    },
    attendanceNextActor(row) {
      if (this.tab === 'exceptions') return row.status === 'PENDING_HANDLE' ? '本人指导教师 / 管理员' : '无需继续处理'
      if (this.tab === 'makeups') return row.status === 'PENDING' ? '本人指导教师 / 管理员' : '学生查看结果'
      return row.result === 'NORMAL' || row.tone !== 'danger' ? '无需处理' : '异常核验人'
    },
    openExceptionDetail(row) {
      const pendingRows = this.rows.filter((item) => item.status === 'PENDING_HANDLE')
      saveReviewQueue({
        kind: 'attendance-exception', title: '打卡异常核实', listPath: this.$route.path,
        listQuery: { ...this.$route.query }, ids: (pendingRows.length ? pendingRows : this.rows).map((item) => item.id)
      })
      this.$router.push({ path: `/admin/internship/exceptions/${row.id}`, query: this.batchStore.withBatchQuery() })
    },
    async openMakeupDetail(row) {
      this.makeupDetail = { visible: true, id: String(row.id), loading: true, error: '', data: null }
      await this.loadMakeupDetail(row.id)
    },
    closeMakeupDetail(visible) {
      if (visible === false) this.makeupDetail = { visible: false, id: '', loading: false, error: '', data: null }
    },
    async loadMakeupDetail(id) {
      const sid = String(id || this.makeupDetail.id)
      this.makeupDetail.loading = true; this.makeupDetail.error = ''
      const res = await attendanceApi.getMakeupDetail(sid)
      if (String(this.makeupDetail.id) !== sid) return
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
        const viewed = await attendanceApi.markMakeupEvidenceViewed(d.id)
        if (viewed.code !== 0) return toast.error(viewed.message || '证据已下载，但查看留痕失败')
        this.makeupDetail.data = { ...d, evidenceViewed: true }
        const row = this.rows.find((item) => String(item.id) === String(d.id))
        if (row) row.evidenceViewed = true
        toast.success('证据已下载，当前版本查看动作已留痕')
      } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openApprove(r) {
      this.conflict = emptyConflict()
      this.pending = { kind: 'approve', id: r.id, expectedVersion: r.version, studentName: r.studentName, checkinDate: r.checkinDate }
      this.dlg = { visible: true, title: '补卡 · 通过', content: `通过「${r.studentName}」${r.checkinDate} 的补卡，将真实补写一条打卡留痕并写审计。`,
        danger: false, confirmText: '通过', requireReason: false, submitting: false }
    },
    openReject(r) {
      this.conflict = emptyConflict()
      this.pending = { kind: 'reject', id: r.id, expectedVersion: r.version, studentName: r.studentName, checkinDate: r.checkinDate }
      this.dlg = { visible: true, title: '补卡 · 驳回', content: `驳回「${r.studentName}」${r.checkinDate} 的补卡，原因将写入审计。`,
        danger: true, confirmText: '驳回', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      const ver = { expectedVersion: p.expectedVersion }
      this.dlg.submitting = true
      let res
      if (p.kind === 'approve') res = await attendanceApi.approveMakeup(p.id, { comment: reason, ...ver })
      else res = await attendanceApi.rejectMakeup(p.id, { comment: reason, ...ver })
      this.dlg.submitting = false
      if (isConflict(res)) {
        // 撞车：处理意见原样留着，只把最新真值摆出来让老师重新决定
        this.conflict = await captureConflict({
          res,
          refresh: () => this.load(),
          latest: () => {
            const fresh = this.rows.find((r) => String(r.id) === String(p.id))
            if (!fresh) throw new Error('这条记录已不在当前列表里')
            this.pending.expectedVersion = fresh.version
            return [
              { label: '最新状态', value: fresh.statusLabel || fresh.status || '' },
              { label: '最新版本', value: fresh.version }
            ]
          }
        })
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
    /** 点「继续处理」才真正打开下一条的确认弹窗（弹窗重开会清空上一条的处理意见） */
    openNextUp() {
      const up = this.nextUp
      if (!up) return
      this.nextUp = null
      if (up.kind === 'reject') this.openReject(up.row)
      else this.openApprove(up.row)
    }
  }
}
</script>

<style scoped>
.att-now { overflow: hidden; margin-bottom: var(--space-3); border: 1px solid color-mix(in srgb, var(--pri) 24%, var(--card-b)); border-radius: 14px; background: var(--card); box-shadow: 0 14px 38px rgba(30,64,175,.08); }
.att-now__head { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; padding: 16px 18px; background: linear-gradient(120deg, var(--pri-bg), #fff 72%); }.att-now__head > div { display: grid; gap: 3px; }.att-now__head span { color: var(--pri); font-size: 10px; font-weight: 800; letter-spacing: .12em; }.att-now__head h2 { margin: 0; color: var(--t1); font-size: 17px; }.att-now__head p { margin: 0; color: var(--t3); font-size: 12px; }.att-now__head b { flex: 0 0 auto; padding: 4px 9px; border-radius: 999px; background: #fff; color: var(--pri); font-size: 12px; }
.att-now__list { display: grid; gap: 10px; padding: 14px; }.att-now__item { display: grid; grid-template-columns: minmax(170px,.9fr) minmax(0,2fr) auto; align-items: center; gap: 14px; padding: 12px 14px; border: 1px solid var(--card-b); border-left: 4px solid var(--warning-500,#f59e0b); border-radius: 10px; }.att-now__identity { display: grid; gap: 3px; min-width: 0; }.att-now__identity small { color: var(--pri); font-weight: 700; }.att-now__identity strong,.att-now__identity span { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }.att-now__identity span { color: var(--t3); font-size: 12px; }.att-now__item dl { display: grid; grid-template-columns: 1.15fr 1.2fr .8fr; gap: 8px; margin: 0; }.att-now__item dl div { min-width: 0; padding: 8px 10px; border-radius: 8px; background: var(--fill-2,#f8fafc); }.att-now__item dt { margin-bottom: 3px; color: var(--t3); font-size: 10px; font-weight: 700; }.att-now__item dd { margin: 0; color: var(--t2); font-size: 12px; line-height: 1.45; }.att-now__state { padding: 24px; color: var(--t3); font-size: 13px; text-align: center; }.att-now__readonly { color: var(--t3); font-size: 12px; }
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
@media (max-width: 900px) { .att-now__item { grid-template-columns: 1fr; }.att-now__item dl { grid-template-columns: 1fr; }.att-now__head { align-items: flex-start; flex-direction: column; } }
@media (max-width: 760px) { .tabs { align-items: flex-start; flex-direction: column; } .tabs__list { width: 100%; overflow-x: auto; } .tabs__btn { flex: 0 0 auto; } .bar__hint { width: 100%; margin-left: 0; } }
</style>
