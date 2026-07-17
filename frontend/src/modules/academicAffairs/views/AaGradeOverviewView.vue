<template>
  <ModulePageShell
    title="成绩分析"
    subtitle="分数段分布 + 及格率 / 优秀率 / 平均分 + 按课程·按班级统计表（读侧聚合，数据来自已发布成绩）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/grade-fail')">挂科清单</button>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/grade-entry')">成绩录入</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">学期<input v-model.trim="term" class="aa-input aa-input--sm" placeholder="学期码，如 2026-1（空=全部）" @keyup.enter="load" /></label>
        <label class="aa-filter__item">分组维度
          <select v-model="dimension" class="aa-input aa-input--sm" @change="load">
            <option value="">总体</option>
            <option value="course">按课程</option>
            <option value="class">按班级</option>
          </select>
        </label>
        <button class="mp-btn" @click="load">查询</button>
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
          <template v-else>
            <AppG2Chart :spec="distSpec" :height="260" />
            <div class="aa-dist">
              <div v-for="d in data.distribution" :key="d.range" class="aa-dist__row">
                <span class="aa-dist__label">{{ d.range }}</span>
                <div class="aa-dist__bar-wrap"><div class="aa-dist__bar" :style="{ width: barWidth(d.count) }"></div></div>
                <span class="aa-dist__count">{{ d.count }}</span>
              </div>
            </div>
          </template>
        </AppSectionCard>

        <AppSectionCard v-if="dimension" :title="dimension === 'course' ? '按课程成绩分析统计表' : '按班级成绩分析统计表'">
          <div class="aa-export">
            <input v-model.trim="exportPurpose" class="aa-input aa-input--md" placeholder="导出用途（≥5 字，写审计）" />
            <button class="mp-btn mp-btn--primary" :disabled="downloading" @click="doExport">{{ downloading ? '导出中…' : '导出 Excel' }}</button>
          </div>
          <EmptyState v-if="!(data.rows && data.rows.length)" title="暂无分组数据" description="该学期下暂无已发布成绩" />
          <div v-else class="aa-table-wrap">
            <table class="aa-table">
              <thead>
                <tr>
                  <th class="aa-th-name">{{ dimension === 'course' ? '课程' : '班级' }}</th>
                  <th>记录数</th><th>平均分</th><th>最高</th><th>最低</th><th>及格率</th><th>优秀率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in data.rows" :key="r.name">
                  <td class="aa-td-name">{{ r.name }}</td>
                  <td>{{ r.total }}</td>
                  <td>{{ r.avgScore }}</td>
                  <td>{{ r.maxScore }}</td>
                  <td>{{ r.minScore }}</td>
                  <td>{{ pct(r.passRate) }}%</td>
                  <td>{{ pct(r.excellentRate) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩分析（/admin/academic-affairs/grade-overview）：GET /grade-views/analysis（可按课程/班级分组）+ 导出 xlsx。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppSectionCard, AppG2Chart } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGradeOverviewView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppMetricCard, AppSectionCard, AppG2Chart },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', term: '', dimension: '',
      data: { total: 0, passRate: 0, excellentRate: 0, avgScore: 0, maxScore: 0, minScore: 0, distribution: [], rows: [] },
      exportPurpose: '', downloading: false
    }
  },
  computed: {
    maxCount() { return Math.max(1, ...(this.data.distribution || []).map((d) => d.count)) },
    distSpec() {
      return {
        type: 'interval',
        data: (this.data.distribution || []).map((d) => ({ name: d.range, value: d.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
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
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 200px; }
.aa-input--md { width: 260px; }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.aa-dist__row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.aa-dist__label { width: 72px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-dist__bar-wrap { flex: 1; height: 18px; background: var(--fill-100, #f2f3f5); border-radius: 4px; overflow: hidden; }
.aa-dist__bar { height: 100%; background: var(--primary-400, #60a5fa); border-radius: 4px; }
.aa-dist__count { width: 48px; text-align: right; font-size: 13px; color: var(--text-900, #1f2329); }
.aa-export { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.aa-table-wrap { overflow-x: auto; }
.aa-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.aa-table th, .aa-table td { padding: 8px 10px; text-align: center; border-bottom: 1px solid var(--border-200, #e5e6eb); white-space: nowrap; }
.aa-table th { color: var(--text-700, #4e5969); font-weight: 600; background: var(--fill-100, #f7f8fa); }
.aa-table td { color: var(--text-900, #1f2329); }
.aa-th-name, .aa-td-name { text-align: left; min-width: 160px; }
</style>
