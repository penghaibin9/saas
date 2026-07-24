<template>
  <AppPageShell
    title="困难学生库"
    subtitle="认定通过（APPROVED）的最新等级聚合，供助学金 / 绿色通道 / 临时补助前置校验引用。"
    role-name="学工处 / 资助老师"
    data-scope-name="按数据范围过滤（辅导员限本班）"
    watermark-purpose="困难学生库查看"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载困难学生库..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="困难学生名单">
        <div class="dl-filters">
          <button
            v-for="f in levelFilters"
            :key="f.key"
            type="button"
            class="dl-chip"
            :class="{ 'is-on': activeLevel === f.key }"
            @click="setLevel(f.key)"
          >{{ f.label }}</button>
        </div>
        <DataTable v-if="items.length" :columns="difficultColumns" :rows="items" row-key="studentId">
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</div>
          </template>
          <template #cell-level="{ row }">
            <StatusTag :type="levelType(row.level)" :label="row.levelLabel || row.level || '—'" dot />
          </template>
          <template #cell-identifiedAt="{ row }">
            <AppDateDisplay :value="row.identifiedAt" mode="date" empty-text="—" />
          </template>
          <template #cell-batchId="{ row }">
            <span class="dl-batch">{{ row.batchId || '—' }}</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前范围与筛选下暂无困难学生</p>
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                       :total="pagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const LEVELS = [
  { key: '', label: '全部' },
  { key: 'SPECIAL', label: '特别困难' },
  { key: 'DIFFICULT', label: '困难' },
  { key: 'GENERAL', label: '一般困难' }
]

const DIFFICULT_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'level', title: '困难等级' },
  { key: 'identifiedAt', title: '认定时间' },
  { key: 'batchId', title: '来源批次' }
]

export default {
  name: 'DifficultStudentsView',
  components: { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  data() {
    return {
      difficultColumns: DIFFICULT_COLUMNS,
      loading: true, errorMessage: '', items: [], total: 0, byLevel: {}, activeLevel: '', levelFilters: LEVELS,
      pagination: { page: 1, pageSize: 20, total: 0 }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'all', label: '困难学生总数', value: this.total, accent: 'primary' },
        { key: 'sp', label: '特别困难', value: this.byLevel.SPECIAL || 0, accent: 'risk' },
        { key: 'df', label: '困难', value: this.byLevel.DIFFICULT || 0, accent: 'warning' },
        { key: 'gn', label: '一般困难', value: this.byLevel.GENERAL || 0, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // 指标待服务端全量统计；名单按当前筛选 + 真实分页取。
      const [all, filtered] = await Promise.all([
        studentAffairsApi.getDifficultStudents({ pageSize: 200 }),
        studentAffairsApi.getDifficultStudents({ level: this.activeLevel, page: this.pagination.page, pageSize: this.pagination.pageSize })
      ])
      if (all.code === 0 && all.data) {
        const allItems = all.data.items || []
        this.total = all.data.total != null ? all.data.total : allItems.length
        this.byLevel = allItems.reduce((m, x) => { m[x.level] = (m[x.level] || 0) + 1; return m }, {})
      } else {
        this.errorMessage = all.message || '困难学生库加载失败'
      }
      if (filtered.code === 0 && filtered.data) {
        this.items = filtered.data.items || []
        this.pagination.total = filtered.data.total != null ? filtered.data.total : this.items.length
      } else if (!this.errorMessage) {
        this.errorMessage = filtered.message || '困难学生库加载失败'
      }
      this.loading = false
    },
    setLevel(k) {
      if (this.activeLevel === k) return
      this.activeLevel = k
      this.pagination.page = 1
      this.load()
    },
    levelType(l) { return ({ SPECIAL: 'danger', DIFFICULT: 'warning', GENERAL: 'info' })[l] || 'default' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.dl-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.dl-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.dl-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.dl-batch { color: var(--text-tertiary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@import '@/styles/module-page.css';
</style>
