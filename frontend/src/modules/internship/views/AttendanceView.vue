<template>
  <ModulePageShell title="打卡请假处理" subtitle="查看学生出勤情况，集中处理缺卡、定位异常、请假和超期未归 · 打卡台账 · 打卡异常 · 补卡审批 · 实习请假"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/leaves')">请假审批</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div class="tabs" aria-label="出勤业务切换">
      <span class="tabs__caption">出勤处置台</span>
      <div class="tabs__list">
        <button v-for="t in tabs" :key="t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }"
          @click="switchTab(t.key)">{{ t.label }}</button>
      </div>
    </div>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按姓名搜索" :debounce="0" button @search="load" />
      <AppQuickFilterChips v-if="tab !== 'checkins'" v-model="statusFilter" :options="chipOptions" @change="load" />
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!rows.length" title="暂无数据" />

    <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="null">
      <template #cell-status="{ row }">
        <AppStatusTag :status="row.status" />
      </template>
      <template #cell-result="{ row }">
        <AppStatusTag :type="row.tone === 'danger' ? 'danger' : 'success'">{{ row.resultLabel }}</AppStatusTag>
      </template>
      <template #cell-actions="{ row }">
        <div class="tbl__ops">
          <template v-if="tab === 'exceptions' && row.status === 'PENDING_HANDLE'">
            <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')" variant="ghost" size="sm" @click="openHandle(row, 'REASONABLE')">合理</AppPermissionButton>
            <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')" variant="ghost" size="sm" @click="openHandle(row, 'ABNORMAL')">异常</AppPermissionButton>
            <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')" variant="ghost" size="sm" :danger="true" @click="openHandle(row, 'TO_RISK')">转风险</AppPermissionButton>
          </template>
          <template v-else-if="tab === 'makeups' && row.status === 'PENDING'">
            <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')" variant="secondary" size="sm" @click="openApprove(row)">通过</AppPermissionButton>
            <AppPermissionButton code="internship.attendance.review" :allowed="canBtn('internship.attendance.review')" variant="ghost" size="sm" :danger="true" @click="openReject(row)">驳回</AppPermissionButton>
          </template>
          <span v-else class="tbl__muted">—</span>
        </div>
      </template>
    </DataTable>

    <AppConfirmDialog v-model:visible="dlg.visible" :title="dlg.title" :content="dlg.content"
      :danger="dlg.danger" :confirm-text="dlg.confirmText" :require-reason="dlg.requireReason"
      reason-label="处理意见" :submitting="dlg.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppSearchBox, AppQuickFilterChips } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { attendanceApi } from '@/modules/internship/api/attendance.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

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
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppSearchBox, AppQuickFilterChips, ModuleSummaryStrip },
  data() {
    return {
      tab: 'checkins',
      tabs: [{ key: 'checkins', label: '打卡台账' }, { key: 'exceptions', label: '打卡异常' }, { key: 'makeups', label: '补卡审批' }],
      rows: [], total: 0, loading: false, error: '',
      tabTotals: { checkins: null, exceptions: null, makeupsAll: null, makeupsPending: null },
      keyword: '', statusFilter: '',
      dlg: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: true, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    columns() { return COLS[this.tab] },
    statusOptions() { return STATUS_OPTS[this.tab] || [] },
    chipOptions() { return [{ label: '全部状态', value: '' }, ...this.statusOptions] },
    tableColumns() { return [...this.columns.map((c) => ({ key: c.key, title: c.label })), { key: 'actions', title: '操作' }] },
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
      this.load()
    },
    switchTab(k) {
      const panel = TAB_PANEL[k] || k
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
      } else {
        this.applyPanel(panel)
      }
    },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
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
      return attendanceApi[api]({ keyword: this.keyword, status: this.statusFilter })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（脱敏 + 水印，已写审计）`) },
    openHandle(r, action) {
      const label = { REASONABLE: '标记合理', ABNORMAL: '记为异常', TO_RISK: '转风险跟进' }[action]
      this.pending = { kind: 'handle', id: r.id, action }
      this.dlg = { visible: true, title: `打卡异常 · ${label}`, content: `对「${r.studentName}」的打卡异常${label}，处理意见将写入审计。`,
        danger: action === 'TO_RISK', confirmText: label, requireReason: true, submitting: false }
    },
    openApprove(r) {
      this.pending = { kind: 'approve', id: r.id }
      this.dlg = { visible: true, title: '补卡 · 通过', content: `通过「${r.studentName}」${r.checkinDate} 的补卡，将真实补写一条打卡留痕并写审计。`,
        danger: false, confirmText: '通过', requireReason: false, submitting: false }
    },
    openReject(r) {
      this.pending = { kind: 'reject', id: r.id }
      this.dlg = { visible: true, title: '补卡 · 驳回', content: `驳回「${r.studentName}」${r.checkinDate} 的补卡，原因将写入审计。`,
        danger: true, confirmText: '驳回', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.dlg.submitting = true
      let res
      if (p.kind === 'handle') res = await attendanceApi.handleException(p.id, { action: p.action, comment: reason })
      else if (p.kind === 'approve') res = await attendanceApi.approveMakeup(p.id, { comment: reason })
      else res = await attendanceApi.rejectMakeup(p.id, { comment: reason })
      this.dlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.dlg.visible = false
      toast.success('操作成功，已写审计')
      this.load()
    }
  }
}
</script>

<style scoped>
.tabs { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 10px 12px; margin-bottom: var(--space-3); border: 1px solid var(--card-b); border-radius: var(--r); background: linear-gradient(100deg, var(--pri-bg), var(--card)); box-shadow: var(--s1); }
.tabs__caption { color: var(--t2); font-size: 12px; font-weight: var(--font-weight-semibold); white-space: nowrap; }
.tabs__list { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: rgba(255, 255, 255, .7); }
.tabs__btn { border: 1px solid transparent; border-radius: 7px; background: transparent; padding: 6px 12px; cursor: pointer; color: var(--text-secondary); font-size: var(--font-size-sm); transition: .16s ease; }
.tabs__btn:hover { color: var(--pri); background: var(--pri-bg); }
.tabs__btn.is-active { color: var(--pri); border-color: var(--pri-100); background: var(--card); font-weight: var(--font-weight-semibold); box-shadow: 0 2px 5px rgba(15, 40, 90, .08); }
.bar { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); padding: 10px 12px; border: 1px solid var(--card-b); border-radius: 12px; background: var(--card); box-shadow: var(--s1); flex-wrap: wrap; }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.tbl__muted { color: var(--text-disabled); }
.tbl__ops { display: flex; gap: var(--space-1); align-items: center; }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
@media (max-width: 760px) { .tabs { align-items: flex-start; flex-direction: column; } .tabs__list { width: 100%; overflow-x: auto; } .tabs__btn { flex: 0 0 auto; } .bar__hint { width: 100%; margin-left: 0; } }
</style>
