<template>
  <ModulePageShell title="指导巡访管理" subtitle="记录指导教师联系学生、企业沟通、现场巡访和问题整改情况 · 指导记录 · 教师巡访 · 安全隐患整改跟进"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.guidance.create" variant="primary" @click="openCreate">＋ 新增{{ tab === 'guidance' ? '指导' : '巡访' }}记录</AppPermissionButton>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/guidance-plan')">指导计划</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div v-if="statsCards.length" class="stats">
      <div v-for="c in statsCards" :key="c.label" class="stats__card">
        <div class="stats__val" :class="{ 'is-warn': c.warn }">{{ c.value }}</div>
        <div class="stats__lbl">{{ c.label }}</div>
      </div>
    </div>

    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-if="tab === 'visit'" v-model="rectifyFilter" :options="rectifyOptions" allow-clear @change="reload" />
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-rectifyStatus="{ row }"><AppStatusTag :type="rectifyTone(row.rectifyStatus)">{{ row.rectifyStatusLabel }}</AppStatusTag></template>
      <template #cell-toRisk="{ row }"><AppStatusTag v-if="row.toRisk" type="danger">已转风险</AppStatusTag><span v-else>—</span></template>
      <template #cell-actions="{ row }">
        <div class="ops">
          <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
          <AppPermissionButton v-if="tab === 'guidance'" code="internship.guidance.void" variant="ghost" size="sm" :danger="true" @click="openVoid(row)">撤销</AppPermissionButton>
          <AppPermissionButton v-if="tab === 'visit' && row.rectifyStatus === 'PENDING'" code="internship.visit.rectify" variant="secondary" size="sm" @click="openRectify(row)">整改跟进</AppPermissionButton>
        </div>
      </template>
    </DataTable>

    <!-- 新增 -->
    <div v-if="createDlg.visible" class="modal" @click.self="createDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">新增{{ tab === 'guidance' ? '指导' : '巡访' }}记录</div>
        <div class="modal__body">
          <AppFormItem label="实习学生" required>
            <AppStudentPicker
              v-model="form.internshipId"
              :remote-search="searchInternStudents"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="方式"><AppSelect v-model="form.method" :options="methodOptions" /></AppFormItem>
          <template v-if="tab === 'guidance'">
            <AppFormItem label="主题"><AppTextInput v-model="form.topic" placeholder="如：岗位适应 / 安全教育" /></AppFormItem>
            <AppFormItem label="指导内容" required><AppTextarea v-model="form.content" :rows="3" placeholder="记录本次指导的具体内容" /></AppFormItem>
            <AppFormItem label="问题类型"><AppTextInput v-model="form.problemType" placeholder="如：岗位不符 / 考勤异常 / 安全隐患" /></AppFormItem>
            <AppFormItem label="处理建议"><AppTextInput v-model="form.suggestion" placeholder="给学生/企业的处理建议" /></AppFormItem>
            <AppFormItem label="下次跟进日期"><AppDatePicker v-model="form.nextFollowDate" /></AppFormItem>
            <div class="chks">
              <label class="chk"><input v-model="form.toRisk" type="checkbox" />标记为风险线索</label>
              <label class="chk"><input v-model="form.notifyCounselor" type="checkbox" />通知辅导员</label>
            </div>
          </template>
          <template v-else>
            <AppFormItem label="企业反馈"><AppTextInput v-model="form.enterpriseFeedback" placeholder="企业对学生的反馈" /></AppFormItem>
            <AppFormItem label="学生反馈"><AppTextInput v-model="form.studentFeedback" placeholder="学生对岗位/实习的反馈" /></AppFormItem>
            <AppFormItem label="安全隐患"><AppTextInput v-model="form.safetyIssue" placeholder="填写后自动进入「整改中」" /></AppFormItem>
            <AppFormItem label="整改要求"><AppTextInput v-model="form.rectifyRequire" placeholder="填写后自动进入「整改中」" /></AppFormItem>
            <AppFormItem label="整改截止"><AppDatePicker v-model="form.rectifyDeadline" /></AppFormItem>
            <AppFormItem label="月度小结"><AppTextarea v-model="form.monthlyReport" :rows="2" placeholder="可选：本月巡访月报" /></AppFormItem>
          </template>
          <AppFormItem label="附件（可选，走文件中心）">
            <input type="file" class="file" @change="onFilePick" />
            <span v-if="form.fileId" class="att">已上传：{{ attachName }}</span>
            <span v-else-if="uploadingFile" class="att">上传中…</span>
          </AppFormItem>
          <p class="hint">仅可对本人指导学生新增，越权将被后端拒绝并写审计。</p>
        </div>
        <div class="modal__foot">
          <AppButton variant="ghost" @click="createDlg.visible = false">取消</AppButton>
          <AppButton variant="primary" :loading="createDlg.submitting" @click="submitCreate">提交</AppButton>
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
            <AppDescriptionList :items="detailItems" :columns="1" />
            <template v-if="detailDlg.data.attachment">
              <div class="sec-t">附件</div>
              <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
            </template>
            <div class="sec-t">操作留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
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
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppSelect, AppTextInput, AppTextarea, AppFormItem,
  AppFilePreview, AppDatePicker, AppStudentPicker } from '@/components/common'
