<template>
  <ModulePageShell
    title="教务统计"
    subtitle="11 项教务运行指标 · 按学年学期 / 学院 / 专业多维筛选 · 汇总卡下钻明细"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <!-- 多维筛选栏 -->
      <div class="aa-filter">
        <label class="aa-filter__item">学期
          <select v-model="filters.termId" class="aa-input aa-input--sm">
            <option value="">全部学期</option>
            <option v-for="t in opts.terms" :key="t.id" :value="t.id">{{ t.label }}{{ t.isCurrent ? '（当前）' : '' }}</option>
          </select>
        </label>
        <label class="aa-filter__item">学院
          <select v-model="filters.collegeId" class="aa-input aa-input--sm" @change="filters.majorId = ''">
            <option value="">全部学院</option>
            <option v-for="c in opts.colleges" :key="c.id" :value="c.id">{{ c.label }}</option>
          </select>
        </label>
        <label class="aa-filter__item">专业
          <select v-model="filters.majorId" class="aa-input aa-input--sm">
            <option value="">全部专业</option>
            <option v-for="m in majorOptions" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
        </label>
        <button class="mp-btn" :disabled="loading" @click="search">查询</button>
        <button class="mp-btn mp-btn--ghost" :disabled="loading" @click="openExport">导出 Excel</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <p v-if="scopeBlocked" class="aa-scope-note">当前账号未配置教务数据范围，暂无可见统计数据（如为学院教务员请联系管理员配置本院范围）。</p>

        <!-- 指标卡片网格 -->
        <div class="aa-cards">
          <button
            v-for="ind in indicators"
            :key="ind.key"
            class="aa-card"
            :class="{ 'aa-card--muted': ind.status === 'MODULE_NOT_ENABLED', 'aa-card--active': activeDrill === ind.key, 'aa-card--drill': drillable(ind) }"
            :disabled="ind.status === 'MODULE_NOT_ENABLED'"
            @click="onCardClick(ind)"
          >
            <span class="aa-card__label">{{ ind.label }}</span>
            <template v-if="ind.status === 'MODULE_NOT_ENABLED'">
              <span class="aa-card__na">未启用</span>
              <span class="aa-card__sub">{{ ind.message }}</span>
            </template>
            <template v-else-if="ind.rate !== null && ind.rate !== undefined && ind.denominator !== undefined && ind.numerator !== undefined && ind.unit === '%'">
              <span class="aa-card__value">{{ ind.rate }}<em>%</em></span>
              <span class="aa-card__sub">{{ ind.numerator }} / {{ ind.denominator }}</span>
            </template>
            <template v-else-if="ind.unit === '%'">
              <span class="aa-card__value aa-card__value--empty">—</span>
              <span class="aa-card__sub">{{ ind.numerator }} / {{ ind.denominator }}</span>
            </template>
            <template v-else>
              <span class="aa-card__value">{{ ind.value }}<em v-if="ind.unit">{{ ind.unit }}</em></span>
              <span v-if="ind.groups && ind.groups.length" class="aa-card__sub">{{ groupSummary(ind) }}</span>
            </template>
            <span v-if="drillable(ind)" class="aa-card__drill-hint">点击下钻 →</span>
          </button>
        </div>

        <!-- 下钻明细 -->
        <div v-if="activeDrill" class="aa-drill">
          <div class="aa-drill__head">
            <strong>{{ drillTitle }}</strong>
            <button class="mp-link" @click="closeDrill">收起</button>
          </div>
          <LoadingState v-if="drill.loading" />
          <EmptyState v-else-if="!drill.rows.length" title="无明细数据" description="当前范围内没有可下钻的记录" />
          <DataTable
            v-else
            :columns="drillColumns"
            :rows="drill.rows"
            row-key="rowKey"
            :pagination="drill.pagination"
            @page-change="onDrillPage"
          />
        </div>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 教务统计总览（/admin/academic-affairs/stats）。
 * 数据全部来自真实后端 /api/v1/academic-affairs/stats/*（无 mock，手册 D1）；范围/脱敏/审计由后端裁定。
 * 下钻仅对已建后端明细端点开放：注册(未注册名单)/学籍异动/学业预警；其余卡片仅展示汇总。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const DRILL_META = {
  registration: {
    title: '未注册学生名单',
    columns: [
      { key: 'studentName', title: '学生' },
      { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'status', title: '注册状态' }
    ],
    fetch: (api, p) => api.getStatsRegistration(p)
  },
  statusChange: {
    title: '学籍异动明细',
    columns: [
      { key: 'studentName', title: '学生' },
      { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'changeType', title: '异动类型' },
      { key: 'fromStatus', title: '原状态' },
      { key: 'toStatus', title: '现状态' }
    ],
    fetch: (api, p) => api.getStatsStatusChange(p)
  },
  warning: {
    title: '学业预警明细',
    columns: [
      { key: 'studentName', title: '学生' },
      { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'className', title: '班级' },
      { key: 'level', title: '等级' },
      { key: 'warnType', title: '类型' },
      { key: 'status', title: '状态' }
    ],
    fetch: (api, p) => api.getStatsWarning(p)
  }
}

export default {
  name: 'AaStatsOverviewView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      filters: { termId: '', collegeId: '', majorId: '' },
      opts: { terms: [], colleges: [], majors: [] },
      indicators: [],
      scopeBlocked: false,
      activeDrill: '',
      drill: { loading: false, rows: [], pagination: { page: 1, pageSize: 20, total: 0 } }
    }
  },
  computed: {
    majorOptions() {
      if (!this.filters.collegeId) return this.opts.majors
      return this.opts.majors.filter((m) => String(m.collegeId) === String(this.filters.collegeId))
    },
    drillTitle() {
      return this.activeDrill ? (DRILL_META[this.activeDrill]?.title || '明细') : ''
    },
    drillColumns() {
      return this.activeDrill ? (DRILL_META[this.activeDrill]?.columns || []) : []
    }
  },
  created() {
    this.init()
  },
  methods: {
    drillable(ind) {
      return !!DRILL_META[ind.key] && ind.status !== 'MODULE_NOT_ENABLED'
    },
    groupSummary(ind) {
      return (ind.groups || []).map((g) => `${g.key}:${g.count}`).join('  ')
    },
    async init() {
      const f = await academicAffairsApi.getStatsFilters()
      if (f.code === 0) this.opts = f.data
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = {
        termId: this.filters.termId || undefined,
        collegeId: this.filters.collegeId || undefined,
        majorId: this.filters.majorId || undefined
      }
      const res = await academicAffairsApi.getStatsOverview(params)
      if (res.code === 0) {
        this.indicators = res.data.indicators || []
        this.scopeBlocked = !!res.data.scope?.blocked
      } else {
        this.error = res.message || '加载失败'
      }
      this.loading = false
      if (this.activeDrill) this.loadDrill()
    },
    search() {
      this.activeDrill = ''
      this.load()
    },
    onCardClick(ind) {
      if (!this.drillable(ind)) return
      if (this.activeDrill === ind.key) {
        this.closeDrill()
        return
      }
      this.activeDrill = ind.key
      this.drill.pagination.page = 1
      this.loadDrill()
    },
    closeDrill() {
      this.activeDrill = ''
      this.drill.rows = []
    },
    onDrillPage(p) {
      this.drill.pagination.page = p
      this.loadDrill()
    },
    async loadDrill() {
      const meta = DRILL_META[this.activeDrill]
      if (!meta) return
      this.drill.loading = true
      const params = {
        termId: this.filters.termId || undefined,
        collegeId: this.filters.collegeId || undefined,
        majorId: this.filters.majorId || undefined,
        page: this.drill.pagination.page,
        pageSize: this.drill.pagination.pageSize
      }
      const res = await meta.fetch(academicAffairsApi, params)
      if (res.code === 0) {
        this.drill.rows = (res.data.list || []).map((r, i) => ({ ...r, rowKey: `${this.activeDrill}-${i}-${r.studentNo || ''}` }))
        this.drill.pagination.total = res.data.total || 0
      } else {
        toast.error(res.message || '下钻失败')
        this.drill.rows = []
      }
      this.drill.loading = false
    },
    async openExport() {
      const purpose = window.prompt('请填写导出用途（≥5 字，将写入审计与文件水印）：', '')
      if (purpose === null) return
      if (!purpose || purpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字')
        return
      }
      const res = await academicAffairsApi.exportStats({
        termId: this.filters.termId ? Number(this.filters.termId) : undefined,
        collegeId: this.filters.collegeId ? Number(this.filters.collegeId) : undefined,
        majorId: this.filters.majorId ? Number(this.filters.majorId) : undefined,
        purpose: purpose.trim()
      })
      if (res.code !== 0) {
        toast.error(res.message || '导出失败')
        return
      }
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = `教务统计总览-${Date.now()}.xlsx`
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
.aa-input--sm { min-width: 160px; }
.mp-btn--ghost { background: transparent; border: 1px solid var(--border-300, #d0d3d9); color: var(--text-700, #4e5969); }
.aa-scope-note { margin: 4px 0; padding: 10px 12px; background: var(--warning-50, #fff7e8); border: 1px solid var(--warning-200, #ffcf8b); border-radius: 6px; color: var(--warning-700, #a86400); font-size: 13px; }
.aa-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
.aa-card { display: flex; flex-direction: column; gap: 6px; padding: 16px; text-align: left; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); cursor: default; transition: box-shadow .15s, border-color .15s; }
.aa-card--drill { cursor: pointer; }
.aa-card--drill:hover { border-color: var(--primary-400, #6aa1ff); box-shadow: 0 2px 10px rgba(22, 93, 255, .08); }
.aa-card--active { border-color: var(--primary-500, #165dff); box-shadow: 0 2px 12px rgba(22, 93, 255, .14); }
.aa-card--muted { background: var(--fill-50, #f7f8fa); }
.aa-card__label { font-size: 13px; color: var(--text-600, #6b7280); }
.aa-card__value { font-size: 26px; font-weight: 700; color: var(--text-900, #1f2329); line-height: 1.1; }
.aa-card__value em { font-size: 14px; font-weight: 500; margin-left: 2px; color: var(--text-500, #86909c); font-style: normal; }
.aa-card__value--empty { color: var(--text-400, #c9cdd4); }
.aa-card__sub { font-size: 12px; color: var(--text-500, #86909c); }
.aa-card__na { font-size: 18px; font-weight: 600; color: var(--text-400, #c9cdd4); }
.aa-card__drill-hint { font-size: 11px; color: var(--primary-500, #165dff); margin-top: 2px; }
.aa-drill { margin-top: 8px; padding: 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-drill__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
</style>
