<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="detail ? detail.batchName : '批次详情'"
    subtitle="阶段时间轴 / 规则配置 / 审计"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__body summary-grid">
            <div class="summary-name">
              <span>毕业设计批次</span>
              <strong>{{ detail.batchName }}</strong>
              <small>{{ detail.batchNo }} · {{ detail.academicYear || detail.gradeYear || '未设置学年' }}</small>
            </div>
            <div class="summary-item"><span>状态</span><StatusTag :type="detail.statusTone" :label="detail.statusLabel" dot /></div>
            <div class="summary-item"><span>计划人数</span><b>{{ detail.plannedCount || 0 }} 人</b></div>
            <div class="summary-item"><span>配置权限</span><b :class="{ 'is-locked': configLocked }">{{ configLocked ? '已锁定' : '可编辑' }}</b></div>
          </div>
        </section>

        <div class="mp-tabs">
          <button v-for="t in detailTabs" :key="t.key" class="mp-tab" :class="{ 'is-active': dtab === t.key }" @click="dtab = t.key">{{ t.label }}</button>
        </div>

        <section v-show="dtab === 'stages'" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">阶段时间轴</span></header>
          <div class="mp-card__body">
            <p class="ie-hint">阶段时间轴（编辑后点「保存阶段」）。{{ configLocked ? '已结束/归档/作废批次不可改。' : '' }}</p>
            <table class="gd-tbl">
              <thead><tr><th>阶段</th><th>开始</th><th>结束</th></tr></thead>
              <tbody>
                <tr v-for="(s, i) in stages" :key="i">
                  <td>{{ s.name }}</td>
                  <td><AppDatePicker v-model="s.startDate" role="start" :end-value="s.endDate" :disabled="configLocked" /></td>
                  <td><AppDatePicker v-model="s.endDate" role="end" :start-value="s.startDate" :disabled="configLocked" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-show="dtab === 'rules'" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">规则配置</span></header>
          <div class="mp-card__body">
            <p class="ie-hint">规则配置（查重/答辩/成绩权重）。保存前会校验成绩权重合计为 100%。</p>
            <label class="mp-kv"><span class="mp-kv__k">查重阈值(%)</span><input v-model.number="rules.plagiarism.thresholdPercent" type="number" min="0" max="100" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
            <label class="mp-kv"><span class="mp-kv__k">查重通过才可答辩</span><input v-model="rules.plagiarism.mustPassToDefense" type="checkbox" :disabled="configLocked" /></label>
            <label class="mp-kv"><span class="mp-kv__k">答辩组人数</span><input v-model.number="rules.defense.groupSize" type="number" min="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
            <label class="mp-kv"><span class="mp-kv__k">答辩及格分</span><input v-model.number="rules.defense.passScore" type="number" min="0" max="100" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
            <label class="mp-kv"><span class="mp-kv__k">导师权重</span><input v-model.number="rules.score.advisorWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
            <label class="mp-kv"><span class="mp-kv__k">评阅权重</span><input v-model.number="rules.score.reviewerWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
            <label class="mp-kv"><span class="mp-kv__k">答辩权重</span><input v-model.number="rules.score.defenseWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
            <div class="rule-total" :class="{ 'is-valid': scoreWeightValid, 'is-invalid': !scoreWeightValid }">
              成绩权重合计 <b>{{ Math.round(scoreWeightTotal * 100) }}%</b>
              <span>{{ scoreWeightValid ? '可保存' : '请调整至 100%' }}</span>
            </div>
          </div>
        </section>

        <section v-show="dtab === 'audit'" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">操作审计</span></header>
          <div class="mp-card__body">
            <AppAuditTrail :records="batchAuditRecords" compact :show-ip="false" />
          </div>
        </section>
      </div>
    </template>
    <template v-if="detail && dtab !== 'audit'" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">返回</button>
      <button v-if="dtab === 'stages'" type="button" class="mp-btn mp-btn--primary" :disabled="configLocked || submitting" @click="saveStages">保存阶段</button>
      <button v-if="dtab === 'rules'" type="button" class="mp-btn mp-btn--primary" :disabled="configLocked || submitting" @click="saveRules">保存规则</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, StatusTag } from '@/components/business'
