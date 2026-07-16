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
            <input v-model.trim="indForm.name" class="ce-input" placeholder="指标名称" />
            <input v-model.number="indForm.weight" type="number" class="ce-input ce-input--sm" placeholder="权重%" />
            <AppPermissionButton code="studentAffairs.counselorEval.manage" size="sm" :loading="acting==='ind'" @click="addIndicator">加指标</AppPermissionButton>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="录入 / 修改评分（发布前）">
        <div class="ce-scoreform">
          <label class="ce-field"><span>考评周期 *</span><input v-model.trim="scoreForm.periodCode" class="ce-input" placeholder="如 2025-2026-1" /></label>
          <label class="ce-field"><span>辅导员标识 *</span><input v-model.trim="scoreForm.counselorKey" class="ce-input" placeholder="工号/登录名" /></label>
          <label class="ce-field"><span>姓名</span><input v-model.trim="scoreForm.counselorName" class="ce-input" /></label>
        </div>
        <div class="ce-scores">
          <label v-for="i in indicators" :key="i.indicatorId" class="ce-field">
            <span>{{ i.name }}（满分{{ i.maxScore || 100 }}）</span>
            <input v-model.number="scoreForm.scores[i.indicatorId]" type="number" min="0" class="ce-input" />
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
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                       :total="pagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 申诉复核 -->
    <AppDrawer v-model:visible="appealDrawer.visible" title="申诉复核">
      <div class="sa-form">
        <AppFormItem label="复核结论" required>
          <AppSelect v-model="appealDrawer.form.result" :options="appealResultOptions" />
        </AppFormItem>
        <AppFormItem label="复核意见" required :error="appealDrawer.errors.opinion">
          <AppQuickPhrases scene-key="common.reviewOpinion" @pick="onPickOpinion" />
          <AppTextarea ref="opinionTa" v-model="appealDrawer.form.opinion" placeholder="复核意见（至少5字）" :rows="4" :disabled="!!acting" />
        </AppFormItem>
        <AppInlineAlert v-if="appealDrawer.errorMessage" type="danger" :description="appealDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="ce-btn" :disabled="!!acting" @click="appealDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.counselorEval.manage" :loading="!!acting" @click="submitAppealReview">提交复核</AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPagination, AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppTextarea } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { applyInsertion, insertAtCursor } from '@/utils/insertAtCursor'

const APPEAL_RESULT_OPTIONS = [
  { label: '维持（UPHELD）', value: 'UPHELD' },
  { label: '调整（ADJUSTED）', value: 'ADJUSTED' }
]

export default {
  name: 'CounselorEvalView',
  components: { AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPagination, AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect, StatusTag: AppStatusTag, AppTextarea },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', indicators: [], evals: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      indForm: { name: '', weight: null },
      scoreForm: { periodCode: '', counselorKey: '', counselorName: '', scores: {} },
      appealResultOptions: APPEAL_RESULT_OPTIONS,
      appealDrawer: { visible: false, evalId: '', form: { result: 'UPHELD', opinion: '' }, errors: {}, errorMessage: '' }
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
        studentAffairsApi.getCounselorEvals({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      ])
      if (ind.code === 0 && ind.data) this.indicators = ind.data.items || []
      else this.errorMessage = ind.message || '加载失败'
      if (ev.code === 0 && ev.data) {
        this.evals = ev.data.items || []
        this.pagination.total = ev.data.total != null ? ev.data.total : this.evals.length
      } else {
        this.evals = []
        if (!this.errorMessage) this.errorMessage = ev.message || '考评记录加载失败'
      }
      this.loading = false
    },
    async addIndicator() {
      if (!this.indForm.name) { toast.error('请输入指标名称'); return }
      this.acting = 'ind'
      const res = await studentAffairsApi.createEvalIndicator({ name: this.indForm.name, weight: this.indForm.weight != null ? Number(this.indForm.weight) : undefined })
      this.acting = ''
      if (res.code === 0) { toast.success('已加指标'); this.indForm = { name: '', weight: null }; this.load() } else toast.error(res.message || '创建失败')
    },
    async saveScore() {
      const f = this.scoreForm
      if (!f.periodCode || !f.counselorKey) { toast.error('周期与辅导员标识必填'); return }
      const scores = {}
      Object.keys(f.scores).forEach((k) => { if (f.scores[k] != null && f.scores[k] !== '') scores[k] = Number(f.scores[k]) })
      this.acting = 'save'
      const res = await studentAffairsApi.upsertCounselorEval({ periodCode: f.periodCode, counselorKey: f.counselorKey, counselorName: f.counselorName || undefined, scores })
      this.acting = ''
      if (res.code === 0) { toast.success('评分已保存'); this.load() } else toast.error(res.message || '保存失败')
    },
    async publish(e) {
      this.acting = e.evalId
      const res = await studentAffairsApi.publishCounselorEval(e.evalId)
      this.acting = ''
      if (res.code === 0) { toast.success('已发布'); this.load() } else toast.error(res.message || '发布失败')
    },
    reviewAppeal(e) {
      this.appealDrawer = { visible: true, evalId: e.evalId, form: { result: 'UPHELD', opinion: '' }, errors: {}, errorMessage: '' }
    },
    onPickOpinion(text) {
      const el = this.$refs.opinionTa?.$refs?.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.appealDrawer.form.opinion, text)
      this.appealDrawer.form.opinion = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async submitAppealReview() {
      const { form, evalId } = this.appealDrawer
      const opinion = (form.opinion || '').trim()
      if (opinion.length < 5) { this.appealDrawer.errors.opinion = '复核意见不能少于5个字'; return }
      this.appealDrawer.errors.opinion = ''
      this.acting = evalId
      const res = await studentAffairsApi.reviewEvalAppeal(evalId, { result: form.result, opinion })
      this.acting = ''
      if (res.code === 0) { toast.success('已复核'); this.appealDrawer.visible = false; this.load() } else this.appealDrawer.errorMessage = res.message || '复核失败'
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
.ce-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.ce-input--sm { width: 90px; }
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
.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.ce-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.ce-btn:hover { border-color: var(--border-dark); }
.ce-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) { .ce-scoreform, .ce-scores { grid-template-columns: 1fr; } }
</style>
