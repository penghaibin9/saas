<template>
  <ModulePageShell title="评价与成绩" subtitle="实习成绩 · 五项权重核算 · 复核发布 · 缺项不可发布"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.score.compute" variant="primary" @click="openCompute()">＋ 核算成绩</AppPermissionButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <!-- 权重配置 -->
    <div class="cfg">
      <span class="cfg__t">五项权重配置</span>
      <div v-for="w in weightDefs" :key="w.key" class="cfg__item">
        <span>{{ w.label }}</span><AppNumberInput v-model="cfg[w.key]" :min="0" :max="100" size="sm" />
      </div>
      <div class="cfg__item"><span>及格线</span><AppNumberInput v-model="cfg.passLine" :min="0" :max="100" size="sm" /></div>
      <span class="cfg__sum" :class="{ 'is-bad': weightSum !== 100 }">合计 {{ weightSum }}/100</span>
      <AppPermissionButton code="internship.score.config" variant="secondary" size="sm" :loading="savingCfg" @click="saveConfig">保存配置</AppPermissionButton>
    </div>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-total="{ row }">
        <b>{{ row.incomplete ? '—' : row.totalScore }}</b><span v-if="row.incomplete" class="miss">缺项</span>
      </template>
      <template #cell-pass="{ row }">{{ row.incomplete ? '—' : (row.isPass ? '及格' : '不及格') }}</template>
      <template #cell-status="{ row }"><AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag></template>
      <template #cell-actions="{ row }">
        <div class="ops">
          <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
          <AppPermissionButton v-if="['PENDING_REVIEW','PENDING_CALC'].includes(row.status)" code="internship.score.compute" variant="ghost" size="sm" @click="openCompute(row)">重算</AppPermissionButton>
          <AppPermissionButton v-if="row.status === 'PENDING_REVIEW'" code="internship.score.publish" variant="secondary" size="sm" :disabled="row.incomplete" @click="confirmAct(row, 'publish')">发布</AppPermissionButton>
          <AppPermissionButton v-if="row.status === 'PENDING_REVIEW'" code="internship.score.publish" variant="ghost" size="sm" @click="confirmAct(row, 'return')">退回</AppPermissionButton>
          <AppPermissionButton v-if="row.status === 'PUBLISHED'" code="internship.score.publish" variant="ghost" size="sm" :danger="true" @click="confirmAct(row, 'withdraw')">撤回</AppPermissionButton>
          <AppPermissionButton v-if="row.status === 'PUBLISHED'" code="internship.score.publish" variant="ghost" size="sm" @click="confirmAct(row, 'archive')">归档</AppPermissionButton>
        </div>
      </template>
    </DataTable>

    <!-- 核算 -->
    <div v-if="computeDlg.visible" class="modal" @click.self="computeDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">核算实习成绩</div>
        <div class="modal__body">
          <AppFormItem label="实习学生" required>
            <AppSelect v-model="cForm.internshipId" :options="studentSelectOptions" :disabled="cForm.locked" placeholder="请选择本人指导学生" />
          </AppFormItem>
          <div class="scores">
            <AppFormItem v-for="s in scoreInputs" :key="s.key" :label="s.label" class="score">
              <AppNumberInput v-model="cForm[s.key]" :min="0" :max="100" />
            </AppFormItem>
          </div>
          <p class="hint">各项 0-100。企业评价分留空时自动取「已通过企业评价」均分；缺项将标记且不可发布。权重取上方配置。</p>
        </div>
        <div class="modal__foot">
          <AppButton variant="ghost" @click="computeDlg.visible = false">取消</AppButton>
          <AppButton variant="primary" :loading="computeDlg.submitting" @click="submitCompute">核算</AppButton>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">成绩详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <div class="sec-t">核算/发布留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
          </template>
        </div>
        <div class="modal__foot"><AppButton variant="secondary" @click="detailDlg.visible = false">关闭</AppButton></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppSelect, AppNumberInput, AppFormItem } from '@/components/common'
import { scoreApi } from '@/modules/internship/api/score.api'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { toast } from '@/utils/toast'

const WEIGHTS = [
  { key: 'checkinWeight', label: '打卡' }, { key: 'weeklyWeight', label: '周报' },
  { key: 'monthlyWeight', label: '月报' }, { key: 'enterpriseWeight', label: '企业' }, { key: 'schoolWeight', label: '学校' }
]
const SCORE_INPUTS = [
  { key: 'checkinScore', label: '打卡' }, { key: 'weeklyScore', label: '周报' },
  { key: 'monthlyScore', label: '月报总结' }, { key: 'enterpriseScore', label: '企业评价' }, { key: 'schoolScore', label: '学校评价' }
]
const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '100px' }, { key: 'studentName', title: '姓名' },
  { key: 'checkinScore', title: '打卡' }, { key: 'weeklyScore', title: '周报' }, { key: 'monthlyScore', title: '月报' },
  { key: 'enterpriseScore', title: '企业' }, { key: 'schoolScore', title: '学校' },
  { key: 'total', title: '总分' }, { key: 'pass', title: '及格' }, { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', width: '260px' }
]
const STATUS_MAP = { PENDING_CALC: '待核算', PENDING_REVIEW: '待复核', PUBLISHED: '已发布', WITHDRAWN: '已撤回', ARCHIVED: '已归档' }
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'statusLabel', label: '状态' },
  { key: 'totalScore', label: '总分' }, { key: 'passLine', label: '及格线' },
  { key: 'checkinScore', label: '打卡分' }, { key: 'weeklyScore', label: '周报分' },
  { key: 'monthlyScore', label: '月报分' }, { key: 'enterpriseScore', label: '企业分' },
  { key: 'schoolScore', label: '学校分' }, { key: 'incompleteReason', label: '缺项' }
]

