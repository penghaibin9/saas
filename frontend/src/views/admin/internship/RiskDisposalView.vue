<template>
  <ModulePageShell title="风险处置" subtitle="实习风险受理 · 跟进 · 升级 · 关闭闭环"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="secondary" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按学生姓名搜索" @keyup.enter="load" />
      <select v-model="levelFilter" class="bar__sel" @change="load">
        <option value="">全部等级</option><option value="HIGH">高</option><option value="MEDIUM">中</option><option value="LOW">低</option>
      </select>
      <select v-model="statusFilter" class="bar__sel" @change="load">
        <option value="">全部状态</option><option value="PENDING_HANDLE">待处理</option>
        <option value="PROCESSING">处理中</option><option value="CLOSED">已关闭</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无风险单</div>

    <table v-else class="tbl">
      <thead>
        <tr><th>姓名</th><th>班级</th><th>风险来源</th><th>等级</th><th>责任人</th><th>状态</th><th>截止</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.studentName }}</td><td>{{ r.className }}</td><td>{{ r.source }}</td>
          <td><AppRiskTag :level="r.level" /></td><td>{{ r.owner || '—' }}</td>
          <td><AppStatusTag :status="r.status" /></td><td>{{ r.deadline || '—' }}</td>
          <td class="tbl__ops">
            <button class="op" @click="openDetail(r)">详情</button>
            <button v-if="r.status === 'PENDING_HANDLE'" class="op op--ok" @click="openAction(r, 'handle')">受理</button>
            <template v-if="r.status === 'PROCESSING'">
              <button class="op" @click="openAction(r, 'follow')">跟进</button>
              <button v-if="r.level !== 'HIGH'" class="op op--warn" @click="openAction(r, 'escalate')">升级</button>
              <button class="op op--danger" @click="openAction(r, 'close')">关闭</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">风险处置详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <div v-for="f in detailFields" :key="f.key" class="dline">
              <span class="dline__lb">{{ f.label }}</span><span class="dline__ct">{{ detailDlg.data[f.key] || '—' }}</span>
            </div>
            <div class="dtrail">
              <div class="dtrail__t">处置留痕</div>
              <div v-for="(t, i) in (detailDlg.data.auditTrail || [])" :key="i" class="dtrail__i">
                <b>{{ actionLabel(t.action) }}</b> · {{ t.operator }} · {{ t.occurredAt }}
                <span v-if="t.detail && t.detail.note"> · {{ t.detail.note }}</span>
                <span v-else-if="t.detail && t.detail.comment"> · {{ t.detail.comment }}</span>
              </div>
              <div v-if="!(detailDlg.data.auditTrail || []).length" class="tbl__muted">暂无</div>
            </div>
          </template>
        </div>
        <div class="modal__foot"><button class="mbtn" @click="detailDlg.visible = false">关闭</button></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="true"
      :reason-label="cd.reasonLabel" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppRiskTag, AppConfirmDialog } from '@/components/common'
import { riskApi } from '@/modules/internship/api/leave-risk.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'riskCode', label: '风险编码' }, { key: 'riskTitle', label: '风险标题' },
  { key: 'riskLevelLabel', label: '等级' }, { key: 'sourceModule', label: '来源' },
  { key: 'ownerName', label: '责任人' }, { key: 'statusLabel', label: '状态' },
  { key: 'deadlineAt', label: '截止' }, { key: 'lastFollowNote', label: '最近跟进' }
]
const ACTION_LABEL = { HANDLE: '受理', FOLLOW: '跟进', ESCALATE: '升级', CLOSE: '关闭',
  CREATE_FROM_GUIDANCE: '指导转入', CREATE: '创建' }
const NEXT_LEVEL = { LOW: 'MEDIUM', MEDIUM: 'HIGH' }

export default {
  name: 'RiskDisposalView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppRiskTag, AppConfirmDialog },
  data() {
    return {
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', levelFilter: '', statusFilter: '',
      detailFields: DETAIL,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  created() { this.load() },
  methods: {
    actionLabel(a) { return ACTION_LABEL[a] || a },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      if (this.levelFilter) params.level = this.levelFilter
      if (this.statusFilter) params.status = this.statusFilter
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
    },
    async doExport() {
      this.exporting = true
      const res = await riskApi.exportRisks({ keyword: this.keyword })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '风险处置台账.xlsx')
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
.tbl__ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm); padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--warn { border-color: var(--warning-100); color: var(--warning-700); }
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
