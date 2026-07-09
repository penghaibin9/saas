<template>
  <ModulePageShell title="打卡与请假" subtitle="打卡台账 · 打卡异常 · 补卡审批 · 实习请假"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton :variant="'secondary'" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }"
        @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按姓名搜索" @keyup.enter="load" />
      <select v-if="tab !== 'checkins'" v-model="statusFilter" class="bar__sel" @change="load">
        <option value="">全部状态</option>
        <option v-for="o in statusOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无数据</div>

    <table v-else class="tbl">
      <thead>
        <tr><th v-for="c in columns" :key="c.key">{{ c.label }}</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td v-for="c in columns" :key="c.key">
            <template v-if="c.key === 'status'"><AppStatusTag :status="r.status" /></template>
            <template v-else-if="c.key === 'result'"><AppStatusTag :type="r.tone === 'danger' ? 'danger' : 'success'">{{ r.resultLabel }}</AppStatusTag></template>
            <template v-else>{{ r[c.key] }}</template>
          </td>
          <td class="tbl__ops">
            <template v-if="tab === 'exceptions' && r.status === 'PENDING_HANDLE'">
              <button class="op" @click="openHandle(r, 'REASONABLE')">合理</button>
              <button class="op" @click="openHandle(r, 'ABNORMAL')">异常</button>
              <button class="op op--danger" @click="openHandle(r, 'TO_RISK')">转风险</button>
            </template>
            <template v-else-if="tab === 'makeups' && r.status === 'PENDING'">
              <button class="op op--ok" @click="openApprove(r)">通过</button>
              <button class="op op--danger" @click="openReject(r)">驳回</button>
            </template>
            <span v-else class="tbl__muted">—</span>
          </td>
        </tr>
      </tbody>
    </table>

    <AppConfirmDialog v-model:visible="dlg.visible" :title="dlg.title" :content="dlg.content"
      :danger="dlg.danger" :confirm-text="dlg.confirmText" :require-reason="dlg.requireReason"
      reason-label="处理意见" :submitting="dlg.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { attendanceApi } from '@/modules/internship/api/attendance.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
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

export default {
  name: 'AttendanceView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppConfirmDialog },
  data() {
    return {
      tab: 'checkins',
      tabs: [{ key: 'checkins', label: '打卡台账' }, { key: 'exceptions', label: '打卡异常' }, { key: 'makeups', label: '补卡审批' }],
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', statusFilter: '',
      dlg: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: true, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    columns() { return COLS[this.tab] },
    statusOptions() { return STATUS_OPTS[this.tab] || [] }
  },
  created() { this.load() },
  methods: {
    switchTab(k) { this.tab = k; this.keyword = ''; this.statusFilter = ''; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const api = { checkins: 'getCheckins', exceptions: 'getExceptions', makeups: 'getMakeups' }[this.tab]
      const res = await attendanceApi[api](params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async doExport() {
      this.exporting = true
      const api = { checkins: 'exportCheckins', exceptions: 'exportExceptions', makeups: 'exportMakeups' }[this.tab]
      const res = await attendanceApi[api]({ keyword: this.keyword, status: this.statusFilter })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '台账.xlsx')
      toast.success(`已导出 ${res.data.rowCount} 条（脱敏 + 水印，已写审计）`)
    },
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
.tabs { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.tabs__btn { border: none; background: none; padding: var(--space-2) var(--space-3); cursor: pointer;
  color: var(--text-secondary); font-size: var(--font-size-sm); border-bottom: 2px solid transparent; }
.tabs__btn.is-active { color: var(--primary-700); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-medium); }
.bar { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.bar__kw, .bar__sel { height: 32px; border: 1px solid var(--border-base); border-radius: var(--radius-base);
  padding: 0 var(--space-2); font-size: var(--font-size-sm); }
.bar__go { height: 32px; padding: 0 var(--space-3); border: 1px solid var(--primary-600); background: var(--primary-600);
  color: #fff; border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm);
  border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.tbl { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.tbl th, .tbl td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-light); }
.tbl th { color: var(--text-tertiary); font-weight: var(--font-weight-medium); background: var(--bg-subtle); }
.tbl__muted { color: var(--text-disabled); }
.tbl__ops { display: flex; gap: var(--space-1); }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
</style>
