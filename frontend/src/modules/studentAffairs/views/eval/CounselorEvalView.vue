<template>
  <AppPageShell
    title="辅导员考评"
    subtitle="指标、评分、发布与申诉"
    role-name="学工处 / 组织人事"
    data-scope-name="按租户（学工处管理）"
    watermark-purpose="辅导员考评"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载考评..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">


      <form class="ce-toolbar" @submit.prevent="search">
        <label class="ce-filter">考评周期<AppTextInput v-model="filters.periodCode" placeholder="全部周期" /></label>
        <label class="ce-filter">状态<AppSelect v-model="filters.status" :options="statusOptions" placeholder="全部状态" @change="search" /></label>
        <AppButton variant="secondary" type="submit">查询</AppButton>
        <div class="ce-toolbar__actions">
          <AppButton variant="ghost" @click="indicatorVisible = true">考评指标</AppButton>
          <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" code="studentAffairs.counselorEval.manage" variant="primary" @click="openScore()">录入评分</AppPermissionButton>
        </div>
      </form>
      <p v-if="!indicators.length" class="ce-notice">尚未配置考评指标，请先配置指标再录入评分。</p>
        <DataTable v-if="evalRows.length" :columns="evalColumns" :rows="evalRows" row-key="evalId">
          <template #cell-idx="{ row }"><span class="ce-rank">{{ row.rowIndex }}</span></template>
          <template #cell-period="{ row }">{{ row.periodCode }}</template>
          <template #cell-counselor="{ row }"><span class="mp-cell-main">{{ row.counselorName || row.counselorKey }}</span><div v-if="row.counselorName" class="mp-cell-sub">{{ row.counselorKey }}</div></template>
          <template #cell-total="{ row }">{{ row.totalScore != null ? row.totalScore : '—' }}</template>
          <template #cell-weighted="{ row }">
            <b v-if="row.weightedTotalScore != null" title="按指标权重加权平均 Σ得分×权重/Σ权重">{{ row.weightedTotalScore }}</b>
            <span v-else class="ce-muted" title="指标未配权重，回退原始总分">—</span>
          </template>
          <template #cell-status="{ row }"><StatusTag :type="row.status === 'PUBLISHED' ? 'success' : 'default'" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-appeal="{ row }">
            <StatusTag v-if="row.appealStatus !== 'NONE'" :type="row.appealStatus === 'SUBMITTED' ? 'warning' : 'processing'" :label="row.appealStatusLabel" dot />
            <span v-else class="ce-muted">无申诉</span>
          </template>
          <template #cell-actions="{ row }">
            <div class="ce-ops">
              <AppPermissionButton v-if="row.status === 'DRAFT'" :allowed="canBtn('studentAffairs.counselorEval.manage')" code="studentAffairs.counselorEval.manage" size="sm" variant="ghost" @click="openScore(row)">修改评分</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" v-if="row.status === 'DRAFT'" code="studentAffairs.counselorEval.manage" size="sm" :loading="acting===row.evalId" @click="publishDlg = { visible: true, row }">发布</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" v-if="row.appealStatus === 'SUBMITTED'" code="studentAffairs.counselorEval.manage" size="sm" variant="secondary" :loading="acting===row.evalId" @click="reviewAppeal(row)">申诉复核</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无符合条件的考评记录</p>

      <AppPagination v-if="pagination.total" :page="pagination.page" :page-size="pagination.pageSize" :total="pagination.total" @change="changePage" />
    </AppGlobalState>

    <AppDrawer v-model:visible="indicatorVisible" title="考评指标" mode="modal" size="medium">
      <ul v-if="indicators.length" class="ce-indicator-list">
        <li v-for="i in indicators" :key="i.indicatorId"><strong>{{ i.name }}</strong><span>满分 {{ i.maxScore || 100 }}</span><span>权重 {{ i.weight == null ? '未设置' : i.weight + '%' }}</span></li>
      </ul>
      <p v-else class="ce-muted">暂无指标</p>
      <form class="ce-indicator-form" @submit.prevent="addIndicator">
        <AppFormItem label="指标名称" required><AppTextInput v-model="indForm.name" :disabled="acting === 'ind'" placeholder="如：学生日常管理" /></AppFormItem>
        <AppFormItem label="权重（%）"><AppNumberInput v-model="indForm.weight" :min="0" :disabled="acting === 'ind'" placeholder="选填" /></AppFormItem>
        <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" code="studentAffairs.counselorEval.manage" variant="primary" :loading="acting === 'ind'" @click="addIndicator">新增指标</AppPermissionButton>
      </form>
      <AppInlineAlert v-if="indError" type="danger" :description="indError" />
      <template #footer><AppButton variant="ghost" @click="indicatorVisible = false">关闭</AppButton></template>
    </AppDrawer>

    <AppDrawer v-model:visible="scoreVisible" :title="editing ? '修改评分' : '录入评分'" mode="modal" size="large">
        <div class="ce-scoreform">
          <label class="ce-field"><span>考评周期 *</span><AppTextInput v-model="scoreForm.periodCode" :disabled="editing || acting === 'save'" placeholder="如 2025-2026-1" /></label>
          <label class="ce-field"><span>辅导员标识 *</span><AppTextInput v-model="scoreForm.counselorKey" :disabled="editing || acting === 'save'" placeholder="工号/登录名" /></label>
          <label class="ce-field"><span>姓名</span><AppTextInput v-model="scoreForm.counselorName" :disabled="acting === 'save'" placeholder="用于列表快速识别" /></label>
        </div>
        <div class="ce-score-title">指标评分</div>
        <div class="ce-scores">
          <label v-for="i in indicators" :key="i.indicatorId" class="ce-field ce-score-item">
            <span>{{ i.name }}（满分{{ i.maxScore || 100 }}）</span>
            <AppNumberInput v-model="scoreForm.scores[i.indicatorId]" :min="0" :max="i.maxScore || 100" :disabled="acting === 'save'" />
          </label>
        </div>

      <AppInlineAlert v-if="scoreError" type="danger" :description="scoreError" />
      <template #footer>
        <span class="ce-total">原始总分 <b>{{ liveTotal }}</b></span>
        <AppButton variant="ghost" :disabled="acting === 'save'" @click="scoreVisible = false">关闭（保留本页输入）</AppButton>
        <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" code="studentAffairs.counselorEval.manage" variant="primary" :loading="acting === 'save'" :disabled="!indicators.length" @click="saveScore">保存评分</AppPermissionButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="publishDlg.visible" title="发布考评" confirm-text="确认发布" :submitting="Boolean(acting)" @confirm="publish(publishDlg.row)">
      <p v-if="publishDlg.row">{{ publishDlg.row.periodCode }} · {{ publishDlg.row.counselorName || publishDlg.row.counselorKey }}</p>
      <p>发布后不能直接修改评分，请确认分值无误。</p>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="appealDlg.visible" title="复核考评申诉" type="primary"
      confirm-text="提交复核" require-reason reason-label="复核意见（≥5字）"
      :submitting="appealDlg.submitting" @confirm="submitAppealReview"
    >
      <AppFormItem label="复核结论" required>
        <AppSelect v-model="appealDlg.result" :options="APPEAL_RESULTS" :disabled="appealDlg.submitting" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppPageShell, AppPermissionButton, AppPagination, AppInlineAlert, AppStatusTag,
  AppConfirmDialog, AppFormItem, AppNumberInput, AppSelect, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

