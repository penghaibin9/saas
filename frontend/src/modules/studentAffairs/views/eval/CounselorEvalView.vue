<template>
  <AppPageShell
    title="辅导员考评"
    subtitle="考评指标配置 → 按周期录入各项评分（自动汇总总分）→ 发布 → 辅导员申诉复核。"
    role-name="学工处 / 组织人事"
    data-scope-name="按租户（学工处管理）"
    watermark-purpose="辅导员考评"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载考评..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前考评工作</span>
          <h2 class="sa-summary-strip__title">先确认指标与权重，再按周期录入评分；发布后仅处理正式申诉</h2>
          <p class="sa-summary-strip__text">当前配置 {{ indicators.length }} 项指标，共有 {{ evalRows.length }} 条已加载考评记录。评分发布前可继续修改，发布后进入正式结果与申诉复核阶段。</p>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="辅导员考评流程">
        <div class="sa-workflow-step" data-step="1"><strong>配置指标</strong><br>明确指标名称、权重和评分口径</div>
        <div class="sa-workflow-step" data-step="2"><strong>录入评分</strong><br>选择周期与辅导员，逐项填写分值</div>
        <div class="sa-workflow-step" data-step="3"><strong>发布结果</strong><br>核对总分、加权分和排名后发布</div>
        <div class="sa-workflow-step" data-step="4"><strong>申诉复核</strong><br>对正式申诉作出维持或调整结论</div>
      </div>

      <AppSectionCard title="一、考评指标">
        <p class="ce-section-hint">指标决定评分结构。新增前请确认名称清楚、权重口径一致，避免同一含义重复建项。</p>
        <div class="ce-indbar">
          <div class="ce-inds">
            <span v-for="i in indicators" :key="i.indicatorId" class="ce-indtag">
              {{ i.name }}<em>{{ i.weight != null ? (i.weight + '%') : '' }}</em>
            </span>
            <span v-if="!indicators.length" class="ce-muted">尚未配置指标，请先在右侧新增指标后再录入评分。</span>
          </div>
          <div class="ce-indadd">
            <AppTextInput v-model="indForm.name" placeholder="指标名称" />
            <AppNumberInput v-model="indForm.weight" class="ce-input--sm" :min="0" placeholder="权重%" />
            <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" code="studentAffairs.counselorEval.manage" size="sm" :loading="acting==='ind'" @click="addIndicator">加指标</AppPermissionButton>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="二、录入 / 修改评分（发布前）">
        <p class="ce-section-hint">先填写考评周期和辅导员标识，再逐项录入分值。页面会即时汇总原始总分，最终加权结果以保存后的正式记录为准。</p>
        <div class="ce-scoreform ce-form-block">
          <label class="ce-field"><span>考评周期 *</span><AppTextInput v-model="scoreForm.periodCode" placeholder="如 2025-2026-1" /></label>
          <label class="ce-field"><span>辅导员标识 *</span><AppTextInput v-model="scoreForm.counselorKey" placeholder="工号/登录名" /></label>
          <label class="ce-field"><span>姓名</span><AppTextInput v-model="scoreForm.counselorName" placeholder="用于列表快速识别" /></label>
        </div>
        <div class="ce-score-title">指标评分</div>
        <div class="ce-scores">
          <label v-for="i in indicators" :key="i.indicatorId" class="ce-field ce-score-item">
            <span>{{ i.name }}（满分{{ i.maxScore || 100 }}）</span>
            <AppNumberInput v-model="scoreForm.scores[i.indicatorId]" :min="0" />
          </label>
        </div>
        <div class="ce-actions">
          <span class="ce-total">当前合计 <b>{{ liveTotal }}</b></span>
          <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" code="studentAffairs.counselorEval.manage" :loading="acting==='save'" :disabled="!indicators.length" @click="saveScore">保存评分</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="三、考评记录与发布">
        <p class="ce-section-hint">记录按总分排名展示。发布前重点核对周期、辅导员、原始总分和加权总分；有正式申诉时再进入复核。</p>
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
              <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" v-if="row.status === 'DRAFT'" code="studentAffairs.counselorEval.manage" size="sm" :loading="acting===row.evalId" @click="publish(row)">发布</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.counselorEval.manage')" v-if="row.appealStatus === 'SUBMITTED'" code="studentAffairs.counselorEval.manage" size="sm" variant="secondary" :loading="acting===row.evalId" @click="reviewAppeal(row)">申诉复核</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无考评记录。请先配置指标并录入本周期辅导员评分。</p>
      </AppSectionCard>
    </AppGlobalState>

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
import { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag,
  AppConfirmDialog, AppFormItem, AppNumberInput, AppSelect, AppTextInput } from '@/components/common'
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
  { key: 'actions', title: '操作', align: 'right', width: '160px' }
]

