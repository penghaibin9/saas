<template>
  <section class="pa-panel" aria-labelledby="pa-title">
    <header class="pa-head">
      <div>
        <span class="pa-eyebrow">益阳采购 AP19～AP24</span>
        <h2 id="pa-title">过程统计与绩效汇总</h2>
        <p>周 / 月 / 全部时间共用同一业务事实；指导老师、班主任、院系、专业、班级和实习生均可切换，自定义列与 Excel 完全同条件。</p>
      </div>
      <AppExportButton
        :export-fn="exportFn"
        :has-permission="canExport"
        :disabled="!batchId || loading || !selectedKeys.length"
      >导出当前列</AppExportButton>
    </header>

    <div class="pa-toolbar">
      <label>
        <span>统计口径</span>
        <select v-model="groupBy" @change="changeGroup">
          <option v-for="item in groupOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </label>
      <label>
        <span>时间范围</span>
        <select v-model="period" @change="reload">
          <option value="WEEK">按周</option>
          <option value="MONTH">按月</option>
          <option value="ALL">全部时间</option>
        </select>
      </label>
      <label v-if="period !== 'ALL'">
        <span>参照日期</span>
        <input v-model="anchor" type="date" @change="reload" />
      </label>
      <AppButton variant="ghost" :disabled="loading || !batchId" @click="reload">刷新</AppButton>
    </div>

    <div v-if="!batchId" class="pa-state">请先选择实习批次。</div>
    <div v-else-if="error" class="pa-state is-error">
      <span>{{ error }}</span>
      <AppButton variant="ghost" size="sm" @click="reload">重试</AppButton>
    </div>
    <div v-else>
      <div class="pa-meta">
        <span>{{ groupLabel }} · {{ periodLabel }}</span>
        <span v-if="windowLabel">{{ windowLabel }}</span>
        <span>共 {{ total }} 行</span>
      </div>

      <details class="pa-columns" open>
        <summary>自定义查看字段（{{ selectedKeys.length }}/{{ availableColumns.length }}）</summary>
        <div class="pa-column-grid">
          <label v-for="item in availableColumns" :key="item.key">
            <input
              type="checkbox"
              :checked="selectedKeys.includes(item.key)"
              @change="toggleColumn(item.key, $event.target.checked)"
            />
            <span>{{ item.title }}</span>
          </label>
        </div>
        <div class="pa-column-actions">
          <button type="button" @click="selectAllColumns">全选</button>
          <button type="button" @click="useCompactColumns">精简常用列</button>
        </div>
      </details>

      <LoadingState v-if="loading" />
      <template v-else>
        <DataTable
          v-if="items.length && tableColumns.length"
          :columns="tableColumns"
          :rows="items"
          row-key="rowKey"
        >
          <template v-for="column in rateColumns" #[`cell-${column.key}]="{ row }" :key="`rate-${column.key}`">
            <span>{{ formatRate(row[column.key]) }}</span>
          </template>
          <template #cell-totalScore="{ row }">
            <span>{{ row.totalScore == null ? '—' : row.totalScore }}</span>
          </template>
        </DataTable>
        <div v-else class="pa-state">当前统计条件暂无数据。</div>

        <div v-if="total > pageSize" class="pa-pager">
          <span>第 {{ page }} / {{ totalPages }} 页</span>
          <div>
            <AppButton variant="ghost" size="sm" :disabled="page <= 1 || loading" @click="goPage(page - 1)">上一页</AppButton>
            <AppButton variant="ghost" size="sm" :disabled="page >= totalPages || loading" @click="goPage(page + 1)">下一页</AppButton>
          </div>
        </div>
      </template>

      <details v-if="definitions" class="pa-definitions">
        <summary>查看统计口径</summary>
        <dl>
          <div v-for="(value, key) in definitions" :key="key">
            <dt>{{ definitionLabel(key) }}</dt><dd>{{ value }}</dd>
          </div>
        </dl>
      </details>
    </div>
  </section>
</template>

<script>
import { DataTable, LoadingState } from '@/components/business'
import { AppExportButton } from '@/components/common'
import { AppButton } from '@/components/ui'
import { statsApi } from '@/modules/internship/api/stats.api'

