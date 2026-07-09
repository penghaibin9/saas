<template>
  <ModulePageShell title="实习请假审批" subtitle="学生实习期请假 · 指导教师审批 · 证明附件留痕"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="secondary" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按学生姓名搜索" @keyup.enter="load" />
      <select v-model="statusFilter" class="bar__sel" @change="load">
        <option value="">全部状态</option>
        <option value="PENDING">待审批</option>
        <option value="APPROVED">已通过</option>
        <option value="REJECTED">已驳回</option>
        <option value="WITHDRAWN">已撤回</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无请假申请</div>

    <table v-else class="tbl">
      <thead>
        <tr><th>学号</th><th>姓名</th><th>指导教师</th><th>类型</th><th>起止</th><th>天数</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.studentNo }}</td><td>{{ r.studentName }}</td><td>{{ r.advisorName }}</td>
          <td>{{ r.leaveTypeLabel }}</td><td>{{ r.startDate }} ~ {{ r.endDate }}</td><td>{{ r.days }}</td>
          <td><AppStatusTag :status="r.status" /></td>
          <td class="tbl__ops">
            <button class="op" @click="openDetail(r)">详情</button>
            <template v-if="r.status === 'PENDING'">
              <button class="op op--ok" @click="openReview(r, 'APPROVE')">通过</button>
              <button class="op op--danger" @click="openReview(r, 'REJECT')">驳回</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">请假详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <div v-for="f in detailFields" :key="f.key" class="dline">
              <span class="dline__lb">{{ f.label }}</span><span class="dline__ct">{{ detailDlg.data[f.key] || '—' }}</span>
            </div>
            <div v-if="detailDlg.data.attachment" class="dline">
              <span class="dline__lb">证明附件</span>
              <span class="dline__ct"><button class="op" @click="downloadAtt(detailDlg.data.attachment)">⬇ {{ detailDlg.data.attachment.fileName }}</button></span>
            </div>
            <div class="dtrail">
              <div class="dtrail__t">审批留痕</div>
              <div v-for="(t, i) in (detailDlg.data.auditTrail || [])" :key="i" class="dtrail__i"><b>{{ t.action }}</b> · {{ t.operator }} · {{ t.occurredAt }}</div>
              <div v-if="!(detailDlg.data.auditTrail || []).length" class="tbl__muted">暂无</div>
            </div>
          </template>
        </div>
        <div class="modal__foot"><button class="mbtn" @click="detailDlg.visible = false">关闭</button></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="审批意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { leaveApi } from '@/modules/internship/api/leave-risk.api'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'leaveTypeLabel', label: '类型' }, { key: 'startDate', label: '开始' },
  { key: 'endDate', label: '结束' }, { key: 'days', label: '天数' }, { key: 'reason', label: '事由' },
  { key: 'statusLabel', label: '状态' }, { key: 'reviewBy', label: '审批人' }, { key: 'reviewComment', label: '审批意见' }
]

export default {
  name: 'LeaveReviewView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppConfirmDialog },
  data() {
    return {
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', statusFilter: '',
      detailFields: DETAIL,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await leaveApi.getLeaves(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await leaveApi.getLeaveDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    async downloadAtt(att) {
      try { await guidanceVisitApi.downloadAttachment(att.fileId, att.fileName) }
      catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openReview(r, action) {
      this.pending = { id: r.id, action }
      const ap = action === 'APPROVE'
      this.cd = { visible: true, title: ap ? '请假 · 通过' : '请假 · 驳回',
        content: `${ap ? '通过' : '驳回'}「${r.studentName}」${r.startDate}~${r.endDate} 的请假，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '驳回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await leaveApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审批完成，已写审计'); this.load()
    },
    async doExport() {
      this.exporting = true
      const res = await leaveApi.exportLeaves({ keyword: this.keyword, status: this.statusFilter })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '请假审批台账.xlsx')
      toast.success(`已导出 ${res.data.rowCount} 条（水印 + 导出留痕）`)
    }
  }
}
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.bar__kw, .bar__sel { height: 32px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-2); font-size: var(--font-size-sm); }
.bar__go { height: 32px; padding: 0 var(--space-3); border: 1px solid var(--primary-600); background: var(--primary-600); color: #fff; border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.tbl { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.tbl th, .tbl td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-light); }
.tbl th { color: var(--text-tertiary); font-weight: var(--font-weight-medium); background: var(--bg-subtle); }
.tbl__muted { color: var(--text-disabled); }
.tbl__ops { display: flex; gap: var(--space-1); }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm); padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(520px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
.mbtn { height: 34px; padding: 0 var(--space-4); border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.dline { display: flex; gap: var(--space-3); padding: var(--space-1) 0; font-size: var(--font-size-sm); }
.dline__lb { width: 88px; flex-shrink: 0; color: var(--text-tertiary); }
.dline__ct { color: var(--text-primary); word-break: break-all; }
.dtrail { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); }
.dtrail__t { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.dtrail__i { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 2px 0; }
</style>
