<template>
  <ModulePageShell title="企业评价" subtitle="企业导师五维评价 · 学校审核 · 来源可追溯"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="primary" @click="openCreate">＋ 录入企业评价</AppButton>
      <AppButton variant="secondary" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按学生姓名搜索" @keyup.enter="load" />
      <select v-model="statusFilter" class="bar__sel" @change="load">
        <option value="">全部审核状态</option><option value="PENDING">待审核</option>
        <option value="APPROVED">已通过</option><option value="RETURNED">已退回</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无企业评价</div>

    <table v-else class="tbl">
      <thead>
        <tr><th>学号</th><th>姓名</th><th>企业导师</th><th>出勤</th><th>技能</th><th>态度</th><th>协作</th><th>安全</th><th>均分</th><th>建议录用</th><th>来源</th><th>审核</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.studentNo }}</td><td>{{ r.studentName }}</td><td>{{ r.mentorName }}</td>
          <td>{{ r.attendanceScore }}</td><td>{{ r.skillScore }}</td><td>{{ r.attitudeScore }}</td>
          <td>{{ r.collaborationScore }}</td><td>{{ r.safetyScore }}</td><td><b>{{ r.avgScore }}</b></td>
          <td>{{ r.recommendHire ? '是' : '否' }}</td>
          <td><AppStatusTag :type="r.source === 'ENTERPRISE' ? 'success' : 'default'">{{ r.sourceLabel }}</AppStatusTag></td>
          <td><AppStatusTag :type="reviewTone(r.reviewStatus)">{{ r.reviewStatusLabel }}</AppStatusTag></td>
          <td class="tbl__ops">
            <button class="op" @click="openDetail(r)">详情</button>
            <template v-if="r.reviewStatus === 'PENDING'">
              <button class="op op--ok" @click="openReview(r, 'APPROVE')">通过</button>
              <button class="op op--danger" @click="openReview(r, 'RETURN')">退回</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 录入 -->
    <div v-if="createDlg.visible" class="modal" @click.self="createDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">录入企业评价</div>
        <div class="modal__body">
          <label class="fld"><span class="fld__lb">实习学生 *</span>
            <select v-model="form.internshipId" class="fld__ct">
              <option value="">请选择本人指导学生</option>
              <option v-for="s in studentOptions" :key="s.id" :value="s.id">{{ s.name }}（{{ s.studentNo }}）· {{ s.enterpriseName || '未分配企业' }}</option>
            </select>
          </label>
          <label class="fld"><span class="fld__lb">企业导师姓名 *（来源可追溯）</span><input v-model="form.mentorName" class="fld__ct" placeholder="填写企业导师真实姓名" /></label>
          <div class="scores">
            <label v-for="s in scoreDefs" :key="s.key" class="score">
              <span class="score__lb">{{ s.label }}</span>
              <input v-model.number="form[s.key]" type="number" min="0" max="100" class="score__in" />
            </label>
          </div>
          <label class="fld"><span class="fld__lb">综合评语</span><textarea v-model="form.overallComment" class="fld__ct fld__ta" placeholder="企业对学生的综合评语"></textarea></label>
          <label class="chk"><input v-model="form.recommendHire" type="checkbox" />建议录用</label>
          <label class="fld"><span class="fld__lb">评价扫描件（可选，企业签署）</span>
            <input type="file" class="fld__ct fld__file" @change="onFile" />
            <span v-if="form.fileId" class="fld__att">已上传：{{ attachName }}</span>
            <span v-else-if="uploadingFile" class="fld__att">上传中…</span>
          </label>
          <p class="modal__hint">五维评分均 0-100。学校录入的企业纸质评价来源标记为「学校录入」，请如实转录企业导师评价，勿代填虚构。</p>
        </div>
        <div class="modal__foot">
          <button class="mbtn" @click="createDlg.visible = false">取消</button>
          <button class="mbtn mbtn--primary" :disabled="createDlg.submitting" @click="submitCreate">{{ createDlg.submitting ? '提交中…' : '提交' }}</button>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">企业评价详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <div v-for="f in detailFields" :key="f.key" class="dline">
              <span class="dline__lb">{{ f.label }}</span><span class="dline__ct">{{ fmt(detailDlg.data, f) }}</span>
            </div>
            <div v-if="detailDlg.data.attachment" class="dline">
              <span class="dline__lb">评价扫描件</span>
              <span class="dline__ct"><button class="op" @click="downloadAtt(detailDlg.data.attachment)">⬇ {{ detailDlg.data.attachment.fileName }}</button></span>
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
import { enterpriseEvalApi } from '@/modules/internship/api/enterprise-eval.api'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const SCORES = [
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' },
  { key: 'safetyScore', label: '安全纪律' }
]
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'mentorName', label: '企业导师' },
  { key: 'positionName', label: '岗位' }, { key: 'attendanceScore', label: '出勤' },
  { key: 'skillScore', label: '技能' }, { key: 'attitudeScore', label: '态度' },
  { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' },
  { key: 'avgScore', label: '均分' }, { key: 'recommendHire', label: '建议录用', bool: true },
  { key: 'overallComment', label: '综合评语' }, { key: 'sourceLabel', label: '来源' },
  { key: 'reviewStatusLabel', label: '审核状态' }, { key: 'reviewComment', label: '审核意见' }
]