import { AppAuditTrail } from '@/components/common'
import { AppDatePicker } from '@/components/common/date'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'
import { toast } from '@/utils/toast'

const DEFAULT_RULES = () => ({
  plagiarism: { thresholdPercent: 30, mustPassToDefense: true },
  defense: { groupSize: 5, passScore: 60 },
  score: { advisorWeight: 0.4, reviewerWeight: 0.3, defenseWeight: 0.3 }
})

export default {
  name: 'GraduationBatchDetailView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, StatusTag, AppDatePicker, AppAuditTrail },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      detail: null, dtab: 'stages', stages: [], rules: DEFAULT_RULES(),
      detailTabs: [
        { key: 'stages', label: '阶段时间轴' },
        { key: 'rules', label: '规则配置' },
        { key: 'audit', label: '审计' }
      ]
    }
  },
  computed: {
    backTo() { return '/admin/graduation/batches' },
    batchAuditRecords() {
      return (this.detail?.auditTrail || []).map((a, i) => ({
        id: i, action: a.action, actor: a.operator, at: a.occurredAt
      }))
    },
    configLocked() {
      return this.detail && ['ARCHIVED', 'VOIDED', 'CLOSED'].includes(this.detail.status)
    },
    scoreWeightTotal() {
      const s = this.rules.score || {}
      return Number(s.advisorWeight || 0) + Number(s.reviewerWeight || 0) + Number(s.defenseWeight || 0)
    },
    scoreWeightValid() {
      return Math.abs(this.scoreWeightTotal - 1) < 0.0001
    }
  },
  created() {
    const tab = this.$route.query.tab
    if (['stages', 'rules', 'audit'].includes(tab)) this.dtab = tab
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationBatchApi.getBatchDetail(this.$route.params.id)
      if (res.code !== 0) { this.error = res.message; this.loading = false; return }
      this.detail = res.data
      this.stages = JSON.parse(JSON.stringify(res.data.stages || []))
      this.rules = {
        ...DEFAULT_RULES(), ...(res.data.rules || {}),
        plagiarism: { ...DEFAULT_RULES().plagiarism, ...(res.data.rules?.plagiarism || {}) },
        defense: { ...DEFAULT_RULES().defense, ...(res.data.rules?.defense || {}) },
        score: { ...DEFAULT_RULES().score, ...(res.data.rules?.score || {}) }
      }
      this.loading = false
    },
    async saveStages() {
      this.submitting = true
      try {
        const res = await graduationBatchApi.setStages(this.detail.id, this.stages)
        if (res.code === 0) { toast.success('阶段已保存'); this.detail = res.data } else toast.error(res.message)
      } finally { this.submitting = false }
    },
    async saveRules() {
      if (!this.scoreWeightValid) {
        toast.error('导师、评阅和答辩权重合计必须为 100%')
        return
      }
      this.submitting = true
      try {
        const res = await graduationBatchApi.setRules(this.detail.id, this.rules)
        if (res.code === 0) { toast.success('规则已保存'); this.detail = res.data } else toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.summary-grid { display: grid; grid-template-columns: minmax(210px, 1.5fr) repeat(3, minmax(120px, 1fr)); align-items: center; gap: var(--space-3); }
.summary-name { display: grid; gap: 2px; min-width: 0; }
.summary-name span, .summary-name small, .summary-item > span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.summary-name strong { overflow: hidden; color: var(--text-primary); font-size: var(--font-size-md); text-overflow: ellipsis; white-space: nowrap; }
.summary-item { display: grid; gap: 4px; }
.summary-item b { color: var(--text-primary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); }
.summary-item b.is-locked { color: var(--warning-700, #b45309); }
.gd-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.gd-tbl th, .gd-tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--dv, #eef1f6); }
.gd-tbl th { color: var(--text-tertiary, #64748b); font-weight: 500; font-size: 12px; }
.ie-in--sm { width: 120px; flex: none; }
.rule-total { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); margin-top: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--gray-50, #f8fafc); }
.rule-total span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.rule-total.is-valid b { color: var(--success-700, #047857); }
.rule-total.is-invalid b, .rule-total.is-invalid span { color: var(--danger, #dc2626); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
