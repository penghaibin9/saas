<template>
  <ModulePageShell
    title="毕业预审结果"
    subtitle="七项供数三态 + 学院初审 → 教务终审（终审写学籍终态，强制二次确认）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/graduation')">返回批次</button>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="rosters" title="三名单">
        <div class="aa-roster-row">
          <span class="aa-roster-chip is-grad">毕业 {{ (rosters.graduated || []).length }}</span>
          <span class="aa-roster-chip is-comp">结业 {{ (rosters.completed || []).length }}</span>
          <span class="aa-roster-chip is-delay">延毕 {{ (rosters.delayed || []).length }}</span>
        </div>
      </AppSectionCard>

      <div class="aa-filter">
        <AppSelect v-model="filters.overall" :options="overallOptions" placeholder="" @change="search" />
        <button class="mp-btn" @click="search">查询</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无预审结果" description="到批次页执行「圈定应届生 + 七项预审」后再来复核" />
      <div v-else class="aa-result-list">
        <AppSectionCard v-for="r in rows" :key="r.resultId" :title="r.realName || ('学生 ' + r.studentId)">
          <template #actions>
            <AppStatusTag :type="overallColor(r.overall)">{{ overallLabel(r.overall) }}</AppStatusTag>
            <AppStatusTag :type="r.conclusion ? 'success' : 'default'" dot>{{ statusLabel(r.status) }}</AppStatusTag>
          </template>
          <div class="aa-items">
            <div v-for="it in r.items" :key="it.item" class="aa-item">
              <span class="aa-item__label">{{ itemLabel(it.item) }}</span>
              <AppStatusTag :type="gradItemColor(it.result)">{{ itemResult(it.result) }}</AppStatusTag>
              <span v-if="it.evidence" class="aa-item__ev">{{ it.evidence }}</span>
            </div>
          </div>
          <div class="aa-result-actions">
            <template v-if="canCollegeReview(r)">
              <button class="mp-btn mp-btn--primary" :disabled="busy" @click="collegeReview(r, 'APPROVE')">学院初审通过</button>
              <button class="mp-btn" :disabled="busy" @click="collegeReview(r, 'REJECT')">学院驳回</button>
            </template>
            <button v-if="r.status === 'ACADEMIC_REVIEW'" class="mp-btn mp-btn--primary" @click="openFinal(r)">教务终审</button>
            <span v-if="r.conclusion" class="aa-final-tag">终审结论：{{ conclusionLabel(r.conclusion) }}</span>
          </div>
        </AppSectionCard>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="finalDlg.visible"
      title="教务终审"
      type="danger"
      confirm-text="确认终审并写学籍"
      :submitting="finalDlg.submitting"
      @confirm="doFinal"
    >
      <div class="aa-final-form">
        <p>终审结论涉及学籍终态，请谨慎选择：</p>
        <label v-for="(l, v) in CONCLUSION_LABEL" :key="v" class="aa-radio">
          <input v-model="finalDlg.conclusion" type="radio" :value="v" /> {{ l }}
        </label>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 毕业预审结果 + 复核（/admin/academic-affairs/graduation/:batchId/results）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { GRAD_ITEM_LABEL, GRAD_ITEM_RESULT, gradItemColor, OVERALL_LABEL, overallColor, CONCLUSION_LABEL, GRAD_STATUS_LABEL } from '@/modules/academicAffairs/constants/grade-graduation'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGraduationResultView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      CONCLUSION_LABEL,
      loading: true, error: '', rows: [], rosters: null, busy: false,
      filters: { overall: '' },
      pagination: { page: 1, pageSize: 50, total: 0 },
      finalDlg: { visible: false, submitting: false, resultId: '', conclusion: 'GRADUATED' }
    }
  },
  computed: {
    batchId() { return this.$route.params.batchId },
    overallOptions() {
      return [
        { value: '', label: '全部预审结果' },
        { value: 'SYSTEM_PASSED', label: '系统通过' },
        { value: 'SYSTEM_ABNORMAL', label: '系统异常' }
      ]
    }
  },
  created() { this.load(); this.loadRosters() },
  methods: {
    gradItemColor, overallColor,
    itemLabel(i) { return GRAD_ITEM_LABEL[i] || i },
    itemResult(r) { return GRAD_ITEM_RESULT[r] || r },
    overallLabel(o) { return OVERALL_LABEL[o] || o || '' },
    statusLabel(s) { return GRAD_STATUS_LABEL[s] || s || '' },
    conclusionLabel(c) { return CONCLUSION_LABEL[c] || c },
    canCollegeReview(r) { return ['SYSTEM_PASSED', 'SYSTEM_ABNORMAL', 'COLLEGE_REVIEW'].includes(r.status) },
    search() { this.pagination.page = 1; this.load() },
    async loadRosters() {
      const res = await academicAffairsApi.getGradRosters(this.batchId)
      if (res.code === 0) this.rosters = res.data
    },
    async collegeReview(r, action) {
      if (this.busy) return
      this.busy = true
      const res = await academicAffairsApi.collegeReviewGrad(r.resultId, action, action === 'REJECT' ? '学院初审驳回' : '')
      this.busy = false
      if (res.code === 0) { toast.success('已处理'); this.load() }
      else toast.error(res.message || '处理失败')
    },
    openFinal(r) {
      this.finalDlg = { visible: true, submitting: false, resultId: r.resultId, conclusion: 'GRADUATED' }
    },
    async doFinal() {
      this.finalDlg.submitting = true
      const res = await academicAffairsApi.finalGrad(this.finalDlg.resultId, this.finalDlg.conclusion, true)
      this.finalDlg.submitting = false
      if (res.code === 0) { this.finalDlg.visible = false; toast.success('终审完成，已写学籍'); this.load(); this.loadRosters() }
      else toast.error(res.message || '终审失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getGradResults(this.batchId, { overall: this.filters.overall || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-roster-row { display: flex; gap: 12px; }
.aa-roster-chip { padding: 6px 14px; border-radius: 16px; font-size: 14px; font-weight: 500; }
.aa-roster-chip.is-grad { background: var(--success-50, #eafff3); color: var(--success-600, #16a34a); }
.aa-roster-chip.is-comp { background: var(--fill-100, #f2f3f5); color: var(--text-700, #4e5969); }
.aa-roster-chip.is-delay { background: var(--warning-50, #fffbeb); color: var(--warning-600, #d97706); }
.aa-filter { display: flex; gap: 12px; align-items: center; }
.aa-filter :deep(.app-select) { width: 220px; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-result-list { display: flex; flex-direction: column; gap: 12px; }
.aa-items { display: flex; flex-wrap: wrap; gap: 8px 20px; }
.aa-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.aa-item__label { color: var(--text-700, #4e5969); min-width: 64px; }
.aa-item__ev { color: var(--text-400, #8a9099); font-size: 12px; }
.aa-result-actions { margin-top: 14px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-final-tag { color: var(--success-600, #16a34a); font-size: 13px; }
.aa-final-form { display: flex; flex-direction: column; gap: 8px; }
.aa-radio { display: flex; align-items: center; gap: 8px; font-size: 14px; }
</style>