import { searchInternStudents } from './components/entityPickerAdapters'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { toast } from '@/utils/toast'

const COLS = {
  guidance: [
    { key: 'studentNo', title: '学号', width: '100px' }, { key: 'studentName', title: '姓名' },
    { key: 'advisorName', title: '指导教师' }, { key: 'methodLabel', title: '方式' },
    { key: 'topic', title: '主题' }, { key: 'problemType', title: '问题类型' },
    { key: 'toRisk', title: '风险线索' }, { key: 'createdAt', title: '记录时间' }, { key: 'actions', title: '操作', width: '150px' }
  ],
  visit: [
    { key: 'studentNo', title: '学号', width: '100px' }, { key: 'studentName', title: '姓名' },
    { key: 'advisorName', title: '巡访教师' }, { key: 'enterpriseName', title: '企业' },
    { key: 'methodLabel', title: '方式' }, { key: 'safetyIssue', title: '安全隐患' },
    { key: 'rectifyStatus', title: '整改状态' }, { key: 'visitAt', title: '巡访时间' }, { key: 'actions', title: '操作', width: '170px' }
  ]
}
const DETAIL = {
  guidance: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' }, { key: 'methodLabel', label: '方式' },
    { key: 'topic', label: '主题' }, { key: 'content', label: '指导内容' }, { key: 'problemType', label: '问题类型' },
    { key: 'suggestion', label: '处理建议' }, { key: 'nextFollowDate', label: '下次跟进' }
  ],
  visit: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '巡访教师' }, { key: 'enterpriseName', label: '企业' },
    { key: 'methodLabel', label: '方式' }, { key: 'enterpriseFeedback', label: '企业反馈' }, { key: 'studentFeedback', label: '学生反馈' },
    { key: 'safetyIssue', label: '安全隐患' }, { key: 'rectifyRequire', label: '整改要求' }, { key: 'rectifyDeadline', label: '整改截止' },
    { key: 'rectifyStatusLabel', label: '整改状态' }, { key: 'monthlyReport', label: '月度小结' }
  ]
}
const METHODS = {
  guidance: [
    { value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '线上' }, { value: 'PHONE', label: '电话' },
    { value: 'VIDEO', label: '视频' }, { value: 'ENTERPRISE_FEEDBACK', label: '企业导师反馈' }
  ],
  visit: [{ value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '线上' }, { value: 'PHONE', label: '电话' }]
}
const RECTIFY_OPTIONS = [{ label: '整改中', value: 'PENDING' }, { label: '已整改', value: 'DONE' }, { label: '无需整改', value: 'NONE' }]
const PANEL_PRESETS = {
  plan: () => ({ redirect: '/admin/internship/guidance-plan' }),
  'insufficient-warning': () => ({ redirect: '/admin/internship/guidance-plan?insufficient=1' }),
  guidance: () => ({ tab: 'guidance', rectifyFilter: '' }),
  visit: () => ({ tab: 'visit', rectifyFilter: '' }),
  'visit-plan': () => ({ tab: 'visit', rectifyFilter: '' }),
  'visit-issue': () => ({ tab: 'visit', rectifyFilter: '' }),
  rectify: () => ({ tab: 'visit', rectifyFilter: 'PENDING' })
}
const TAB_PANEL = { guidance: 'guidance', visit: 'visit' }

function emptyForm() {
  return { internshipId: '', method: 'ONSITE', topic: '', content: '', problemType: '', suggestion: '',
    nextFollowDate: '', toRisk: false, notifyCounselor: false, enterpriseFeedback: '', studentFeedback: '',
    safetyIssue: '', rectifyRequire: '', rectifyDeadline: '', monthlyReport: '', fileId: '' }
}

