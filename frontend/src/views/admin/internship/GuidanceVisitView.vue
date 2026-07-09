<template>
  <ModulePageShell title="指导与巡访" subtitle="指导记录 · 教师巡访 · 安全隐患整改跟进"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="primary" @click="openCreate">＋ 新增{{ tab === 'guidance' ? '指导' : '巡访' }}记录</AppButton>
      <AppButton variant="secondary" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }"
        @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按学生姓名搜索" @keyup.enter="load" />
      <select v-if="tab === 'visit'" v-model="rectifyFilter" class="bar__sel" @change="load">
        <option value="">全部整改状态</option>
        <option value="PENDING">整改中</option>
        <option value="DONE">已整改</option>
        <option value="NONE">无需整改</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无{{ tab === 'guidance' ? '指导' : '巡访' }}记录</div>

    <table v-else class="tbl">
      <thead>
        <tr><th v-for="c in columns" :key="c.key">{{ c.label }}</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td v-for="c in columns" :key="c.key">
            <template v-if="c.key === 'rectifyStatus'">
              <AppStatusTag :type="rectifyTone(r.rectifyStatus)">{{ r.rectifyStatusLabel }}</AppStatusTag>
            </template>
            <template v-else-if="c.key === 'toRisk'">
              <AppStatusTag v-if="r.toRisk" type="danger">已转风险</AppStatusTag>
              <span v-else class="tbl__muted">—</span>
            </template>
            <template v-else>{{ r[c.key] || '—' }}</template>
          </td>
          <td class="tbl__ops">
            <button class="op" @click="openDetail(r)">详情</button>
            <template v-if="tab === 'guidance'">
              <button class="op op--danger" @click="openVoid(r)">撤销</button>
            </template>
            <template v-else-if="tab === 'visit' && r.rectifyStatus === 'PENDING'">
              <button class="op op--ok" @click="openRectify(r)">整改跟进</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 新增记录 -->
    <div v-if="createDlg.visible" class="modal" @click.self="createDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">新增{{ tab === 'guidance' ? '指导' : '巡访' }}记录</div>
        <div class="modal__body">
          <label class="fld"><span class="fld__lb">实习学生 *</span>
            <select v-model="form.internshipId" class="fld__ct">
              <option value="">请选择本人指导学生</option>
              <option v-for="s in studentOptions" :key="s.id" :value="s.id">{{ s.name }}（{{ s.studentNo }}）· {{ s.enterpriseName || '未分配企业' }}</option>
            </select>
          </label>
          <label class="fld"><span class="fld__lb">方式</span>
            <select v-model="form.method" class="fld__ct">
              <option v-for="m in methodOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
            </select>
          </label>

          <template v-if="tab === 'guidance'">
            <label class="fld"><span class="fld__lb">主题</span><input v-model="form.topic" class="fld__ct" placeholder="如：岗位适应 / 安全教育" /></label>
            <label class="fld"><span class="fld__lb">指导内容 *</span><textarea v-model="form.content" class="fld__ct fld__ta" placeholder="记录本次指导的具体内容"></textarea></label>
            <label class="fld"><span class="fld__lb">问题类型</span><input v-model="form.problemType" class="fld__ct" placeholder="如：岗位不符 / 考勤异常 / 安全隐患" /></label>
            <label class="fld"><span class="fld__lb">处理建议</span><input v-model="form.suggestion" class="fld__ct" placeholder="给学生/企业的处理建议" /></label>
            <label class="fld"><span class="fld__lb">下次跟进日期</span><input v-model="form.nextFollowDate" type="date" class="fld__ct" /></label>
            <div class="fld fld--row">
              <label class="chk"><input v-model="form.toRisk" type="checkbox" />标记为风险线索</label>
              <label class="chk"><input v-model="form.notifyCounselor" type="checkbox" />通知辅导员</label>
            </div>
          </template>

          <template v-else>
            <label class="fld"><span class="fld__lb">企业反馈</span><input v-model="form.enterpriseFeedback" class="fld__ct" placeholder="企业对学生的反馈" /></label>
            <label class="fld"><span class="fld__lb">学生反馈</span><input v-model="form.studentFeedback" class="fld__ct" placeholder="学生对岗位/实习的反馈" /></label>
            <label class="fld"><span class="fld__lb">安全隐患</span><input v-model="form.safetyIssue" class="fld__ct" placeholder="填写后自动进入「整改中」" /></label>
            <label class="fld"><span class="fld__lb">整改要求</span><input v-model="form.rectifyRequire" class="fld__ct" placeholder="填写后自动进入「整改中」" /></label>
            <label class="fld"><span class="fld__lb">整改截止</span><input v-model="form.rectifyDeadline" type="date" class="fld__ct" /></label>
            <label class="fld"><span class="fld__lb">月度小结</span><textarea v-model="form.monthlyReport" class="fld__ct fld__ta" placeholder="可选：本月巡访月报"></textarea></label>
          </template>

          <p class="modal__hint">仅可对本人指导学生新增，越权将被后端拒绝并写审计。</p>
        </div>
        <div class="modal__foot">
          <button class="mbtn" @click="createDlg.visible = false">取消</button>
          <button class="mbtn mbtn--primary" :disabled="createDlg.submitting" @click="submitCreate">
            {{ createDlg.submitting ? '提交中…' : '提交' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">{{ tab === 'guidance' ? '指导' : '巡访' }}详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <div v-for="f in detailFields" :key="f.key" class="dline">
              <span class="dline__lb">{{ f.label }}</span>
              <span class="dline__ct">{{ detailDlg.data[f.key] || '—' }}</span>
            </div>
            <div class="dtrail">
              <div class="dtrail__t">操作留痕</div>
              <div v-for="(t, i) in (detailDlg.data.auditTrail || [])" :key="i" class="dtrail__i">
                <b>{{ t.action }}</b> · {{ t.operator }} · {{ t.occurredAt }}
              </div>
              <div v-if="!(detailDlg.data.auditTrail || []).length" class="tbl__muted">暂无</div>
            </div>
          </template>
        </div>
        <div class="modal__foot">
          <button class="mbtn" @click="detailDlg.visible = false">关闭</button>
        </div>
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
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const COLS = {
  guidance: [
    { key: 'studentNo', label: '学号' }, { key: 'studentName', label: '姓名' },
    { key: 'advisorName', label: '指导教师' }, { key: 'methodLabel', label: '方式' },
    { key: 'topic', label: '主题' }, { key: 'problemType', label: '问题类型' },
    { key: 'toRisk', label: '风险线索' }, { key: 'createdAt', label: '记录时间' }
  ],
  visit: [
    { key: 'studentNo', label: '学号' }, { key: 'studentName', label: '姓名' },
    { key: 'advisorName', label: '巡访教师' }, { key: 'enterpriseName', label: '企业' },
    { key: 'methodLabel', label: '方式' }, { key: 'safetyIssue', label: '安全隐患' },
    { key: 'rectifyStatus', label: '整改状态' }, { key: 'visitAt', label: '巡访时间' }
  ]
}
const DETAIL = {
  guidance: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
    { key: 'methodLabel', label: '方式' }, { key: 'topic', label: '主题' },
    { key: 'content', label: '指导内容' }, { key: 'problemType', label: '问题类型' },
    { key: 'suggestion', label: '处理建议' }, { key: 'nextFollowDate', label: '下次跟进' }
  ],
  visit: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '巡访教师' },
    { key: 'enterpriseName', label: '企业' }, { key: 'methodLabel', label: '方式' },
    { key: 'enterpriseFeedback', label: '企业反馈' }, { key: 'studentFeedback', label: '学生反馈' },
    { key: 'safetyIssue', label: '安全隐患' }, { key: 'rectifyRequire', label: '整改要求' },
    { key: 'rectifyDeadline', label: '整改截止' }, { key: 'rectifyStatusLabel', label: '整改状态' },
    { key: 'monthlyReport', label: '月度小结' }
  ]
}
const METHODS = {
  guidance: [
    { value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '线上' }, { value: 'PHONE', label: '电话' },
    { value: 'VIDEO', label: '视频' }, { value: 'ENTERPRISE_FEEDBACK', label: '企业导师反馈' }
  ],
  visit: [{ value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '线上' }, { value: 'PHONE', label: '电话' }]
}

