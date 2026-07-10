<template>
  <ModulePageShell title="风险处置" subtitle="实习风险受理 · 跟进 · 升级 · 关闭闭环"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="levelFilter" :options="levelOptions" allow-clear @change="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-level="{ row }"><AppRiskTag :level="row.level" /></template>
      <template #cell-owner="{ row }">{{ row.owner || '—' }}</template>
      <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
      <template #cell-deadline="{ row }">{{ row.deadline || '—' }}</template>
      <template #cell-actions="{ row }">
        <div class="ops">
          <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
          <AppPermissionButton v-if="row.status === 'PENDING_HANDLE'" code="internship.risk.handle" variant="secondary" size="sm" @click="openAction(row, 'handle')">受理</AppPermissionButton>
          <template v-if="row.status === 'PROCESSING'">
            <AppPermissionButton code="internship.risk.handle" variant="ghost" size="sm" @click="openAction(row, 'follow')">跟进</AppPermissionButton>
            <AppPermissionButton v-if="row.level !== 'HIGH'" code="internship.risk.handle" variant="ghost" size="sm" @click="openAction(row, 'escalate')">升级</AppPermissionButton>
            <AppPermissionButton code="internship.risk.handle" variant="ghost" size="sm" :danger="true" @click="openAction(row, 'close')">关闭</AppPermissionButton>
          </template>
        </div>
      </template>
    </DataTable>

    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">风险处置详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <div class="sec-t">处置留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无处置记录" />
          </template>
        </div>
        <div class="modal__foot"><AppButton variant="secondary" @click="detailDlg.visible = false">关闭</AppButton></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="true"
      :reason-label="cd.reasonLabel" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppRiskTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
  AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips } from '@/components/common'
import { riskApi } from '@/modules/internship/api/leave-risk.api'
import { toast } from '@/utils/toast'

const COLUMNS = [
  { key: 'studentName', title: '姓名' }, { key: 'className', title: '班级' },
  { key: 'source', title: '风险来源' }, { key: 'level', title: '等级', width: '80px' },
  { key: 'owner', title: '责任人' }, { key: 'status', title: '状态' },
  { key: 'deadline', title: '截止' }, { key: 'actions', title: '操作', width: '240px' }
]
const LEVEL_OPTIONS = [{ label: '高', value: 'HIGH' }, { label: '中', value: 'MEDIUM' }, { label: '低', value: 'LOW' }]
const STATUS_OPTIONS = [{ label: '待处理', value: 'PENDING_HANDLE' }, { label: '处理中', value: 'PROCESSING' }, { label: '已关闭', value: 'CLOSED' }]
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'riskCode', label: '风险编码' }, { key: 'riskTitle', label: '风险标题' },
  { key: 'riskLevelLabel', label: '等级' }, { key: 'sourceModule', label: '来源' },
  { key: 'ownerName', label: '责任人' }, { key: 'statusLabel', label: '状态' },
  { key: 'deadlineAt', label: '截止' }, { key: 'lastFollowNote', label: '最近跟进' }
]
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
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppRiskTag, AppConfirmDialog,
    AppExportButton, AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', levelFilter: '', statusFilter: '', riskCode: '',
      columns: COLUMNS, levelOptions: LEVEL_OPTIONS, statusOptions: STATUS_OPTIONS,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    detailItems() { const d = this.detailDlg.data || {}; return DETAIL.map((f) => ({ label: f.label, value: d[f.key] })) },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator,
        reason: t.detail && (t.detail.note || t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'pending').toString())
      }
    }
  },
  methods: {
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.pending
      const { levelFilter, statusFilter, riskCode } = preset()
      this.levelFilter = levelFilter
      this.statusFilter = statusFilter
      this.riskCode = riskCode
      this.keyword = ''
      this.page = 1
      this.load()
    },
    exportFn() { return riskApi.exportRisks({ keyword: this.keyword }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.levelFilter) params.level = this.levelFilter
      if (this.statusFilter) params.status = this.statusFilter
      if (this.riskCode) params.riskCode = this.riskCode
      const res = await riskApi.getRisks(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await riskApi.getRiskDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    openAction(r, kind) {
      const map = {
        handle: { title: '受理风险', content: `受理「${r.studentName}」的风险并转入处理中，受理意见将写审计。`, danger: false, confirmText: '受理', reasonLabel: '受理意见（≥5字）' },
        follow: { title: '风险跟进', content: `为「${r.studentName}」追加一条跟进记录。`, danger: false, confirmText: '跟进', reasonLabel: '跟进说明' },
        escalate: { title: '风险升级', content: `将「${r.studentName}」风险等级升级为「${r.level === 'LOW' ? '中' : '高'}」，升级原因将写审计。`, danger: true, confirmText: '升级', reasonLabel: '升级原因' },
        close: { title: '风险关闭', content: `将「${r.studentName}」的风险化解并关闭归档，关闭说明将写审计。`, danger: true, confirmText: '关闭', reasonLabel: '关闭说明（≥5字）' }
      }[kind]
      this.pending = { id: r.id, kind, level: r.level }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      let res
      if (p.kind === 'handle') res = await riskApi.handle(p.id, { comment: reason })
      else if (p.kind === 'follow') res = await riskApi.follow(p.id, { note: reason })
      else if (p.kind === 'escalate') res = await riskApi.escalate(p.id, { level: NEXT_LEVEL[p.level], note: reason })
      else res = await riskApi.close(p.id, { result: 'RESOLVED', comment: reason })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计'); this.load()
    }
  }
}
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(520px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
