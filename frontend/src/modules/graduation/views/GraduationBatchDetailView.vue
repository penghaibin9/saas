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
      <section class="gb-summary" aria-label="批次配置摘要">
        <div class="gb-summary__name">
          <span>毕业设计批次</span>
          <strong>{{ detail.batchName }}</strong>
          <small>{{ detail.batchNo }} · {{ detail.academicYear || detail.gradeYear || '未设置学年' }}</small>
        </div>
        <div class="gb-summary__item"><span>状态</span><StatusTag :type="detail.statusTone" :label="detail.statusLabel" dot /></div>
        <div class="gb-summary__item"><span>计划人数</span><b>{{ detail.plannedCount || 0 }} 人</b></div>
        <div class="gb-summary__item"><span>配置权限</span><b :class="{ 'is-locked': configLocked }">{{ configLocked ? '已锁定' : '可编辑' }}</b></div>
      </section>
      <div class="gb-tabs">
        <button v-for="t in detailTabs" :key="t.key" class="gb-tabs__item" :class="{ 'is-active': dtab === t.key }" @click="dtab = t.key">{{ t.label }}</button>
      </div>

      <div v-show="dtab === 'stages'" class="gb-sec">
        <p class="ie-hint">阶段时间轴（编辑后点「保存阶段」）。{{ configLocked ? '已结束/归档/作废批次不可改。' : '' }}</p>
        <table class="gb-tbl">
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

      <div v-show="dtab === 'rules'" class="gb-sec">
        <p class="ie-hint">规则配置（查重/答辩/成绩权重）。保存前会校验成绩权重合计为 100%。</p>
        <label class="gb-kv"><span>查重阈值(%)</span><input v-model.number="rules.plagiarism.thresholdPercent" type="number" min="0" max="100" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
        <label class="gb-kv"><span>查重通过才可答辩</span><input v-model="rules.plagiarism.mustPassToDefense" type="checkbox" :disabled="configLocked" /></label>
        <label class="gb-kv"><span>答辩组人数</span><input v-model.number="rules.defense.groupSize" type="number" min="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
        <label class="gb-kv"><span>答辩及格分</span><input v-model.number="rules.defense.passScore" type="number" min="0" max="100" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
        <label class="gb-kv"><span>导师权重</span><input v-model.number="rules.score.advisorWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
        <label class="gb-kv"><span>评阅权重</span><input v-model.number="rules.score.reviewerWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
        <label class="gb-kv"><span>答辩权重</span><input v-model.number="rules.score.defenseWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
        <div class="gb-rule-total" :class="{ 'is-valid': scoreWeightValid, 'is-invalid': !scoreWeightValid }">
          成绩权重合计 <b>{{ Math.round(scoreWeightTotal * 100) }}%</b>
          <span>{{ scoreWeightValid ? '可保存' : '请调整至 100%' }}</span>
        </div>
      </div>

      <div v-show="dtab === 'audit'" class="gb-sec">
        <AppAuditTrail :records="batchAuditRecords" compact :show-ip="false" />
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
.gb-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.gb-tabs__item { padding: 8px 12px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gb-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gb-sec { font-size: 13px; }
.gb-summary { display: grid; grid-template-columns: minmax(210px, 1.5fr) repeat(3, minmax(120px, 1fr)); align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-md, 8px); background: linear-gradient(100deg, var(--primary-50, #eff6ff), var(--card, #fff) 68%); }
.gb-summary__name { display: grid; gap: 2px; min-width: 0; }
.gb-summary__name span, .gb-summary__name small, .gb-summary__item > span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gb-summary__name strong { overflow: hidden; color: var(--text-primary); font-size: var(--font-size-md); text-overflow: ellipsis; white-space: nowrap; }
.gb-summary__item { display: grid; gap: 4px; }
.gb-summary__item b { color: var(--text-primary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); }
.gb-summary__item b.is-locked { color: var(--warning-700, #b45309); }
.gb-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.gb-tbl th, .gb-tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line, #eef1f6); }
.gb-tbl th { color: var(--t3, #64748b); font-weight: 500; font-size: 12px; }
.gb-kv { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 6px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.gb-kv > span { color: var(--t2, #475569); }
.gb-kv .ie-in--sm { width: 120px; flex: none; }
.gb-rule-total { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); margin-top: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--gray-50, #f8fafc); }
.gb-rule-total span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gb-rule-total.is-valid b { color: var(--success-700, #047857); }
.gb-rule-total.is-invalid b, .gb-rule-total.is-invalid span { color: var(--danger, #dc2626); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 760px) { .gb-summary { grid-template-columns: 1fr 1fr; } .gb-summary__name { grid-column: 1 / -1; } }
</style>
