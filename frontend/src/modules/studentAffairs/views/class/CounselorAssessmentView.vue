<template>
  <ModulePageShell title="辅导员考评" subtitle="系统留痕自动生成工作量 · 学院评分 · 综合排名（自动*0.6+学院*0.4）"
    :role-name="roleName" :data-scope-name="scopeHint">
    <template #actions>
      <AppButton variant="secondary" size="sm" @click="openPeriodForm">＋ 新建考评周期</AppButton>
    </template>

    <div class="mp-stack">
      <div class="bar">
        <label class="bar-lbl">考评周期</label>
        <AppSelect v-model="periodId" :options="periodOptions" placeholder="选择考评周期" @change="onPeriodChange" />
        <template v-if="curPeriod">
          <AppStatusTag :status="curPeriod.status" :label="curPeriod.statusLabel" />
          <AppButton variant="ghost" size="sm" :loading="collecting" :disabled="curPeriod.status === 'PUBLISHED'" @click="collect">生成/刷新指标</AppButton>
          <AppButton variant="ghost" size="sm" :disabled="curPeriod.status === 'PUBLISHED'" @click="publish">发布考评</AppButton>
        </template>
      </div>

      <EmptyState v-if="!periodId" title="请选择或新建考评周期" description="新建周期后点「生成/刷新指标」自动抓取各辅导员工作量" />
      <template v-else>
        <LoadingState v-if="loading" />
        <EmptyState v-else-if="!rows.length" title="该周期暂无考评记录" description="点「生成/刷新指标」按数据范围内班级的辅导员自动生成" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="id">
          <template #cell-rankNo="{ row }"><b>{{ row.rankNo || '—' }}</b></template>
          <template #cell-counselor="{ row }">
            <div class="mp-cell-main">{{ row.counselorName || ('辅导员#' + row.counselorId) }}</div>
            <div class="mp-cell-sub">带班 {{ row.classCount }} · 学生 {{ row.studentCount }} · 办结请假 {{ metric(row, 'closedLeave') }} · 风险处置 {{ metric(row, 'riskClosed') }} · 材料 {{ metric(row, 'materialCount') }}</div>
          </template>
          <template #cell-autoScore="{ row }">{{ fmtScore(row.autoScore) }}</template>
          <template #cell-collegeScore="{ row }">{{ fmtScore(row.collegeScore) }}</template>
          <template #cell-totalScore="{ row }"><b>{{ fmtScore(row.totalScore) }}</b></template>
          <template #cell-status="{ row }"><AppStatusTag :status="row.status" :label="row.statusLabel" dot /></template>
          <template #cell-actions="{ row }">
            <AppPermissionButton code="studentAffairs.class.create" variant="secondary" size="sm" :disabled="isPublished" @click="openScore(row)">学院评分</AppPermissionButton>
          </template>
        </DataTable>
        <p class="mp-note">系统自动分=工作量折算（透明可解释：带班×5 + 办结请假×2 + 风险处置×3 + 材料×1，基线60封顶100）；综合分=自动×0.6+学院×0.4。申诉/正式归档流程见历史欠账（本轮为一步发布）。</p>
      </template>
    </div>

    <!-- 新建周期 / 评分 弹窗 -->
    <div v-if="fm.visible" class="fm-mask" @click.self="closeForm">
      <div class="fm-dialog">
        <div class="fm-title">{{ fm.title }}</div>
        <div class="fm-body">
          <template v-if="fm.kind === 'period'">
            <div class="fm-item"><label class="fm-label">周期名称<i>*</i></label>
              <AppTextInput v-model="fm.values.periodName" placeholder="如：2025-2026学年上 辅导员考评" :maxlength="100" /></div>
            <div class="fm-item"><label class="fm-label">学期</label>
              <AppTextInput v-model="fm.values.semester" placeholder="如：2025-1" :maxlength="50" /></div>
          </template>
          <template v-else>
            <div class="fm-item"><label class="fm-label">被考评辅导员</label>
              <div class="mp-cell-main">{{ fm.row.counselorName || ('辅导员#' + fm.row.counselorId) }}（自动分 {{ fmtScore(fm.row.autoScore) }}）</div></div>
            <div class="fm-item"><label class="fm-label">学院评分（0-100）<i>*</i></label>
              <AppNumberInput v-model="fm.values.collegeScore" :min="0" :max="100" placeholder="0-100" /></div>
          </template>
          <p v-if="fm.err" class="fm-err">{{ fm.err }}</p>
        </div>
        <div class="fm-foot">
          <AppButton variant="ghost" @click="closeForm">取消</AppButton>
          <AppButton variant="primary" :loading="fm.submitting" @click="submitForm">确定</AppButton>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 辅导员考评（/admin/campus-service/counselor-assessment）。
 * 建周期 → 系统自动抓取工作量指标 → 学院评分 → 综合排名 → 发布。真实对接 /student-affairs/counselor-assessment/*。
 */
import { ModulePageShell, DataTable, LoadingState, EmptyState } from '@/components/business'
import { AppStatusTag, AppSelect, AppTextInput, AppNumberInput, AppPermissionButton } from '@/components/common'
import { AppButton } from '@/components/ui'
import { assessmentApi } from '@/modules/studentAffairs/api/class.api'
import { toast } from '@/utils/toast'