/** 复核结论枚举：原为 window.prompt 让用户手打 UPHELD/ADJUSTED，打错即失败 */
const APPEAL_RESULTS = [
  { value: 'UPHELD', label: '维持原考评结果' },
  { value: 'ADJUSTED', label: '调整考评结果' }
]
const EVAL_COLUMNS = [
  { key: 'idx', title: '#', width: '48px' },
  { key: 'period', title: '周期' },
  { key: 'counselor', title: '辅导员' },
  { key: 'total', title: '总分' },
  { key: 'weighted', title: '加权总分' },
  { key: 'status', title: '状态' },
  { key: 'appeal', title: '申诉' },
  { key: 'actions', title: '操作', align: 'right', width: '220px' }
]

export default {
  name: 'CounselorEvalView',
  props: { ctx: { type: Object, default: null } },
  components: { AppGlobalState, AppPageShell, AppPermissionButton, AppPagination, AppInlineAlert, AppDrawer, AppButton, StatusTag: AppStatusTag,
    AppConfirmDialog, AppFormItem, AppNumberInput, AppSelect, AppTextInput, DataTable },
  data() {
    return {
      APPEAL_RESULTS,
      indicatorVisible: false, scoreVisible: false, editing: false, scoreError: '', indError: '', loadRequest: 0,
      scoreDrafts: {}, scoreKey: 'new',
      publishDlg: { visible: false, row: null },
      filters: { periodCode: '', status: '' }, pagination: { page: 1, pageSize: 20, total: 0 },
      statusOptions: [{ value: '', label: '全部状态' }, { value: 'DRAFT', label: '待发布' }, { value: 'PUBLISHED', label: '已发布' }],
      evalColumns: EVAL_COLUMNS,
      loading: true, acting: '', errorMessage: '', indicators: [], evals: [],
      indForm: { name: '', weight: null },
      scoreForm: { periodCode: '', counselorKey: '', counselorName: '', scores: {} },
      appealDlg: { visible: false, evalId: '', result: 'UPHELD', submitting: false }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    liveTotal() {
      return Math.round(Object.values(this.scoreForm.scores).reduce((a, v) => a + (Number(v) || 0), 0) * 100) / 100
    },
    evalRows() {
      return this.evals.map((e, i) => ({ ...e, rowIndex: (this.pagination.page - 1) * this.pagination.pageSize + i + 1 }))
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    search() { this.pagination.page = 1; this.load() },
    changePage(next) { this.pagination.page = next.page; this.pagination.pageSize = next.pageSize; this.load() },
    openScore(row) {
      if (!this.indicators.length) { this.indicatorVisible = true; return }
      this.scoreDrafts[this.scoreKey] = { ...this.scoreForm, scores: { ...this.scoreForm.scores } }
      this.scoreKey = row ? String(row.evalId) : 'new'
      const draft = this.scoreDrafts[this.scoreKey] || (row
        ? { periodCode: row.periodCode, counselorKey: row.counselorKey, counselorName: row.counselorName, scores: row.scores, remark: row.remark }
        : { periodCode: this.filters.periodCode, counselorKey: '', counselorName: '', scores: {} })
      this.scoreForm = { ...draft, scores: { ...draft.scores } }
      this.editing = Boolean(row)
      this.scoreError = ''
      this.scoreVisible = true
    },
    async load() {
      const requestId = ++this.loadRequest
      this.loading = true; this.errorMessage = ''
      const [ind, ev] = await Promise.all([
        studentAffairsApi.getEvalIndicators(),
        studentAffairsApi.getCounselorEvals({ ...this.filters, periodCode: this.filters.periodCode.trim(), page: this.pagination.page, pageSize: this.pagination.pageSize })
      ])
      if (requestId !== this.loadRequest) return
      if (ind.code === 0 && ind.data) this.indicators = ind.data.items || []
      else this.errorMessage = ind.message || '加载失败'
      if (ev.code === 0 && ev.data) { this.evals = ev.data.items || []; this.pagination.total = ev.data.total || 0 }
      else { this.evals = []; this.errorMessage = ev.message || '考评记录加载失败' }
      this.loading = false
    },
    async addIndicator() {
      const name = (this.indForm.name || '').trim()
      if (!name) { this.indError = '请输入指标名称'; return }
      if (this.acting) return
      this.indError = ''
      this.acting = 'ind'
      const res = await studentAffairsApi.createEvalIndicator({ name, weight: this.indForm.weight != null ? Number(this.indForm.weight) : undefined })
      this.acting = ''
      if (res.code === 0) { toast.success('已加指标'); this.indForm = { name: '', weight: null }; this.load() } else this.indError = res.message || '创建失败'
    },
    async saveScore() {
      const f = this.scoreForm
      const periodCode = (f.periodCode || '').trim()
      const counselorKey = (f.counselorKey || '').trim()
      if (!periodCode || !counselorKey) { this.scoreError = '请填写考评周期与辅导员工号 / 登录名'; return }
      if (this.acting) return
      this.scoreError = ''
      const scores = {}
      Object.keys(f.scores).forEach((k) => { if (f.scores[k] != null && f.scores[k] !== '') scores[k] = Number(f.scores[k]) })
      this.acting = 'save'
      const res = await studentAffairsApi.upsertCounselorEval({ periodCode, counselorKey, counselorName: (f.counselorName || '').trim() || undefined, scores, remark: f.remark })
      this.acting = ''
      if (res.code === 0) {
        toast.success('评分已保存，可在记录中核对并发布')
        this.scoreVisible = false
        delete this.scoreDrafts[this.scoreKey]
        this.scoreKey = 'new'
        this.editing = false
        this.scoreForm = this.scoreDrafts.new || { periodCode, counselorKey: '', counselorName: '', scores: {} }
        this.load()
      } else this.scoreError = res.message || '保存失败'
    },
    async publish(e) {
      if (!e || this.acting) return
      this.acting = e.evalId
      const res = await studentAffairsApi.publishCounselorEval(e.evalId, e.version)
      this.acting = ''
      if (res.code === 0) { toast.success('已发布'); this.publishDlg.visible = false; this.load() } else toast.error(res.message || '发布失败')
    },
    /** 复核申诉：结论走下拉（原让用户手打 UPHELD/ADJUSTED），意见走弹窗必填区（≥5字由组件校验） */
    reviewAppeal(e) {
      this.appealDlg = { visible: true, evalId: e.evalId, version: e.version, result: 'UPHELD', submitting: false }
    },
    async submitAppealReview({ reason }) {
      const d = this.appealDlg
      d.submitting = true
      this.acting = d.evalId
      const res = await studentAffairsApi.reviewEvalAppeal(d.evalId, { result: d.result, opinion: reason, version: d.version })
      d.submitting = false
      this.acting = ''
      if (res.code !== 0) { toast.error(res.message || '复核失败'); return }
      d.visible = false
      toast.success('已复核')
      this.load()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ce-toolbar { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid var(--border-light); }
.ce-filter { display: grid; gap: 6px; width: 170px; font-size: 13px; color: var(--text-secondary); }
.ce-toolbar__actions { margin-left: auto; display: flex; gap: 8px; }
.ce-notice { padding: 10px 0; color: var(--text-secondary); font-size: 13px; }
.ce-scoreform { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 16px; }
.ce-field { display: grid; gap: 6px; font-size: 13px; min-width: 0; }
.ce-score-title { margin: 24px 0 8px; font-size: 14px; font-weight: 600; }
.ce-scores { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 0 24px; }
.ce-score-item { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border-light); }
.ce-score-item > :last-child { width: 120px; flex-shrink: 0; }
.ce-indicator-list { margin: 0 0 20px; padding: 0; list-style: none; }
.ce-indicator-list li { display: flex; flex-wrap: wrap; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--border-light); font-size: 13px; }
.ce-indicator-list strong { flex: 1; }
.ce-indicator-list span, .ce-muted { color: var(--text-tertiary); }
.ce-indicator-form { display: grid; grid-template-columns: minmax(0,1fr) 140px; gap: 12px; }
.ce-indicator-form > :last-child { justify-self: start; }
.ce-total { margin-right: auto; align-self: center; color: var(--text-secondary); font-size: 13px; }
.ce-total b { font-size: 22px; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.ce-rank { color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.ce-ops { display: flex; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
.sa-empty { padding: 48px 16px; text-align: center; color: var(--text-tertiary); }
@media (max-width: 720px) { .ce-scoreform, .ce-scores { grid-template-columns: 1fr; } .ce-toolbar__actions { margin-left: 0; } }
</style>