function emptyForm() {
  return { internshipId: '', mentorName: '', attendanceScore: null, skillScore: null,
    attitudeScore: null, collaborationScore: null, safetyScore: null,
    overallComment: '', recommendHire: false, fileId: '' }
}

export default {
  name: 'EnterpriseEvalView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppConfirmDialog },
  data() {
    return {
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', statusFilter: '', scoreDefs: SCORES, detailFields: DETAIL,
      studentOptions: [], form: emptyForm(), attachName: '', uploadingFile: false,
      createDlg: { visible: false, submitting: false },
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  created() { this.load() },
  methods: {
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    fmt(d, f) { return f.bool ? (d[f.key] ? '是' : '否') : (d[f.key] === 0 ? 0 : (d[f.key] || '—')) },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      const res = await enterpriseEvalApi.getEvals(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openCreate() {
      this.form = emptyForm(); this.attachName = ''; this.createDlg.visible = true
      if (!this.studentOptions.length) {
        const res = await internStudentApi.getStudents({ page: 1, pageSize: 200 })
        if (res.code === 0) this.studentOptions = res.data.list.map((s) => ({ id: s.id, name: s.name, studentNo: s.studentNo, enterpriseName: s.enterpriseName }))
      }
    },
    async onFile(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await enterpriseEvalApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
    },
    async submitCreate() {
      if (!this.form.internshipId) return toast.error('请选择实习学生')
      if (!this.form.mentorName.trim()) return toast.error('请填写企业导师姓名')
      for (const s of SCORES) {
        const v = this.form[s.key]
        if (v === null || v === '' || v < 0 || v > 100) return toast.error(`${s.label}评分须为 0-100`)
      }
      this.createDlg.submitting = true
      const res = await enterpriseEvalApi.create(this.form)
      this.createDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      this.createDlg.visible = false; toast.success('已录入并写审计'); this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await enterpriseEvalApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    async downloadAtt(att) {
      try { await enterpriseEvalApi.downloadAttachment(att.fileId, att.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openReview(r, action) {
      const ap = action === 'APPROVE'
      this.pending = { id: r.id, action }
      this.cd = { visible: true, title: ap ? '企业评价 · 通过' : '企业评价 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的企业评价，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await enterpriseEvalApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审核完成，已写审计'); this.load()
    },
    async doExport() {
      this.exporting = true
      const res = await enterpriseEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '企业评价台账.xlsx')
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
.tbl th, .tbl td { text-align: left; padding: var(--space-2) var(--space-2); border-bottom: 1px solid var(--border-light); }
.tbl th { color: var(--text-tertiary); font-weight: var(--font-weight-medium); background: var(--bg-subtle); }
.tbl__ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm); padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(560px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
.modal__hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.mbtn { height: 34px; padding: 0 var(--space-4); border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.mbtn--primary { background: var(--primary-600); border-color: var(--primary-600); color: #fff; }
.mbtn--primary:disabled { opacity: 0.6; cursor: not-allowed; }
.fld { display: flex; flex-direction: column; gap: var(--space-1); margin-bottom: var(--space-3); }
.fld__lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.fld__ct { height: 34px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-2); font-size: var(--font-size-sm); }
.fld__ta { height: 60px; padding: var(--space-2); resize: vertical; }
.fld__file { height: auto; padding: var(--space-1) 0; border: none; font-size: var(--font-size-xs); }
.fld__att { font-size: var(--font-size-xs); color: var(--success-700); }
.scores { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.score { display: flex; flex-direction: column; gap: 2px; width: calc(20% - var(--space-2)); min-width: 72px; }
.score__lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.score__in { height: 32px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-1); font-size: var(--font-size-sm); width: 100%; }
.chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.dline { display: flex; gap: var(--space-3); padding: var(--space-1) 0; font-size: var(--font-size-sm); }
.dline__lb { width: 96px; flex-shrink: 0; color: var(--text-tertiary); }
.dline__ct { color: var(--text-primary); word-break: break-all; }
.dtrail { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); }
.dtrail__t { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.dtrail__i { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 2px 0; }
</style>
