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
          <select v-model="termId" class="aa-select" @change="loadWeeks">
            <option v-for="t in terms" :key="t.termId" :value="t.termId">
              {{ t.yearCode }} 第 {{ t.termNo }} 学期{{ t.isCurrent ? '（当前）' : '' }}
            </option>
          </select>
        </label>
      </div>

      <EmptyState
        v-if="!termsLoading && !terms.length"
        title="还没有学年学期"
        description="学期周次依附于学期，请先到「学年学期」创建并发布一个学期"
      >
        <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</button>
      </EmptyState>

      <template v-else>
        <ErrorState v-if="error" :description="error" @retry="loadWeeks" />
        <LoadingState v-else-if="loading" />
        <EmptyState
          v-else-if="!weeks.length"
          title="该学期尚未配置教学周"
          description="请先到「教学周配置」设置教学周总数与开学日期"
        >
          <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/academic-affairs/terms/teaching-weeks')">前往教学周配置</button>
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
/** 学期周次（/admin/academic-affairs/terms/weeks）：GET /terms/{id}/weeks（只读计算，来自学期开学日+教学周数+校历）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const TYPE_LABEL = { TEACHING: '教学周', EXAM: '考试周', HOLIDAY: '假期', INTERNSHIP: '实习周' }
const TYPE_COLOR = { TEACHING: 'default', EXAM: 'danger', HOLIDAY: 'success', INTERNSHIP: 'warning' }

export default {
  name: 'AaTermWeeksView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TYPE_LABEL,
      termsLoading: true,
      terms: [],
      termId: '',
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
  created() {
    this.loadTerms()
  },
  methods: {
    typeColor(t) { return TYPE_COLOR[t] || 'default' },
    async loadTerms() {
      this.termsLoading = true
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) {
        this.terms = res.data.list
        const cur = this.terms.find((t) => t.isCurrent) || this.terms[0]
        if (cur) {
          this.termId = cur.termId
          this.loadWeeks()
        }
      } else {
        this.error = res.message
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
