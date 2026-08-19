<template>
  <ModulePageShell
    title="学期周次"
    subtitle="按开学日期与教学周数展开逐周日期，叠加校历假期/考试/实习安排，标注当前所在周"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" :options="termOptions" @change="loadWeeks" />
        </label>
      </div>

      <p v-if="currentError" class="mp-note">当前学期解析失败，未自动猜测“当前”；已保留显式学期选择供历史周次查询。{{ currentError }}</p>

      <EmptyState
        v-if="!termsLoading && !terms.length"
        title="还没有学年学期"
        description="学期周次依附于学期，请先到「学年学期」创建并发布一个学期"
      >
        <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</AppButton>
      </EmptyState>

      <template v-else>
        <ErrorState v-if="error" :description="error" @retry="loadWeeks" />
        <LoadingState v-else-if="loading" />
        <EmptyState
          v-else-if="!weeks.length"
          title="该学期尚未配置教学周"
          description="请先到「教学周配置」设置教学周总数与开学日期"
        >
          <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/terms/teaching-weeks')">前往教学周配置</AppButton>
        </EmptyState>
        <DataTable v-else :columns="columns" :rows="weeks" row-key="weekNo">
          <template #cell-weekNo="{ row }">
            <span :class="{ 'aa-week-current': row.isCurrent }">第 {{ row.weekNo }} 周{{ row.isCurrent ? '（本周）' : '' }}</span>
          </template>
          <template #cell-range="{ row }">{{ row.startDate }} ~ {{ row.endDate }}</template>
          <template #cell-weekType="{ row }">
            <AppStatusTag :type="typeColor(row.weekType)" dot>{{ TYPE_LABEL[row.weekType] || row.weekType }}</AppStatusTag>
          </template>
          <template #cell-remark="{ row }">{{ row.remark || '—' }}</template>
        </DataTable>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学期周次（/admin/academic-affairs/terms/weeks）：历史学期显式可查；默认 term 由 A-C1 /terms/current 决定。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppTermEntityPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { loadAcademicTermCatalog } from '@/modules/academicAffairs/pickerAdapters'

const TYPE_LABEL = { TEACHING: '教学周', EXAM: '考试周', HOLIDAY: '假期', INTERNSHIP: '实习周' }
const TYPE_COLOR = { TEACHING: 'default', EXAM: 'danger', HOLIDAY: 'success', INTERNSHIP: 'warning' }

export default {
  name: 'AaTermWeeksView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppTermEntityPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TYPE_LABEL,
      termsLoading: true,
      terms: [],
      termId: '',
      currentContext: null,
      currentError: '',
      loading: false,
      error: '',
      weeks: [],
      columns: [
        { key: 'weekNo', title: '周次' },
        { key: 'range', title: '起止日期' },
        { key: 'weekType', title: '类型' },
        { key: 'remark', title: '备注' }
      ]
    }
  },
  computed: {
    termOptions() {
      return this.terms.map((t) => ({
        value: t.termId,
        label: `${t.yearCode} 第 ${t.termNo} 学期${this.isResolvedCurrent(t) ? '（全校当前）' : ''}`
      }))
    }
  },
  created() {
    this.refreshTermCatalog()
  },
  methods: {
    typeColor(t) { return TYPE_COLOR[t] || 'default' },
    isResolvedCurrent(term) {
      return Boolean(term && this.currentContext?.termId) && String(term.termId) === String(this.currentContext.termId)
    },
    async loadCurrentContext() {
      this.currentError = ''
      const res = await academicAffairsApi.getCurrentTerm()
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败'
      }
    },
    async refreshTermCatalog() {
      this.termsLoading = true
      try {
        this.terms = await loadAcademicTermCatalog()
        await this.loadCurrentContext()
        const resolved = this.terms.find((t) => this.isResolvedCurrent(t))
        const selected = resolved || this.terms[0]
        if (selected) {
          this.termId = selected.termId
          this.loadWeeks()
        }
      } catch (error) {
        this.error = error.message || '学期数据加载失败'
      }
      this.termsLoading = false
    },
    async loadWeeks() {
      if (!this.termId) return
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTermWeeks(this.termId)
      if (res.code === 0) {
        this.weeks = res.data || []
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-select {
  height: 32px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
}
.aa-week-current { font-weight: 600; color: var(--primary-600, #2563eb); }
</style>
