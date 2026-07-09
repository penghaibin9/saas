<template>
  <ModulePageShell title="申请与协议" subtitle="三方协议 · 协议生成 · 学生/企业/学校确认 · 签署扫描件留痕"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="primary" @click="openGenerate">＋ 生成协议</AppButton>
      <AppButton variant="secondary" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按学生姓名搜索" @keyup.enter="load" />
      <select v-model="statusFilter" class="bar__sel" @change="load">
        <option value="">全部状态</option>
        <option v-for="(l, k) in statusMap" :key="k" :value="k">{{ l }}</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无协议</div>

    <table v-else class="tbl">
      <thead>
        <tr><th>学号</th><th>姓名</th><th>企业</th><th>岗位</th><th>学生</th><th>企业</th><th>学校</th><th>协议状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.studentNo }}</td><td>{{ r.studentName }}</td><td>{{ r.enterpriseName }}</td><td>{{ r.positionName }}</td>
          <td><AppStatusTag :type="confirmTone(r.studentConfirm)">{{ r.studentConfirmLabel }}</AppStatusTag></td>
          <td><AppStatusTag :type="confirmTone(r.enterpriseConfirm)">{{ r.enterpriseConfirmLabel }}</AppStatusTag></td>
          <td><AppStatusTag :type="confirmTone(r.schoolConfirm)">{{ r.schoolConfirmLabel }}</AppStatusTag></td>
          <td><AppStatusTag :status="r.status">{{ r.statusLabel }}</AppStatusTag></td>
          <td class="tbl__ops">
            <button class="op" @click="openDetail(r)">详情</button>
            <button v-if="r.status === 'DRAFT'" class="op op--ok" @click="confirmAct(r, 'issue')">下发</button>
            <button v-if="r.status === 'PENDING_ENTERPRISE'" class="op op--ok" @click="openEnterprise(r)">记录企业签署</button>
            <button v-if="r.status === 'PENDING_SCHOOL'" class="op op--ok" @click="confirmAct(r, 'school')">学校确认</button>
            <button v-if="r.status === 'EFFECTIVE'" class="op" @click="confirmAct(r, 'archive')">归档</button>
            <button v-if="canReject(r.status)" class="op op--danger" @click="confirmAct(r, 'reject')">驳回</button>
            <button v-if="canVoid(r.status)" class="op op--danger" @click="confirmAct(r, 'void')">作废</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 生成 -->
    <div v-if="genDlg.visible" class="modal" @click.self="genDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">生成三方协议</div>
        <div class="modal__body">
          <label class="fld"><span class="fld__lb">实习学生 *</span>
            <select v-model="genForm.internshipId" class="fld__ct">
              <option value="">请选择本人指导学生</option>
              <option v-for="s in studentOptions" :key="s.id" :value="s.id">{{ s.name }}（{{ s.studentNo }}）· {{ s.enterpriseName || '未分配企业' }}</option>
            </select>
          </label>
          <p class="modal__hint">生成后为草稿，需依次「下发→学生确认→企业签署(上传扫描件)→学校确认」方可生效。仅可对本人指导学生生成。</p>
        </div>
        <div class="modal__foot">
          <button class="mbtn" @click="genDlg.visible = false">取消</button>
          <button class="mbtn mbtn--primary" :disabled="genDlg.submitting" @click="submitGenerate">{{ genDlg.submitting ? '生成中…' : '生成' }}</button>
        </div>
      </div>
    </div>

    <!-- 记录企业签署 -->
    <div v-if="entDlg.visible" class="modal" @click.self="entDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">记录企业签署</div>
        <div class="modal__body">
          <label class="fld"><span class="fld__lb">企业经办人</span><input v-model="entForm.confirmBy" class="fld__ct" placeholder="如：企业 HR 张三" /></label>
          <label class="fld"><span class="fld__lb">签署扫描件 *（企业已签的纸质三方协议）</span>
            <input type="file" class="fld__ct fld__file" @change="onEntFile" />
            <span v-if="entForm.fileId" class="fld__att">已上传：{{ entAttachName }}</span>
            <span v-else-if="uploadingFile" class="fld__att">上传中…</span>
          </label>
          <p class="modal__hint">无电子签章时，以上传企业已签署的纸质三方协议扫描件为准（电子签章能力预留）。</p>
        </div>
        <div class="modal__foot">
          <button class="mbtn" @click="entDlg.visible = false">取消</button>
          <button class="mbtn mbtn--primary" :disabled="entDlg.submitting || !entForm.fileId" @click="submitEnterprise">{{ entDlg.submitting ? '提交中…' : '确认企业已签署' }}</button>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">协议详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <div v-for="f in detailFields" :key="f.key" class="dline">
              <span class="dline__lb">{{ f.label }}</span><span class="dline__ct">{{ detailDlg.data[f.key] || '—' }}</span>
            </div>
            <div v-if="detailDlg.data.attachment" class="dline">
              <span class="dline__lb">签署扫描件</span>
              <span class="dline__ct"><button class="op" @click="downloadAtt(detailDlg.data.attachment)">⬇ {{ detailDlg.data.attachment.fileName }}</button></span>
            </div>
            <div class="dtrail">
              <div class="dtrail__t">三方确认留痕</div>
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
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { agreementApi } from '@/modules/internship/api/agreement.api'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const STATUS_MAP = {
  DRAFT: '草稿', PENDING_STUDENT: '待学生确认', PENDING_ENTERPRISE: '待企业确认',
  PENDING_SCHOOL: '待学校确认', EFFECTIVE: '已生效', REJECTED: '已驳回', VOIDED: '已作废', ARCHIVED: '已归档'
}
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'enterpriseName', label: '企业' }, { key: 'positionName', label: '岗位' },
  { key: 'studentConfirmLabel', label: '学生确认' }, { key: 'enterpriseConfirmLabel', label: '企业确认' },
  { key: 'schoolConfirmLabel', label: '学校确认' }, { key: 'statusLabel', label: '协议状态' },
  { key: 'rejectReason', label: '驳回/作废原因' }
]

