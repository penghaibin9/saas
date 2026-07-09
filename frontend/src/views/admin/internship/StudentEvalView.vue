<template>
  <ModulePageShell title="评价与成绩" subtitle="学生鉴定 · 学生自评 · 指导教师意见 · 学校审核"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="secondary" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按学生姓名搜索" @keyup.enter="load" />
      <select v-model="statusFilter" class="bar__sel" @change="load">
        <option value="">全部审核状态</option><option value="PENDING">待审核</option>
        <option value="APPROVED">已通过</option><option value="RETURNED">已退回</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 学生自评经 mobile 提交</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无学生鉴定（学生尚未提交自评）</div>

    <table v-else class="tbl">
      <thead>
        <tr><th>学号</th><th>姓名</th><th>指导教师</th><th>自评</th><th>教师意见</th><th>企业意见</th><th>学校审核</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.studentNo }}</td><td>{{ r.studentName }}</td><td>{{ r.advisorName }}</td>
          <td><AppStatusTag :type="r.submitStatus === 'SUBMITTED' ? 'success' : 'default'">{{ r.submitStatusLabel }}</AppStatusTag></td>
          <td>{{ r.hasAdvisorOpinion ? '已填' : '未填' }}</td><td>{{ r.hasMentorOpinion ? '已填' : '未填' }}</td>
          <td><AppStatusTag :type="reviewTone(r.reviewStatus)">{{ r.reviewStatusLabel }}</AppStatusTag></td>
          <td class="tbl__ops">
            <button class="op" @click="openDetail(r)">详情</button>
            <button v-if="r.submitStatus === 'SUBMITTED'" class="op" @click="openComment(r)">填意见</button>
            <template v-if="r.submitStatus === 'SUBMITTED' && r.reviewStatus === 'PENDING'">
              <button class="op op--ok" @click="openReview(r, 'APPROVE')">通过</button>
              <button class="op op--danger" @click="openReview(r, 'RETURN')">退回</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 填意见 -->
    <div v-if="cmtDlg.visible" class="modal" @click.self="cmtDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">指导教师意见</div>
        <div class="modal__body">
          <label class="fld"><span class="fld__lb">指导教师意见 *</span><textarea v-model="cmtForm.advisorOpinion" class="fld__ct fld__ta" placeholder="对学生实习表现的鉴定意见"></textarea></label>
          <label class="fld"><span class="fld__lb">企业导师意见（可选，如实转录）</span><textarea v-model="cmtForm.mentorOpinion" class="fld__ct fld__ta" placeholder="企业导师对学生的意见"></textarea></label>
        </div>
        <div class="modal__foot">
          <button class="mbtn" @click="cmtDlg.visible = false">取消</button>
          <button class="mbtn mbtn--primary" :disabled="cmtDlg.submitting" @click="submitComment">{{ cmtDlg.submitting ? '保存中…' : '保存意见' }}</button>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">学生鉴定详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <div v-for="f in detailFields" :key="f.key" class="dline">
              <span class="dline__lb">{{ f.label }}</span><span class="dline__ct">{{ detailDlg.data[f.key] || '—' }}</span>
            </div>
            <div class="dtrail">
              <div class="dtrail__t">操作留痕</div>
              <div v-for="(t, i) in (detailDlg.data.auditTrail || [])" :key="i" class="dtrail__i"><b>{{ t.action }}</b> · {{ t.operator }} · {{ t.occurredAt }}</div>
            </div>
          </template>
        </div>
        <div class="modal__foot"><button class="mbtn" @click="detailDlg.visible = false">关闭</button></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="审核意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { studentEvalApi } from '@/modules/internship/api/student-eval.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'selfSummary', label: '实习总结' }, { key: 'selfHarvest', label: '学习收获' },
  { key: 'selfProblem', label: '存在问题' }, { key: 'advisorOpinion', label: '指导教师意见' },
  { key: 'mentorOpinion', label: '企业导师意见' }, { key: 'reviewStatusLabel', label: '学校审核' },
  { key: 'reviewComment', label: '审核意见' }
]

export default {
  name: 'StudentEvalView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppConfirmDialog },
  data() {
    return {
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', statusFilter: '', detailFields: DETAIL,
      cmtForm: { advisorOpinion: '', mentorOpinion: '' }, cmtDlg: { visible: false, submitting: false }, cmtRow: null,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  created() { this.load() },
  methods: {
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      const res = await studentEvalApi.getEvals(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    openComment(r) {
      this.cmtRow = r; this.cmtForm = { advisorOpinion: '', mentorOpinion: '' }; this.cmtDlg.visible = true
    },
    async submitComment() {
      if (!this.cmtForm.advisorOpinion.trim()) return toast.error('请填写指导教师意见')
      this.cmtDlg.submitting = true
      const res = await studentEvalApi.advisorComment(this.cmtRow.id, this.cmtForm)
      this.cmtDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '保存失败')
      this.cmtDlg.visible = false; toast.success('已保存意见'); this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await studentEvalApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    openReview(r, action) {
      const ap = action === 'APPROVE'
      this.pending = { id: r.id, action }
      this.cd = { visible: true, title: ap ? '鉴定 · 通过' : '鉴定 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的实习鉴定，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await studentEvalApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审核完成，已写审计'); this.load()
    },
    async doExport() {
      this.exporting = true
      const res = await studentEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '学生鉴定台账.xlsx')
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
.tbl__ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm); padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(540px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
.mbtn { height: 34px; padding: 0 var(--space-4); border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.mbtn--primary { background: var(--primary-600); border-color: var(--primary-600); color: #fff; }
.mbtn--primary:disabled { opacity: 0.6; cursor: not-allowed; }
.fld { display: flex; flex-direction: column; gap: var(--space-1); margin-bottom: var(--space-3); }
.fld__lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.fld__ct { border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: var(--space-2); font-size: var(--font-size-sm); }
.fld__ta { height: 72px; resize: vertical; }
.dline { display: flex; gap: var(--space-3); padding: var(--space-1) 0; font-size: var(--font-size-sm); }
.dline__lb { width: 96px; flex-shrink: 0; color: var(--text-tertiary); }
.dline__ct { color: var(--text-primary); word-break: break-all; white-space: pre-wrap; }
.dtrail { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); }
.dtrail__t { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.dtrail__i { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 2px 0; }
</style>
