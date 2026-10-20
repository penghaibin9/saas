<template>
  <AppPageShell
    title="困难认定统计"
    subtitle="按状态与核定等级聚合，仅统计口径，不含家庭经济明细。数据范围与认定台账一致。"
    :role-name="ctx?.currentRole?.roleName || ''"
    :data-scope-name="ctx?.dataScope?.scopeName || ''"
    watermark-purpose="困难认定统计"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载认定统计..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前认定结论</span>
          <h2 class="sa-summary-strip__title">申请 {{ stats.total || 0 }} 份，已生效 {{ stats.approved || 0 }} 份，在途或未通过 {{ (stats.total || 0) - (stats.approved || 0) }} 份</h2>
          <p class="sa-summary-strip__text">先看状态分布判断流程积压，再看核定等级结构。本页不返回家庭收入、负债、特殊标签等敏感明细。</p>
        </div>
      </section>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <div class="ss-cols">
        <AppSectionCard title="按状态分布">
          <p class="stats-hint">识别班级评议、辅导员初审、学院复审、学校终审和公示等阶段的积压。</p>
          <BreakdownTable :rows="stats.byStatus" :label-map="STATUS_LABELS" empty="当前范围暂无困难认定申请" />
        </AppSectionCard>
        <AppSectionCard title="按核定等级分布">
          <p class="stats-hint">按已生效申请统计等级，调整审核中的申请沿用原等级；同一学生多批次分别计数。</p>
          <BreakdownTable :rows="stats.byLevel" :label-map="LEVEL_LABELS" empty="当前范围暂无核定等级数据" />
        </AppSectionCard>
      </div>
      <p class="stats-note">本页按申请份数统计，与认定台账口径一致；去重后的当前人数请查看困难学生库。</p>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard } from '@/components/common'
import BreakdownTable from '@/modules/studentAffairs/views/common/BreakdownTable.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const STATUS_LABELS = { DRAFT: '草稿', SUBMITTED: '已提交', CLASS_REVIEW: '班级评议', COUNSELOR_REVIEW: '辅导员初审', COLLEGE_REVIEW: '学院复审', SCHOOL_REVIEW: '学校终审', PUBLICITY: '公示中', APPROVED: '已通过', REJECTED: '已驳回', ADJUST_REVIEW: '动态调整', ARCHIVED: '已归档' }
const LEVEL_LABELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }

export default {
  name: 'AidStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, BreakdownTable },
  props: { ctx: { type: Object, default: null } },
  data() { return { loadSeq: 0, loading: true, errorMessage: '', stats: { total: 0, approved: 0, byStatus: [], byLevel: [] }, STATUS_LABELS, LEVEL_LABELS } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = (this.stats.total || 0) - (this.stats.approved || 0)
      return [
        { key: 't', label: '申请总数', value: this.stats.total || 0, accent: 'primary' },
        { key: 'a', label: '已生效申请', value: this.stats.approved || 0, accent: 'success' },
        { key: 'p', label: '在途/未通过', value: pending, accent: pending ? 'warning' : 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      const seq = ++this.loadSeq
      this.loading = true; this.errorMessage = ''
      try {
      const res = await studentAffairsApi.getAidStats()
      if (seq !== this.loadSeq) return
      if (res.code === 0 && res.data) {
        this.stats = res.data
      } else {
        this.errorMessage = res.message || '认定统计加载失败'
      }
      } catch { if (seq === this.loadSeq) this.errorMessage = '认定统计暂未加载，请重试' }
      finally { if (seq === this.loadSeq) this.loading = false }
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.ss-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.stats-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.stats-note { margin: var(--space-4) 0 0; padding: 10px 12px; border-left: 3px solid var(--primary-300, #93c5fd); background: var(--primary-50, #eff6ff); color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.65; }
@media (max-width: 960px) { .sa-grid--metrics, .ss-cols { grid-template-columns: 1fr; } }
</style>