export default {
  name: 'ScoreView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppSelect, AppNumberInput, AppFormItem },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', columns: COLUMNS, weightDefs: WEIGHTS, scoreInputs: SCORE_INPUTS,
      statusOptions: Object.entries(STATUS_MAP).map(([value, label]) => ({ value, label })),
      cfg: { checkinWeight: 20, weeklyWeight: 20, monthlyWeight: 10, enterpriseWeight: 30, schoolWeight: 20, passLine: 60 },
      savingCfg: false, studentOptions: [],
      cForm: { internshipId: '', locked: false, checkinScore: null, weeklyScore: null, monthlyScore: null, enterpriseScore: null, schoolScore: null },
      computeDlg: { visible: false, submitting: false },
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    weightSum() { return WEIGHTS.reduce((a, w) => a + (Number(this.cfg[w.key]) || 0), 0) },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    studentSelectOptions() { return this.studentOptions.map((s) => ({ value: s.id, label: `${s.name}（${s.studentNo}）` })) },
    detailItems() { const d = this.detailDlg.data || {}; return DETAIL.map((f) => ({ label: f.label, value: d[f.key] })) },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.reason || t.detail.comment || (t.detail.missing || []).join('、')), at: t.occurredAt
      }))
    }
  },
  created() { this.loadConfig(); this.load() },
  methods: {
    exportFn() { return scoreApi.exportScores({ keyword: this.keyword, status: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    async loadConfig() { const res = await scoreApi.getConfig(); if (res.code === 0) this.cfg = { ...this.cfg, ...res.data } },
    async saveConfig() {
      if (this.weightSum !== 100) return toast.error(`五项权重之和须为 100，当前 ${this.weightSum}`)
      this.savingCfg = true
      const res = await scoreApi.saveConfig(this.cfg)
      this.savingCfg = false
      if (res.code !== 0) return toast.error(res.message || '保存失败')
      toast.success('权重配置已保存')
    },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await scoreApi.getScores(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openCompute(row) {
      this.cForm = { internshipId: '', locked: false, checkinScore: null, weeklyScore: null, monthlyScore: null, enterpriseScore: null, schoolScore: null }
      if (row && row.internId) {
        this.cForm.internshipId = row.internId; this.cForm.locked = true
        this.cForm.checkinScore = row.checkinScore; this.cForm.weeklyScore = row.weeklyScore
        this.cForm.monthlyScore = row.monthlyScore; this.cForm.enterpriseScore = row.enterpriseScore; this.cForm.schoolScore = row.schoolScore
      }
      this.computeDlg.visible = true
      if (!this.studentOptions.length) {
        const res = await internStudentApi.getStudents({ page: 1, pageSize: 200 })
        if (res.code === 0) this.studentOptions = res.data.list.map((s) => ({ id: s.id, name: s.name, studentNo: s.studentNo }))
      }
    },
    async submitCompute() {
      if (!this.cForm.internshipId) return toast.error('请选择实习学生')
      this.computeDlg.submitting = true
      const body = { internshipId: this.cForm.internshipId }
      for (const s of SCORE_INPUTS) if (this.cForm[s.key] !== null && this.cForm[s.key] !== '') body[s.key] = this.cForm[s.key]
      const res = await scoreApi.compute(body)
      this.computeDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '核算失败')
      this.computeDlg.visible = false
      toast.success(res.data.incomplete ? `已核算（缺项：${res.data.incompleteReason}）` : `已核算，总分 ${res.data.total}`)
      this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await scoreApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    confirmAct(r, kind) {
      const map = {
        publish: { title: '发布成绩', content: `发布「${r.studentName}」的实习成绩（总分 ${r.totalScore}）？发布后学生可见。`, danger: false, confirmText: '发布', requireReason: false },
        return: { title: '退回重算', content: `退回「${r.studentName}」的成绩到待核算？`, danger: false, confirmText: '退回', requireReason: false },
        withdraw: { title: '撤回成绩', content: `撤回「${r.studentName}」的已发布成绩，原因将写审计。`, danger: true, confirmText: '撤回', requireReason: true },
        archive: { title: '归档成绩', content: `归档「${r.studentName}」的已发布成绩？`, danger: false, confirmText: '归档', requireReason: false }
      }[kind]
      this.pending = { id: r.id, kind }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      let res
      if (p.kind === 'publish') res = await scoreApi.publish(p.id)
      else if (p.kind === 'return') res = await scoreApi.returnRecalc(p.id, { reason })
      else if (p.kind === 'withdraw') res = await scoreApi.withdraw(p.id, { reason })
      else res = await scoreApi.archive(p.id)
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计'); this.load()
    }
  }
}
</script>

<style scoped>
.cfg { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); margin-bottom: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-base); }
.cfg__t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); }
.cfg__item { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--text-secondary); }
.cfg__item :deep(.app-number-input) { width: 64px; }
.cfg__sum { font-size: var(--font-size-sm); color: var(--success-700); }
.cfg__sum.is-bad { color: var(--danger-600); }
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.miss { color: var(--danger-600); font-size: var(--font-size-xs); margin-left: 4px; }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.scores { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.score { width: calc(20% - var(--space-2)); min-width: 92px; }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(600px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