const COLUMNS = [
  { key: 'rankNo', title: '排名' }, { key: 'counselor', title: '辅导员 / 工作量' },
  { key: 'autoScore', title: '自动分' }, { key: 'collegeScore', title: '学院分' },
  { key: 'totalScore', title: '综合分' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }
]

export default {
  name: 'CounselorAssessmentView',
  components: { ModulePageShell, DataTable, LoadingState, EmptyState, AppStatusTag, AppSelect, AppTextInput, AppNumberInput, AppPermissionButton, AppButton },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      periods: [], periodId: '', loading: false, collecting: false, rows: [], columns: COLUMNS,
      fm: { visible: false, kind: '', title: '', submitting: false, err: '', values: {}, row: {} }
    }
  },
  computed: {
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '学工处 / 学院学工' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.name) || '按数据范围裁剪' },
    periodOptions() { return this.periods.map((p) => ({ label: `${p.periodName}（${p.statusLabel}）`, value: p.id })) },
    curPeriod() { return this.periods.find((p) => String(p.id) === String(this.periodId)) || null },
    isPublished() { return !!(this.curPeriod && this.curPeriod.status === 'PUBLISHED') }
  },
  created() { this.loadPeriods() },
  methods: {
    fmtScore(v) { return v === null || v === undefined ? '—' : v },
    metric(row, key) { return (row.metrics && row.metrics[key]) || 0 },
    async loadPeriods() {
      const res = await assessmentApi.periods({ pageSize: 100 })
      if (res.code !== 0) return toast.error(res.message || '周期加载失败')
      this.periods = res.data.list
      if (!this.periodId && this.periods.length) { this.periodId = this.periods[0].id; this.loadAssessments() }
    },
    onPeriodChange() { this.loadAssessments() },
    async loadAssessments() {
      if (!this.periodId) return
      this.loading = true
      const res = await assessmentApi.assessments(this.periodId)
      this.loading = false
      if (res.code !== 0) { toast.error(res.message || '考评加载失败'); this.rows = []; return }
      this.rows = (res.data && res.data.items) || []
    },
    async collect() {
      this.collecting = true
      const res = await assessmentApi.collect(this.periodId)
      this.collecting = false
      if (res.code !== 0) return toast.error(res.message || '生成失败')
      toast.success(`已生成 ${res.data.counselors} 位辅导员考评`)
      await this.loadPeriods(); this.loadAssessments()
    },
    async publish() {
      const res = await assessmentApi.publish(this.periodId)
      if (res.code !== 0) return toast.error(res.message || '发布失败')
      toast.success('考评已发布')
      this.loadPeriods()
    },
    openPeriodForm() {
      this.fm = { visible: true, kind: 'period', title: '新建考评周期', submitting: false, err: '', values: { periodName: '', semester: '' }, row: {} }
    },
    openScore(row) {
      if (this.isPublished) return
      this.fm = { visible: true, kind: 'score', title: '学院评分', submitting: false, err: '', values: { collegeScore: '' }, row }
    },
    closeForm() { this.fm.visible = false },
    async submitForm() {
      this.fm.err = ''
      if (this.fm.kind === 'period') {
        if (!this.fm.values.periodName || !this.fm.values.periodName.trim()) { this.fm.err = '请填写周期名称'; return }
        this.fm.submitting = true
        const res = await assessmentApi.createPeriod({ periodName: this.fm.values.periodName.trim(), semester: this.fm.values.semester || null })
        this.fm.submitting = false
        if (res.code !== 0) { this.fm.err = res.message || '创建失败'; return }
        this.fm.visible = false; toast.success('已创建周期')
        this.periodId = res.data.id
        await this.loadPeriods(); this.loadAssessments()
      } else {
        const sc = Number(this.fm.values.collegeScore)
        if (this.fm.values.collegeScore === '' || Number.isNaN(sc) || sc < 0 || sc > 100) { this.fm.err = '请填写 0-100 的学院评分'; return }
        this.fm.submitting = true
        const res = await assessmentApi.score(this.fm.row.id, { collegeScore: sc })
        this.fm.submitting = false
        if (res.code !== 0) { this.fm.err = res.message || '评分失败'; return }
        this.fm.visible = false; toast.success('已评分')
        this.loadAssessments()
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.bar-lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.is-disabled { opacity: 0.5; cursor: not-allowed; }
.fm-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.fm-dialog { width: 420px; max-width: calc(100vw - 32px); background: var(--bg-card, #fff); border-radius: 12px; box-shadow: var(--shadow-lg, 0 12px 40px rgba(0,0,0,0.18)); overflow: hidden; }
.fm-title { padding: 14px 18px; font-weight: 600; font-size: 15px; border-bottom: 1px solid var(--border-light); }
.fm-body { padding: 16px 18px; display: flex; flex-direction: column; gap: var(--space-3); }
.fm-item { display: flex; flex-direction: column; gap: 6px; }
.fm-label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.fm-label i { color: var(--danger-600); font-style: normal; margin-left: 2px; }
.fm-err { color: var(--danger-600); font-size: var(--font-size-sm); margin: 0; }
.fm-foot { padding: 12px 18px; display: flex; justify-content: flex-end; gap: var(--space-2); border-top: 1px solid var(--border-light); }
</style>