const GROUPS = [
  ['STUDENT', '实习生过程统计'],
  ['ADVISOR', '指导老师绩效'],
  ['HOMEROOM', '班主任绩效'],
  ['COLLEGE', '院系实习汇总'],
  ['MAJOR', '专业实习汇总'],
  ['CLASS', '班级实习汇总']
]
const RATE_RE = /(Rate|率)$/
const today = () => {
  const d = new Date()
  const p = value => String(value).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
const COMPACT = {
  STUDENT: ['studentName','studentNo','college','major','className','advisorName','expectedCheckins','actualCheckins','weeklyExpected','weeklySubmitted','weeklyCompletionRate','totalScore'],
  ADVISOR: ['name','employeeNo','college','studentCount','boundCount','averageCheckinRate','weeklyExpected','weeklySubmitted','weeklyReviewRate','weeklyTimelyReviewRate','monthlyCompletionRate','summaryReviewRate'],
  HOMEROOM: ['name','employeeNo','college','className','studentCount','boundCount','averageCheckinRate','weeklyCompletionRate','weeklyReviewRate','weeklyTimelyReviewRate','monthlyCompletionRate','summaryReviewRate'],
  COLLEGE: ['college','studentCount','internshipStudentCount','bindingRate','onboardRate','majorMatchRate','stabilityRate','checkinRate','weeklyCompletionRate','weeklyReviewRate','monthlyCompletionRate','monthlyReviewRate'],
  MAJOR: ['college','major','studentCount','bindingRate','onboardRate','majorMatchRate','stabilityRate','checkinRate','weeklyCompletionRate','weeklyReviewRate','monthlyCompletionRate','monthlyReviewRate'],
  CLASS: ['college','major','className','headTeacherName','studentCount','bindingRate','onboardRate','majorMatchRate','stabilityRate','checkinRate','weeklyCompletionRate','monthlyCompletionRate']
}

export default {
  name: 'ProcessAnalyticsPanel',
  components: { DataTable, LoadingState, AppExportButton, AppButton },
  props: {
    batchId: { type: [String, Number], default: '' },
    canExport: { type: Boolean, default: false }
  },
  data() {
    return {
      groupBy: 'STUDENT',
      period: 'ALL',
      anchor: today(),
      availableColumns: [],
      selectedKeys: [],
      items: [],
      total: 0,
      page: 1,
      pageSize: 50,
      loading: false,
      error: '',
      windowStart: '',
      windowEnd: '',
      definitions: null,
      seq: 0
    }
  },
  computed: {
    groupOptions() { return GROUPS.map(([value, label]) => ({ value, label })) },
    groupLabel() { return GROUPS.find(([value]) => value === this.groupBy)?.[1] || this.groupBy },
    periodLabel() { return { WEEK: '按周', MONTH: '按月', ALL: '全部时间' }[this.period] || this.period },
    windowLabel() {
      if (!this.windowStart || !this.windowEnd) return ''
      return `${this.windowStart} 至 ${this.windowEnd}`
    },
    tableColumns() {
      return this.availableColumns
        .filter(item => this.selectedKeys.includes(item.key))
        .map(item => ({ key: item.key, title: item.title, width: this.columnWidth(item.key) }))
    },
    rateColumns() { return this.tableColumns.filter(item => RATE_RE.test(item.key)) },
    totalPages() { return Math.max(1, Math.ceil(this.total / this.pageSize)) },
    requestColumns() { return this.selectedKeys.join(',') }
  },
  watch: {
    batchId() { this.page = 1; this.reload() }
  },
  mounted() { this.reload() },
  beforeUnmount() { this.seq += 1 },
  methods: {
    params(extra = {}) {
      return {
        batchId: this.batchId || undefined,
        groupBy: this.groupBy,
        period: this.period,
        anchor: this.period === 'ALL' ? undefined : this.anchor,
        page: this.page,
        pageSize: this.pageSize,
        ...extra
      }
    },
    async loadAllColumns() {
      const seq = ++this.seq
      this.loading = true
      this.error = ''
      const res = await statsApi.getProcessAnalytics(this.params({ page: this.page }))
      if (seq !== this.seq) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '过程统计加载失败'
        return
      }
      const data = res.data || {}
      this.availableColumns = data.availableColumns || []
      if (!this.selectedKeys.length || this.selectedKeys.some(key => !this.availableColumns.some(item => item.key === key))) {
        this.selectedKeys = this.availableColumns.map(item => item.key)
      }
      this.applyData(data)
    },
    async reload() {
      if (!this.batchId) {
        this.items = []; this.total = 0; this.availableColumns = []; this.selectedKeys = []; this.error = ''
        return
      }
      await this.loadAllColumns()
    },
    applyData(data) {
      this.items = data.items || []
      this.total = Number(data.total || 0)
      this.windowStart = data.windowStart || ''
      this.windowEnd = data.windowEnd || ''
      this.definitions = data.definitions || null
    },
    async changeGroup() {
      this.page = 1
      this.selectedKeys = []
      await this.reload()
    },
    toggleColumn(key, checked) {
      if (checked) {
        if (!this.selectedKeys.includes(key)) this.selectedKeys = [...this.selectedKeys, key]
        return
      }
      if (this.selectedKeys.length <= 1) return
      this.selectedKeys = this.selectedKeys.filter(item => item !== key)
    },
    selectAllColumns() { this.selectedKeys = this.availableColumns.map(item => item.key) },
    useCompactColumns() {
      const wanted = COMPACT[this.groupBy] || []
      const valid = wanted.filter(key => this.availableColumns.some(item => item.key === key))
      this.selectedKeys = valid.length ? valid : this.availableColumns.slice(0, 12).map(item => item.key)
    },
    async goPage(value) {
      if (value < 1 || value > this.totalPages) return
      this.page = value
      await this.reload()
    },
    exportFn() {
      return statsApi.exportProcessAnalytics(this.params({
        columns: this.requestColumns,
        page: undefined,
        pageSize: undefined
      }))
    },
    formatRate(value) { return value == null ? '暂无数据' : `${value}%` },
    columnWidth(key) {
      if (RATE_RE.test(key)) return '110px'
      if (/Name|college|major|class|teacher|batch|internshipType/i.test(key)) return '150px'
      return '110px'
    },
    definitionLabel(key) {
      return {
        binding: '绑定',
        checkin: '签到',
        stability: '稳定率',
        majorMatch: '专业对口',
        weeklyExpected: '周报应交',
        timelyReview: '准时批阅',
        customColumns: '自定义列'
      }[key] || key
    }
  }
}
</script>

