<template>
  <ModulePageShell
    title="补考重修缓考免修 · 统计分析"
    subtitle="四条线人数（批次数）与通过率 · 按学期/学院/维度下钻"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aamk-filter">
        <label class="aamk-filter__item">学期
          <AppTermCodePicker v-model="filters.term" placeholder="全部学期" />
        </label>
        <label class="aamk-filter__item">学院
          <AppCollegePicker v-model="filters.collegeId" :options="collegeOptions" placeholder="全部学院" />
        </label>
        <label class="aamk-filter__item">下钻维度
          <AppSelect v-model="filters.dimension" :options="dimensionOptions" />
        </label>
        <AppButton :loading="loading" @click="search">查询</AppButton>
        <AppButton variant="ghost" :disabled="loading" @click="openExport">导出 Excel</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="search" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="aamk-cards">
          <AppMetricCard
            v-for="c in cards"
            :key="c.key"
            :title="c.title"
            :value="c.count"
            unit="人/批次"
            :description="c.rateText"
            drillable
            :drill-target="c.key"
            @drill="onDrill"
          />
        </div>

        <div v-if="groups" class="aamk-groups">
          <AppSectionCard v-for="c in cards" :key="`g-${c.key}`" :title="`${c.title} · ${dimensionLabel}分布`">
            <EmptyState v-if="!(groups[c.key] || []).length" title="暂无分组数据" />
            <template v-else>
              <AppG2Chart :spec="groupChartSpec(groups[c.key])" :height="220" />
              <ul class="aamk-group-list">
                <li v-for="g in groups[c.key]" :key="g.key" class="aamk-group-item">
                  <span class="aamk-group-item__key">{{ g.key }}</span>
                  <span class="aamk-group-item__count">{{ g.count }}</span>
                </li>
              </ul>
            </template>
          </AppSectionCard>
        </div>

        <AppSectionCard v-if="drillLine" :title="`${drillLineLabel} · 明细`">
          <EmptyState v-if="!detailRows.length" title="暂无数据" />
          <DataTable v-else :columns="detailColumns" :rows="detailRows" row-key="rowKey" />
        </AppSectionCard>
      </template>
    </div>

    <AppExportConfirm
      v-model:visible="exportVisible"
      module-name="补考重修缓考免修统计"
      :scope-label="ctx.dataScope.scopeName"
      :submitting="exporting"
      @confirm="doExport"
    />
  </ModulePageShell>
</template>

<script>
/** 补考重修缓考免修 · 统计分析（三级施工卡 10）：/admin/academic-affairs/makeup/stats，独立页面（非 console tab）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppSectionCard, AppExportConfirm, AppG2Chart, AppTermCodePicker, AppCollegePicker, AppSelect } from '@/components/common'
import { academicAffairsApi, academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _LINES = [
  { key: 'makeup', title: '补考' },
  { key: 'retake', title: '重修' },
  { key: 'deferred', title: '缓考' },
  { key: 'exemption', title: '免修' }
]
const _DIM_LABEL = { course: '课程', term: '学期', college: '学院' }
const _DETAIL_COLUMNS = {
  makeup: [{ key: 'courseName', title: '课程' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }, { key: 'finalScore', title: '最终成绩' }],
  retake: [{ key: 'studentName', title: '学生' }, { key: 'courseName', title: '课程' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }],
  exemption: [{ key: 'studentName', title: '学生' }, { key: 'courseName', title: '课程' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }],
  deferred: [{ key: 'studentName', title: '学生' }, { key: 'courseName', title: '课程' }, { key: 'status', title: '状态' }]
}

export default {
  name: 'AaMakeupStatsView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppMetricCard, AppSectionCard, AppExportConfirm, AppG2Chart, AppTermCodePicker, AppCollegePicker, AppSelect },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '',
      filters: { term: '', collegeId: '', dimension: '' },
      opts: { terms: [], colleges: [] },
      stats: null, groups: null,
      drillLine: '', detailRows: [],
      exportVisible: false, exporting: false
    }
  },
  computed: {
    collegeOptions() {
      return [{ label: '全部学院', value: '' }, ...this.opts.colleges.map((c) => ({ label: c.label, value: c.id }))]
    },
    dimensionOptions() {
      return [
        { label: '不分组', value: '' }, { label: '按课程', value: 'course' },
        { label: '按学期', value: 'term' }, { label: '按学院', value: 'college' }
      ]
    },
    cards() {
      if (!this.stats) return _LINES.map((l) => ({ ...l, count: 0, rateText: '暂无数据' }))
      return _LINES.map((l) => {
        const d = this.stats[l.key] || { count: 0, passRate: null }
        const rateText = d.passRate === null || d.passRate === undefined ? '通过率：暂无终态数据' : `通过率：${Math.round(d.passRate * 1000) / 10}%`
        return { ...l, count: d.count, rateText }
      })
    },
    dimensionLabel() { return _DIM_LABEL[this.filters.dimension] || '' },
    drillLineLabel() { return (_LINES.find((l) => l.key === this.drillLine) || {}).title || '' },
    detailColumns() { return _DETAIL_COLUMNS[this.drillLine] || [] }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const f = await academicAffairsApi.getStatsFilters()
    if (f.code === 0) this.opts = { terms: f.data.terms || [], colleges: f.data.colleges || [] }
    this.search()
  },
  methods: {
    groupChartSpec(rows) {
      return {
        type: 'interval',
        data: (rows || []).map((g) => ({ name: g.key, value: g.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    async search() {
      this.loading = true; this.error = ''; this.drillLine = ''; this.detailRows = []
      const res = await api.stats({
        term: this.filters.term || undefined,
        collegeId: this.filters.collegeId || undefined,
        dimension: this.filters.dimension || undefined
      })
      if (res.code === 0) { this.stats = res.data; this.groups = res.data.groups || null } else this.error = res.message
      this.loading = false
    },
    async onDrill(line) {
      this.drillLine = line
      const res = await api.statsDetail({
        term: this.filters.term || undefined,
        collegeId: this.filters.collegeId || undefined,
        line,
        pageSize: 100
      })
      if (res.code === 0) this.detailRows = (res.data.list || []).map((r, i) => ({ ...r, rowKey: `${line}-${i}` }))
      else toast.error(res.message)
    },
    openExport() { this.exportVisible = true },
    async doExport({ reason }) {
      this.exporting = true
      const res = await api.exportStats({
        term: this.filters.term || undefined,
        collegeId: this.filters.collegeId || undefined,
        purpose: reason
      })
      this.exporting = false
      if (res.code !== 0) { toast.error(res.message || '导出失败'); return }
      this.exportVisible = false
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = `补考重修缓考免修统计-${Date.now()}.xlsx`
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
.aamk-filter { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.aamk-filter__item { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary, #64748b); }
.aamk-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.aamk-groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.aamk-group-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aamk-group-item { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px dashed var(--border-color, #e5e7eb); }
.aamk-group-item__key { color: var(--text-secondary, #64748b); }
.aamk-group-item__count { font-weight: 600; }
</style>
