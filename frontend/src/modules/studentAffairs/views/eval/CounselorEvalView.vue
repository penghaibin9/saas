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
      <AppSectionCard title="考评指标">
        <div class="ce-indbar">
          <div class="ce-inds">
            <span v-for="i in indicators" :key="i.indicatorId" class="ce-indtag">
              {{ i.name }}<em>{{ i.weight != null ? (i.weight + '%') : '' }}</em>
            </span>
            <span v-if="!indicators.length" class="ce-muted">尚未配置指标</span>
          </div>
          <div class="ce-indadd">
            <AppTextInput v-model="indForm.name" placeholder="指标名称" />
            <AppNumberInput v-model="indForm.weight" class="ce-input--sm" :min="0" placeholder="权重%" />
            <AppPermissionButton code="studentAffairs.counselorEval.manage" size="sm" :loading="acting==='ind'" @click="addIndicator">加指标</AppPermissionButton>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="录入 / 修改评分（发布前）">
        <div class="ce-scoreform">
          <label class="ce-field"><span>考评周期 *</span><AppTextInput v-model="scoreForm.periodCode" placeholder="如 2025-2026-1" /></label>
          <label class="ce-field"><span>辅导员标识 *</span><AppTextInput v-model="scoreForm.counselorKey" placeholder="工号/登录名" /></label>
          <label class="ce-field"><span>姓名</span><AppTextInput v-model="scoreForm.counselorName" /></label>
        </div>
        <div class="ce-scores">
          <label v-for="i in indicators" :key="i.indicatorId" class="ce-field">
            <span>{{ i.name }}（满分{{ i.maxScore || 100 }}）</span>
            <AppNumberInput v-model="scoreForm.scores[i.indicatorId]" :min="0" />
          </label>
        </div>
        <div class="ce-actions">
          <span class="ce-total">合计：<b>{{ liveTotal }}</b></span>
          <AppPermissionButton code="studentAffairs.counselorEval.manage" :loading="acting==='save'" :disabled="!indicators.length" @click="saveScore">保存评分</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="考评记录（按总分排名）">
        <table class="sa-table">
          <thead><tr><th>#</th><th>周期</th><th>辅导员</th><th>总分</th><th>加权总分</th><th>状态</th><th>申诉</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(e, idx) in evals" :key="e.evalId">
              <td>{{ idx + 1 }}</td>
              <td>{{ e.periodCode }}</td>
              <td><strong>{{ e.counselorName || e.counselorKey }}</strong></td>
              <td>{{ e.totalScore != null ? e.totalScore : '—' }}</td>
              <td>
                <b v-if="e.weightedTotalScore != null" title="按指标权重加权平均 Σ得分×权重/Σ权重">{{ e.weightedTotalScore }}</b>
                <span v-else class="ce-muted" title="指标未配权重，回退原始总分">—</span>
              </td>
              <td><StatusTag :type="e.status === 'PUBLISHED' ? 'success' : 'default'" :label="e.statusLabel || e.status" dot /></td>
              <td>
                <StatusTag v-if="e.appealStatus !== 'NONE'" :type="e.appealStatus === 'SUBMITTED' ? 'warning' : 'processing'" :label="e.appealStatusLabel" dot />
                <span v-else class="ce-muted">—</span>
              </td>
              <td class="ce-ops">
                <AppPermissionButton v-if="e.status === 'DRAFT'" code="studentAffairs.counselorEval.manage" size="sm" :loading="acting===e.evalId" @click="publish(e)">发布</AppPermissionButton>
                <AppPermissionButton v-if="e.appealStatus === 'SUBMITTED'" code="studentAffairs.counselorEval.manage" size="sm" variant="secondary" :loading="acting===e.evalId" @click="reviewAppeal(e)">申诉复核</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!evals.length"><td colspan="7" class="sa-empty">暂无考评记录</td></tr>
          </tbody>
        </table>
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
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

/** 复核结论枚举：原为 window.prompt 让用户手打 UPHELD/ADJUSTED，打错即失败 */
const APPEAL_RESULTS = [
  { value: 'UPHELD', label: '维持原考评结果' },
  { value: 'ADJUSTED', label: '调整考评结果' }
]

export default {
  name: 'CounselorEvalView',
  components: { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag,
    AppConfirmDialog, AppFormItem, AppNumberInput, AppSelect, AppTextInput },
  data() {
    return {
      APPEAL_RESULTS,
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
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [ind, ev] = await Promise.all([
        studentAffairsApi.getEvalIndicators(),
        studentAffairsApi.getCounselorEvals({ pageSize: 300 })
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
      const res = await studentAffairsApi.publishCounselorEval(e.evalId)
      this.acting = ''
      if (res.code === 0) { toast.success('已发布'); this.load() } else toast.error(res.message || '发布失败')
    },
    /** 复核申诉：结论走下拉（原让用户手打 UPHELD/ADJUSTED），意见走弹窗必填区（≥5字由组件校验） */
    reviewAppeal(e) {
      this.appealDlg = { visible: true, evalId: e.evalId, result: 'UPHELD', submitting: false }
    },
    async submitAppealReview({ reason }) {
      const d = this.appealDlg
      d.submitting = true
      this.acting = d.evalId
      const res = await studentAffairsApi.reviewEvalAppeal(d.evalId, { result: d.result, opinion: reason })
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
.ce-indbar { display: flex; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; align-items: center; }
.ce-inds { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.ce-indtag { border: 1px solid var(--border-light); border-radius: var(--radius-full); padding: 4px 12px; font-size: var(--font-size-sm); }
.ce-indtag em { color: var(--text-tertiary); font-style: normal; margin-left: 4px; }
.ce-indadd { display: flex; gap: var(--space-2); align-items: center; }
.ce-indadd > * { flex: 1 1 140px; min-width: 120px; }
.ce-indadd > .app-perm-btn { flex: 0 0 auto; min-width: 0; }
.ce-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.ce-input--sm { flex: 0 0 110px; min-width: 90px; width: 90px; }
.ce-scoreform, .ce-scores { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.ce-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.ce-actions { display: flex; justify-content: flex-end; align-items: center; gap: var(--space-4); }
.ce-total { color: var(--text-secondary); }
.ce-total b { font-size: var(--font-size-lg); color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ce-muted { color: var(--text-tertiary); }
.ce-ops { display: flex; gap: 6px; }
@media (max-width: 960px) { .ce-scoreform, .ce-scores { grid-template-columns: 1fr; } }
</style>