<style scoped>
.pa-panel{margin-top:20px;border:1px solid var(--border-base);border-radius:12px;background:var(--bg-card);overflow:hidden}
.pa-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;padding:20px;border-bottom:1px solid var(--border-base)}
.pa-head h2{margin:4px 0 0;font-size:18px}.pa-head p{max-width:850px;margin:7px 0 0;color:var(--text-secondary);font-size:13px;line-height:1.65}
.pa-eyebrow{font-size:11px;font-weight:700;color:var(--primary-600)}
.pa-toolbar{display:flex;align-items:end;gap:12px;flex-wrap:wrap;padding:14px 20px;border-bottom:1px solid var(--border-base);background:var(--bg-subtle,#f8fafc)}
.pa-toolbar label{display:grid;gap:6px;font-size:12px;color:var(--text-secondary)}
.pa-toolbar select,.pa-toolbar input{height:36px;min-width:150px;padding:0 9px;border:1px solid var(--border-base);border-radius:7px;background:var(--bg-card);color:var(--text-primary)}
.pa-meta{display:flex;gap:14px;flex-wrap:wrap;padding:12px 20px;color:var(--text-secondary);font-size:12px}
.pa-columns{margin:0 20px 14px;padding:12px 14px;border:1px solid var(--border-base);border-radius:9px;background:var(--bg-subtle,#f8fafc)}
.pa-columns summary{cursor:pointer;font-size:12px;font-weight:650}.pa-column-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px 14px;margin-top:12px}
.pa-column-grid label{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text-secondary)}
.pa-column-actions{display:flex;gap:12px;margin-top:12px}.pa-column-actions button{border:0;background:transparent;color:var(--primary-600);font-size:12px;cursor:pointer;padding:0}
.pa-state{display:flex;align-items:center;justify-content:center;gap:10px;padding:32px 20px;color:var(--text-secondary)}.pa-state.is-error{color:var(--danger-600)}
.pa-pager{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border-top:1px solid var(--border-base);font-size:12px;color:var(--text-secondary)}.pa-pager>div{display:flex;gap:8px}
.pa-definitions{margin:16px 20px 20px;padding:12px 14px;border:1px solid var(--border-base);border-radius:9px}.pa-definitions summary{cursor:pointer;font-size:12px;font-weight:650}
.pa-definitions dl{display:grid;gap:8px;margin:12px 0 0}.pa-definitions dl>div{display:grid;grid-template-columns:100px 1fr;gap:12px}.pa-definitions dt{font-size:12px;font-weight:650}.pa-definitions dd{margin:0;font-size:12px;color:var(--text-secondary);line-height:1.6}
@media(max-width:760px){.pa-head{flex-direction:column}.pa-toolbar label{width:100%}.pa-toolbar select,.pa-toolbar input{width:100%}.pa-pager{align-items:flex-start;flex-direction:column}}
</style>
