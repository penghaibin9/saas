<template>
  <ModulePageShell
    title="成绩分析"
    subtitle="分数段分布 + 及格率 / 优秀率 / 平均分 + 按课程·按班级统计表（读侧聚合，数据来自已发布成绩）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/academic-affairs/grade-fail')">挂科清单</AppButton>
      <AppButton variant="ghost" @click="$router.push('/admin/academic-affairs/grade-entry')">成绩录入</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <span class="aa-filter__label">学期</span>
        <AppTextInput v-model="term" placeholder="学期码，如 2026-1（空=全部）" size="compact" style="max-width:210px" />
        <span class="aa-filter__label">分组维度</span>
        <AppSelect v-model="dimension" :options="dimensionOptions" style="min-width:130px" @change="load" />
        <AppButton variant="ghost" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="aa-metric-grid">
          <AppMetricCard title="总成绩记录" :value="data.total" unit="条" />
          <AppMetricCard title="及格率" :value="pct(data.passRate)" unit="%" />
          <AppMetricCard title="优秀率" :value="pct(data.excellentRate)" unit="%" />
          <AppMetricCard title="平均分" :value="data.avgScore || 0" />
          <AppMetricCard title="最高分" :value="data.maxScore || 0" />
          <AppMetricCard title="最低分" :value="data.minScore || 0" />
        </div>

        <AppSectionCard title="分数段分布">
          <EmptyState v-if="!data.total" title="暂无成绩数据" description="发布成绩录入任务后，这里出现分数段分布" />
          <div v-else class="aa-dist">
            <div v-for="d in data.distribution" :key="d.range" class="aa-dist__row">
              <span class="aa-dist__label">{{ d.range }}</span>
              <div class="aa-dist__bar-wrap"><div class="aa-dist__bar" :style="{ width: barWidth(d.count) }"></div></div>
              <span class="aa-dist__count">{{ d.count }}</span>
            </div>
          </div>
        </AppSectionCard>

        <AppSectionCard v-if="dimension" :title="dimension === 'course' ? '按课程成绩分析统计表' : '按班级成绩分析统计表'">
          <div class="aa-export">
            <AppTextInput v-model="exportPurpose" placeholder="导出用途（≥5 字，写审计）" size="compact" style="max-width:280px" />
            <AppButton variant="primary" :loading="downloading" @click="doExport">导出 Excel</AppButton>
          </div>
          <EmptyState v-if="!(data.rows && data.rows.length)" title="暂无分组数据" description="该学期下暂无已发布成绩" />
          <DataTable v-else :columns="columns" :rows="data.rows" row-key="name">
            <template #cell-passRate="{ row }">{{ pct(row.passRate) }}%</template>
            <template #cell-excellentRate="{ row }">{{ pct(row.excellentRate) }}%</template>
          </DataTable>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩分析（/admin/academic-affairs/grade-overview）：GET /grade-views/analysis（可按课程/班级分组）+ 导出 xlsx。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppSectionCard, AppSelect, AppTextInput } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGradeOverviewView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppButton, AppMetricCard, AppSectionCard, AppSelect, AppTextInput
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', term: '', dimension: '',
      data: { total: 0, passRate: 0, excellentRate: 0, avgScore: 0, maxScore: 0, minScore: 0, distribution: [], rows: [] },
      exportPurpose: '', downloading: false,
      dimensionOptions: [
        { label: '总体', value: '' }, { label: '按课程', value: 'course' }, { label: '按班级', value: 'class' }
      ]
    }
  },
  computed: {
    maxCount() { return Math.max(1, ...(this.data.distribution || []).map((d) => d.count)) },
    columns() {
      return [
        { key: 'name', title: this.dimension === 'course' ? '课程' : '班级' },
        { key: 'total', title: '记录数' }, { key: 'avgScore', title: '平均分' },
        { key: 'maxScore', title: '最高' }, { key: 'minScore', title: '最低' },
        { key: 'passRate', title: '及格率' }, { key: 'excellentRate', title: '优秀率' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    pct(v) { return Math.round((v || 0) * 100) },
    barWidth(count) { return Math.round((count / this.maxCount) * 100) + '%' },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getGradeAnalysis(this.term || undefined, this.dimension || undefined)
      if (res.code === 0) this.data = { rows: [], ...res.data }
      else this.error = res.message
      this.loading = false
    },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字')
        return
      }
      this.downloading = true
      const res = await academicAffairsApi.exportGradeAnalysis({
        term: this.term || undefined,
        dimension: this.dimension || 'course',
        purpose: this.exportPurpose.trim()
      })
      this.downloading = false
      if (res.code !== 0) {
        toast.error(res.message || '导出失败')
        return
      }
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = `成绩分析统计表-${Date.now()}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
      toast.success('导出成功')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-filter__label { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.aa-dist__row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.aa-dist__label { width: 72px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-dist__bar-wrap { flex: 1; height: 18px; background: var(--fill-100, #f2f3f5); border-radius: 4px; overflow: hidden; }
.aa-dist__bar { height: 100%; background: var(--primary-400, #60a5fa); border-radius: 4px; }
.aa-dist__count { width: 48px; text-align: right; font-size: 13px; color: var(--text-900, #1f2329); }
.aa-export { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
</style>