function emptyForm() {
  return {
    internshipId: '', method: 'ONSITE', topic: '', content: '', problemType: '', suggestion: '',
    nextFollowDate: '', toRisk: false, notifyCounselor: false,
    enterpriseFeedback: '', studentFeedback: '', safetyIssue: '', rectifyRequire: '',
    rectifyDeadline: '', monthlyReport: ''
  }
}

export default {
  name: 'GuidanceVisitView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppConfirmDialog },
  data() {
    return {
      tab: 'guidance',
      tabs: [{ key: 'guidance', label: '指导记录' }, { key: 'visit', label: '教师巡访' }],
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', rectifyFilter: '',
      studentOptions: [],
      form: emptyForm(),
      createDlg: { visible: false, submitting: false },
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    columns() { return COLS[this.tab] },
    detailFields() { return DETAIL[this.tab] },
    methodOptions() { return METHODS[this.tab] }
  },
  created() { this.load() },
  methods: {
    switchTab(k) { this.tab = k; this.keyword = ''; this.rectifyFilter = ''; this.load() },
    rectifyTone(s) { return s === 'PENDING' ? 'warning' : s === 'DONE' ? 'success' : 'default' },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      let res
      if (this.tab === 'guidance') {
        res = await guidanceVisitApi.getGuidances(params)
      } else {
        if (this.rectifyFilter) params.rectify = this.rectifyFilter
        res = await guidanceVisitApi.getVisits(params)
      }
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openCreate() {
      this.form = emptyForm()
      this.form.method = this.methodOptions[0].value
      this.createDlg.visible = true
      if (!this.studentOptions.length) {
        const res = await internStudentApi.getStudents({ page: 1, pageSize: 200 })
        if (res.code === 0) {
          this.studentOptions = res.data.list.map((s) => ({
            id: s.id, name: s.name, studentNo: s.studentNo, enterpriseName: s.enterpriseName
          }))
        }
      }
    },
    async submitCreate() {
      if (!this.form.internshipId) return toast.error('请选择实习学生')
      if (this.tab === 'guidance' && !this.form.content.trim()) return toast.error('指导内容必填')
      this.createDlg.submitting = true
      const res = this.tab === 'guidance'
        ? await guidanceVisitApi.createGuidance(this.form)
        : await guidanceVisitApi.createVisit(this.form)
      this.createDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      this.createDlg.visible = false
      toast.success('已保存并写审计')
      this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = this.tab === 'guidance'
        ? await guidanceVisitApi.getGuidanceDetail(r.id)
        : await guidanceVisitApi.getVisitDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    openVoid(r) {
      this.pending = { kind: 'void', id: r.id }
      this.cd = { visible: true, title: '撤销指导记录', content: `撤销「${r.studentName}」的指导记录，撤销原因将写入审计。`,
        danger: true, confirmText: '撤销', reasonLabel: '撤销原因', submitting: false }
    },
    openRectify(r) {
      this.pending = { kind: 'rectify', id: r.id }
      this.cd = { visible: true, title: '巡访整改跟进', content: `将「${r.studentName}」的安全隐患整改标记为「已整改」，跟进说明将写入审计。`,
        danger: false, confirmText: '标记已整改', reasonLabel: '整改跟进说明', submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      const res = p.kind === 'void'
        ? await guidanceVisitApi.voidGuidance(p.id, { reason })
        : await guidanceVisitApi.rectifyVisit(p.id, { status: 'DONE', note: reason })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false
      toast.success('操作成功，已写审计')
      this.load()
    },
    async doExport() {
      this.exporting = true
      const res = this.tab === 'guidance'
        ? await guidanceVisitApi.exportGuidances({ keyword: this.keyword })
        : await guidanceVisitApi.exportVisits({ keyword: this.keyword })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '台账.xlsx')
      toast.success(`已导出 ${res.data.rowCount} 条（水印 + 导出留痕）`)
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
.tbl th, .tbl td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-light); vertical-align: top; }
.tbl th { color: var(--text-tertiary); font-weight: var(--font-weight-medium); background: var(--bg-subtle); }
.tbl__muted { color: var(--text-disabled); }
.tbl__ops { display: flex; gap: var(--space-1); }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }

.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center;
  justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(560px, 100%);
  max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light);
  display: flex; justify-content: flex-end; gap: var(--space-2); }
.modal__hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.mbtn { height: 34px; padding: 0 var(--space-4); border: 1px solid var(--border-base); background: var(--bg-card);
  border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.mbtn--primary { background: var(--primary-600); border-color: var(--primary-600); color: #fff; }
.mbtn--primary:disabled { opacity: 0.6; cursor: not-allowed; }
.fld { display: flex; flex-direction: column; gap: var(--space-1); margin-bottom: var(--space-3); }
.fld--row { flex-direction: row; gap: var(--space-4); }
.fld__lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.fld__ct { height: 34px; border: 1px solid var(--border-base); border-radius: var(--radius-base);
  padding: 0 var(--space-2); font-size: var(--font-size-sm); }
.fld__ta { height: 72px; padding: var(--space-2); resize: vertical; }
.chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); }
.dline { display: flex; gap: var(--space-3); padding: var(--space-1) 0; font-size: var(--font-size-sm); }
.dline__lb { width: 88px; flex-shrink: 0; color: var(--text-tertiary); }
.dline__ct { color: var(--text-primary); word-break: break-all; }
.dtrail { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); }
.dtrail__t { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.dtrail__i { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 2px 0; }
</style>