export default {
  name: 'AgreementView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppConfirmDialog },
  data() {
    return {
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', statusFilter: '', statusMap: STATUS_MAP, detailFields: DETAIL,
      studentOptions: [],
      genForm: { internshipId: '' }, genDlg: { visible: false, submitting: false },
      entForm: { confirmBy: '', fileId: '' }, entDlg: { visible: false, submitting: false }, entRow: null,
      entAttachName: '', uploadingFile: false,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  created() { this.load() },
  methods: {
    confirmTone(s) { return s === 'CONFIRMED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    canReject(s) { return ['PENDING_STUDENT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL'].includes(s) },
    canVoid(s) { return ['DRAFT', 'PENDING_STUDENT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL'].includes(s) },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await agreementApi.getAgreements(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openGenerate() {
      this.genForm = { internshipId: '' }; this.genDlg.visible = true
      if (!this.studentOptions.length) {
        const res = await internStudentApi.getStudents({ page: 1, pageSize: 200 })
        if (res.code === 0) this.studentOptions = res.data.list.map((s) => ({ id: s.id, name: s.name, studentNo: s.studentNo, enterpriseName: s.enterpriseName }))
      }
    },
    async submitGenerate() {
      if (!this.genForm.internshipId) return toast.error('请选择实习学生')
      this.genDlg.submitting = true
      const res = await agreementApi.generate({ internshipId: this.genForm.internshipId })
      this.genDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '生成失败')
      this.genDlg.visible = false; toast.success('已生成协议草稿'); this.load()
    },
    openEnterprise(r) {
      this.entRow = r; this.entForm = { confirmBy: '', fileId: '' }; this.entAttachName = ''; this.entDlg.visible = true
    },
    async onEntFile(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await agreementApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.entForm.fileId = res.data.fileId; this.entAttachName = res.data.fileName || file.name
      toast.success('扫描件已上传')
    },
    async submitEnterprise() {
      this.entDlg.submitting = true
      const res = await agreementApi.enterpriseConfirm(this.entRow.id, { confirmBy: this.entForm.confirmBy, fileId: this.entForm.fileId })
      this.entDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      this.entDlg.visible = false; toast.success('已记录企业签署'); this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await agreementApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    async downloadAtt(att) {
      try { await agreementApi.downloadAttachment(att.fileId, att.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    confirmAct(r, kind) {
      const map = {
        issue: { title: '下发协议', content: `将「${r.studentName}」的协议下发给学生确认？`, danger: false, confirmText: '下发', requireReason: false },
        school: { title: '学校确认', content: `确认「${r.studentName}」三方协议生效？`, danger: false, confirmText: '确认生效', requireReason: false },
        archive: { title: '归档协议', content: `归档「${r.studentName}」的已生效协议？`, danger: false, confirmText: '归档', requireReason: false },
        reject: { title: '驳回协议', content: `驳回「${r.studentName}」的协议，原因将写入审计。`, danger: true, confirmText: '驳回', requireReason: true },
        void: { title: '作废协议', content: `作废「${r.studentName}」的协议，原因将写入审计。`, danger: true, confirmText: '作废', requireReason: true }
      }[kind]
      this.pending = { id: r.id, kind }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      let res
      if (p.kind === 'issue') res = await agreementApi.issue(p.id)
      else if (p.kind === 'school') res = await agreementApi.schoolConfirm(p.id)
      else if (p.kind === 'archive') res = await agreementApi.archive(p.id)
      else if (p.kind === 'reject') res = await agreementApi.reject(p.id, { reason })
      else res = await agreementApi.voidAgreement(p.id, { reason })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计'); this.load()
    },
    async doExport() {
      this.exporting = true
      const res = await agreementApi.exportAgreements({ keyword: this.keyword, status: this.statusFilter })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '三方协议台账.xlsx')
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
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(540px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
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
.fld__file { height: auto; padding: var(--space-1) 0; border: none; font-size: var(--font-size-xs); }
.fld__att { font-size: var(--font-size-xs); color: var(--success-700); }
.dline { display: flex; gap: var(--space-3); padding: var(--space-1) 0; font-size: var(--font-size-sm); }
.dline__lb { width: 96px; flex-shrink: 0; color: var(--text-tertiary); }
.dline__ct { color: var(--text-primary); word-break: break-all; }
.dtrail { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); }
.dtrail__t { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.dtrail__i { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 2px 0; }
</style>