export default {
  name: 'CounselorEvalView',
  props: { ctx: { type: Object, default: null } },
  components: { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag,
    AppConfirmDialog, AppFormItem, AppNumberInput, AppSelect, AppTextInput, DataTable },
  data() {
    return {
      APPEAL_RESULTS,
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
      return this.evals.map((e, i) => ({ ...e, rowIndex: i + 1 }))
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      const [ind, ev] = await Promise.all([
        studentAffairsApi.getEvalIndicators(),
        // 待服务端全量统计：考评工作台仅加载 API 单页上限。
        studentAffairsApi.getCounselorEvals({ pageSize: 200 })
      ])
      if (ind.code === 0 && ind.data) this.indicators = ind.data.items || []
      else this.errorMessage = ind.message || '加载失败'
      this.evals = (ev.code === 0 && ev.data) ? (ev.data.items || []) : []
      this.loading = false
    },
    async addIndicator() {
      const name = (this.indForm.name || '').trim()
      if (!name) { toast.error('请输入指标名称'); return }
      this.acting = 'ind'
      const res = await studentAffairsApi.createEvalIndicator({ name, weight: this.indForm.weight != null ? Number(this.indForm.weight) : undefined })
      this.acting = ''
      if (res.code === 0) { toast.success('已加指标'); this.indForm = { name: '', weight: null }; this.load() } else toast.error(res.message || '创建失败')
    },
    async saveScore() {
      const f = this.scoreForm
      const periodCode = (f.periodCode || '').trim()
      const counselorKey = (f.counselorKey || '').trim()
      if (!periodCode || !counselorKey) { toast.error('周期与辅导员标识必填'); return }
      const scores = {}
      Object.keys(f.scores).forEach((k) => { if (f.scores[k] != null && f.scores[k] !== '') scores[k] = Number(f.scores[k]) })
      this.acting = 'save'
      const res = await studentAffairsApi.upsertCounselorEval({ periodCode, counselorKey, counselorName: (f.counselorName || '').trim() || undefined, scores })
      this.acting = ''
      if (res.code === 0) { toast.success('评分已保存'); this.load() } else toast.error(res.message || '保存失败')
    },
    async publish(e) {
      this.acting = e.evalId
      const res = await studentAffairsApi.publishCounselorEval(e.evalId, e.version)
      this.acting = ''
      if (res.code === 0) { toast.success('已发布'); this.load() } else toast.error(res.message || '发布失败')
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
.ce-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.ce-indbar { display: flex; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; align-items: flex-start; }
.ce-inds { display: flex; gap: var(--space-2); flex-wrap: wrap; flex: 1 1 420px; min-width: 0; }
.ce-indtag { border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-full); padding: 6px 12px; background: var(--primary-50, #eff6ff); color: var(--text-primary); font-size: var(--font-size-sm); }
.ce-indtag em { color: var(--text-tertiary); font-style: normal; margin-left: 4px; }
.ce-indadd { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; flex: 1 1 360px; justify-content: flex-end; }
.ce-indadd > * { flex: 1 1 140px; min-width: 120px; }
.ce-indadd > .app-perm-btn { flex: 0 0 auto; min-width: 0; }
.ce-input--sm { flex: 0 0 110px; min-width: 90px; width: 90px; }
.ce-form-block { padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-section); }
.ce-scoreform, .ce-scores { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.ce-score-title { margin: var(--space-4) 0 var(--space-2); color: var(--text-primary); font-weight: 700; }
.ce-field { display: flex; flex-direction: column; gap: 5px; font-size: var(--font-size-sm); min-width: 0; }
.ce-score-item { padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-card); }
.ce-actions { display: flex; justify-content: flex-end; align-items: center; gap: var(--space-4); margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--border-light); }
.ce-total { color: var(--text-secondary); }
.ce-total b { margin-left: 4px; font-size: var(--font-size-xl); color: var(--color-primary); font-variant-numeric: tabular-nums; }
.ce-rank { display: inline-grid; place-items: center; min-width: 26px; height: 26px; border-radius: 50%; background: var(--bg-section); color: var(--text-secondary); font-weight: 700; }
.ce-muted { color: var(--text-tertiary); }
.ce-ops { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
@media (max-width: 960px) { .ce-scoreform, .ce-scores { grid-template-columns: 1fr; } .ce-indadd { justify-content: flex-start; } }
@media (max-width: 640px) { .ce-actions { align-items: stretch; flex-direction: column; } .ce-actions > * { width: 100%; } }
@import '@/styles/module-page.css';
</style>