export default {
  name: 'GuidanceVisitView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppSelect,
    AppTextInput, AppTextarea, AppFormItem, AppFilePreview, AppDatePicker, AppStudentPicker, ModuleSummaryStrip },
  data() {
    return {
      tab: 'guidance',
      tabs: [{ key: 'guidance', label: '指导记录' }, { key: 'visit', label: '教师巡访' }],
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', rectifyFilter: '', rectifyOptions: RECTIFY_OPTIONS,
      form: emptyForm(), attachName: '', uploadingFile: false,
      createDlg: { visible: false, submitting: false },
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校',
      guidanceStats: null,
      visitStats: null
    }
  },
  computed: {
    statsCards() {
      if (this.tab === 'guidance' && this.guidanceStats) {
        const g = this.guidanceStats
        return [
          { label: '在岗学生', value: g.studentCount },
          { label: '人均指导次数', value: g.avgCount },
          { label: `不足 ${g.threshold} 次`, value: g.insufficientCount, warn: g.insufficientCount > 0 }
        ]
      }
      if (this.tab === 'visit' && this.visitStats) {
        const v = this.visitStats
        return [
          { label: '巡访记录', value: v.totalVisits },
          { label: '整改中', value: v.pendingRectify, warn: v.pendingRectify > 0 },
          { label: '已整改', value: v.doneRectify }
        ]
      }
      return []
    },
    summaryMetrics() {
      return this.statsCards.slice(0, 5).map((c) => ({ label: c.label, value: c.value }))
    },
    columns() { return COLS[this.tab] },
    detailFields() { return DETAIL[this.tab] },
    methodOptions() { return METHODS[this.tab] },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    detailItems() { const d = this.detailDlg.data || {}; return this.detailFields.map((f) => ({ label: f.label, value: d[f.key] })) },
    attachmentFiles() { const a = this.detailDlg.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.note || t.detail.reason || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'guidance').toString())
      }
    },
    '$route.query.keyword': {
      immediate: true,
      handler(kw) {
        if (kw && String(kw) !== this.keyword) {
          this.keyword = String(kw)
          this.page = 1
          this.load()
        }
      }
    }
  },
  methods: {
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.guidance
      const cfg = preset()
      if (cfg.redirect) {
        this.$router.replace(cfg.redirect)
        return
      }
      const { tab, rectifyFilter } = cfg
      this.tab = tab
      if (!this.$route.query.keyword) this.keyword = ''
      this.rectifyFilter = rectifyFilter
      this.page = 1
      this.loadStats()
      this.load()
    },
    async loadStats() {
      if (this.tab === 'guidance') {
        const res = await guidanceVisitApi.getGuidanceStats(2)
        if (res.code === 0) this.guidanceStats = res.data
      } else {
        const res = await guidanceVisitApi.getVisitStats()
        if (res.code === 0) this.visitStats = res.data
      }
    },
    rectifyTone(s) { return s === 'PENDING' ? 'warning' : s === 'DONE' ? 'success' : 'default' },
    exportFn() {
      return this.tab === 'guidance'
        ? guidanceVisitApi.exportGuidances({ keyword: this.keyword })
        : guidanceVisitApi.exportVisits({ keyword: this.keyword })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    switchTab(k) {
      const panel = TAB_PANEL[k] || k
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
      } else {
        this.applyPanel(panel)
      }
    },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      let res
      if (this.tab === 'guidance') res = await guidanceVisitApi.getGuidances(params)
      else { if (this.rectifyFilter) params.rectify = this.rectifyFilter; res = await guidanceVisitApi.getVisits(params) }
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    searchInternStudents,
    openCreate() {
      // 学生候选改为选择器内按关键字远程搜索，不再一次性预载 200 条
      this.form = emptyForm(); this.attachName = ''; this.form.method = this.methodOptions[0].value; this.createDlg.visible = true
    },
    async onFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await guidanceVisitApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
      toast.success('附件已上传')
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
      this.createDlg.visible = false; toast.success('已保存并写审计'); this.loadStats(); this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = this.tab === 'guidance' ? await guidanceVisitApi.getGuidanceDetail(r.id) : await guidanceVisitApi.getVisitDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    async downloadAtt() {
      const a = this.detailDlg.data?.attachment
      if (!a) return
      try { await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
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
      this.cd.visible = false; toast.success('操作成功，已写审计'); this.loadStats(); this.load()
    }
  }
}
</script>

<style scoped>
.stats { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-3); }
.stats__card { min-width: 120px; padding: var(--space-3); background: var(--bg-card); border: 1px solid var(--border-light); border-radius: 8px; }
.stats__val { font-size: var(--font-size-xl); font-weight: 600; }
.stats__val.is-warn { color: var(--danger-600); }
.stats__lbl { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: var(--space-1); }
.tabs { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.tabs__btn { border: none; background: none; padding: var(--space-2) var(--space-3); cursor: pointer; color: var(--text-secondary); font-size: var(--font-size-sm); border-bottom: 2px solid transparent; }
.tabs__btn.is-active { color: var(--primary-700); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-medium); }
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.chks { display: flex; gap: var(--space-4); margin-bottom: var(--space-3); }
.chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); }
.file { font-size: var(--font-size-xs); }
.att { font-size: var(--font-size-xs); color: var(--success-700); margin-left: var(--space-2); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(560px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
