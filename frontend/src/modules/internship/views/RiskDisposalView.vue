<template>
  <ModulePageShell title="风险处置" subtitle="实习风险受理 · 跟进 · 升级 · 关闭闭环"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" :has-permission="canBtn('internship.risk.export')" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="levelFilter" :options="levelOptions" allow-clear @change="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
    </div>

    <DualPaneWorkspace aside-title="风险单" :aside-count="total" :aside-width="420">
      <!-- 左栏：风险队列 -->
      <template #aside>
        <div v-if="error" class="state is-err">{{ error }} <button class="mp-link" @click="load">重试</button></div>
        <div v-else-if="loading" class="state">加载中…</div>
        <div v-else-if="!rows.length" class="state">当前筛选条件下暂无风险单</div>
        <ul v-else class="queue">
          <li v-for="row in rows" :key="row.id" class="queue__item"
            :class="{ 'is-active': row.id === selectedId }" @click="select(row)">
            <div class="queue__top">
              <span class="mp-cell-main">{{ row.studentName }}</span>
              <span class="mp-note">{{ row.className }}</span>
              <AppRiskTag :level="row.level" class="queue__lvl" />
            </div>
            <div class="queue__src" :title="row.source">{{ row.source }}</div>
            <div class="queue__meta">
              <AppStatusTag :status="row.status" />
              <span class="mp-note">截止 {{ row.deadline || '未设置' }}</span>
            </div>
            <div v-if="row.lastFollow && row.lastFollow !== '—'" class="queue__follow" :title="row.lastFollow">
              最近跟进：{{ row.lastFollow }}
            </div>
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
        <EmptyState v-else-if="!selectedId && queueDone" title="当前筛选下风险已全部处理"
          description="本队列暂无待处置风险，可调整左侧筛选条件查看其他风险单" />
        <EmptyState v-else-if="!selectedId" title="未选择风险单"
          description="点击左侧队列中的风险单，在此完成受理、跟进、催办、升级与关闭" />
        <template v-else-if="detail">
          <section class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">风险概要</span>
              <span class="ws__tags">
                <AppRiskTag :level="detail.riskLevel" />
                <AppStatusTag :status="detail.status" />
              </span>
            </div>
            <div class="mp-card__body">
              <AppDescriptionList :items="summaryItems" :columns="2" />
            </div>
          </section>

          <section class="mp-card">
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
              <AppPermissionButton code="internship.risk.handle" :allowed="canBtn('internship.risk.handle')" variant="ghost" :danger="true"
                @click="openAction('close')">关闭</AppPermissionButton>
            </template>
            <span v-else class="mp-note">该风险单已关闭归档，仅保留处置留痕。</span>
          </div>
        </template>
      </div>
    </DualPaneWorkspace>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-label="cd.reasonLabel" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppRiskTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
  AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppPagination } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import { riskApi, complaintApi } from '@/modules/internship/api/leave-risk.api'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'

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
  components: { ModulePageShell, DualPaneWorkspace, LoadingState, ErrorState, EmptyState,
    AppStatusTag, AppRiskTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
    AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppPagination },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', levelFilter: '', statusFilter: '', riskCode: '',
      complaintMode: false,
      levelOptions: LEVEL_OPTIONS, statusOptions: STATUS_OPTIONS,
      selectedId: '', detail: null, detailLoading: false, detailError: '', queueDone: false,
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', requireReason: true, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    /** 只渲染 getRiskDetail 真实返回字段（internship_risk_service._row） */
    summaryItems() {
      const d = this.detail || {}
      return [
        { label: '风险编码', value: d.riskCode },
        { label: '风险标题', value: d.riskTitle },
        { label: '风险等级', value: d.riskLevelLabel },
        { label: '来源模块', value: d.sourceModule },
        { label: '当前状态', value: d.statusLabel },
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
    '$route.query.panel': {
      immediate: true,
      handler() { this.syncRouteFilters() }
    },
    '$route.query.caseType': {
      immediate: false,
      handler() { this.syncRouteFilters() }
    },
    '$route.query.stage': {
      immediate: false,
      handler() { this.syncRouteFilters() }
    },
    /** 选中项写在 query.id，刷新 / 分享链接可恢复 */
    '$route.query.id': {
      immediate: true,
      handler(id) {
        const sid = id ? String(id) : ''
        this.selectedId = sid
        if (sid) {
          this.queueDone = false
          this.loadDetail(sid)
        } else {
          this.detail = null
          this.detailLoading = false
          this.detailError = ''
        }
      }
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.load()
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    /** navPlan 使用 stage=pending|processing|closed；部分入口仍用 panel= */
    syncRouteFilters() {
      const q = this.$route.query || {}
      if (String(q.caseType || '') === 'complaint') {
        this.complaintMode = true
        this.keyword = ''
        this.page = 1
        this.loadComplaints()
        return
      }
      this.complaintMode = false
      const key = (q.panel || q.stage || 'pending').toString()
      this.applyPanel(key)
    },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.pending
      const { levelFilter, statusFilter, riskCode } = preset()
      this.levelFilter = levelFilter
      this.statusFilter = statusFilter
      this.riskCode = riskCode
      this.keyword = ''
      this.page = 1
      this.queueDone = false
      this.load()
    },
    exportFn() {
      return riskApi.exportRisks({
        keyword: this.keyword,
        batchId: this.batchStore.selectedBatchId || undefined
      })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.queueDone = false; this.load() },
    onPageChange({ page }) { this.page = page; this.load() },
    async load() {
      if (this.complaintMode) return this.loadComplaints()
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
      this.loading = true; this.error = ''
      const res = await complaintApi.getComplaints({ page: this.page, pageSize: this.pageSize })
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
      const rid = String(id || '')
      if (!rid) return
      this.detailLoading = true; this.detailError = ''; this.detail = null
      const res = this.complaintMode
        ? await complaintApi.getComplaintDetail(rid)
        : await riskApi.getRiskDetail(rid)
      if (String(this.selectedId) !== rid) return
      this.detailLoading = false
      if (res.code !== 0) { this.detailError = res.message || '加载失败'; return }
      this.detail = res.data
    },
    select(row) {
      if (!row || row.id == null || row.id === '') return
      const id = String(row.id)
      if (id === String(this.selectedId || '')) return
      this.selectedId = id
      this.queueDone = false
      this.detailError = ''
      this.loadDetail(id)
      if (String(this.$route.query.id || '') !== id) {
        this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id }) })
      }
    },
    clearSelection() {
      const query = { ...this.$route.query }
      delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    goStudent() {
      if (this.detail?.internId) {
        this.$router.push({
          path: `/admin/internship/students/${this.detail.internId}`,
          query: this.batchStore.withBatchQuery({})
        })
      }
    },
    openAction(kind) {
      if (this.complaintMode) return
      const d = this.detail
      if (!d) return
      const map = {
        handle: { title: '受理风险', content: `受理「${d.studentName}」的风险并转入处理中，受理意见将写审计。`, danger: false, confirmText: '受理', reasonLabel: '受理意见（≥5字）', requireReason: true },
        follow: { title: '风险跟进', content: `为「${d.studentName}」追加一条跟进记录。`, danger: false, confirmText: '跟进', reasonLabel: '跟进说明', requireReason: true },
        remind: { title: '催办跟进', content: `向责任人「${d.ownerName || '责任人'}」发送站内催办提醒，催办将写审计。`, danger: false, confirmText: '发送催办', reasonLabel: '', requireReason: false },
        escalate: { title: '风险升级', content: `将「${d.studentName}」风险等级升级为「${d.riskLevel === 'LOW' ? '中' : '高'}」，升级原因将写审计。`, danger: true, confirmText: '升级', reasonLabel: '升级原因', requireReason: true },
        close: { title: '风险关闭', content: `将「${d.studentName}」的风险化解并关闭归档，关闭说明将写审计。`, danger: true, confirmText: '关闭', reasonLabel: '关闭说明（≥5字）', requireReason: true }
      }[kind]
      this.pending = { id: d.id, kind, level: d.riskLevel, mode: 'risk', expectedVersion: d.version }
      this.cd = { visible: true, ...map, submitting: false }
    },
    openComplaintAction(action) {
      const d = this.detail
      if (!d) return
      const map = {
        ACCEPT: { title: '受理投诉', content: `受理投诉「${d.complaintNo || d.id}」，转入已受理。`, danger: false, confirmText: '受理', reasonLabel: '责任人（可空）', requireReason: false },
        INVESTIGATE: { title: '转入调查', content: '将投诉转入调查中。', danger: false, confirmText: '转入调查', reasonLabel: '', requireReason: false },
        RESOLVE: { title: '办结投诉', content: '填写办结结论（不少于 5 字）。', danger: false, confirmText: '办结', reasonLabel: '结论（≥5字）', requireReason: true },
        REJECT: { title: '判定不成立', content: '填写不成立理由（不少于 5 字）。', danger: true, confirmText: '不成立', reasonLabel: '理由（≥5字）', requireReason: true },
        CLOSE: { title: '关闭归档', content: '关闭该投诉并归档。', danger: false, confirmText: '关闭', reasonLabel: '', requireReason: false },
        TO_RISK: { title: '转风险单', content: '将本投诉转为实习风险单，保留双向链接。', danger: true, confirmText: '转风险', reasonLabel: '', requireReason: false }
      }[action]
      this.pending = { id: d.id, kind: action, mode: 'complaint' }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      if (!p) return
      this.cd.submitting = true
      let res
      try {
        if (p.mode === 'complaint') {
          if (p.kind === 'TO_RISK') res = await complaintApi.toRisk(p.id)
          else {
            const body = {}
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
        this.cd.submitting = false
      }
      if (!res || res.code !== 0) return toast.error((res && res.message) || '操作失败')
      this.cd.visible = false
      toast.success('操作成功，已写审计')
      if (p.kind === 'close' || p.kind === 'CLOSE') {
        await this.afterClose(p.id)
      } else {
        await this.load()
        if (this.selectedId) this.loadDetail(this.selectedId)
      }
    },
    /** 关闭成功：刷新列表后自动选中下一条未关闭风险；没有则清空选中并提示队列已清 */
    async afterClose(closedId) {
      const prevIdx = this.rows.findIndex((r) => r.id === closedId)
      await this.load()
      const open = this.rows.filter((r) => r.status !== 'CLOSED')
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
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.state.is-err { color: var(--danger-600); }

/* 左栏：紧凑风险队列 */
.queue { list-style: none; margin: 0; padding: 0; }
.queue__item { padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-light); border-left: 3px solid transparent; cursor: pointer; transition: background 0.12s ease, border-color 0.12s ease; }
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
</style>
