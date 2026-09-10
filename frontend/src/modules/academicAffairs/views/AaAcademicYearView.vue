<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="学年管理"
    subtitle="按学年查看学期设置、起止日期与筹备进度。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="$route.query.returnToken" @click="academicFlow?.back($route.query.returnToken, '/admin/academic-affairs/terms')">返回原位置</AppButton>
      <AppButton v-if="canManage" variant="primary" @click="goCreate">新建学期</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="学年 · 台账">
      <form class="aa-year-filter" @submit.prevent="applyFilter">
        <AppTextInput v-model="search" placeholder="搜索学年" aria-label="搜索学年" />
        <AppButton type="submit">查询</AppButton><AppButton @click="search = ''; applyFilter()">清空</AppButton>
        <span class="mp-note">已加载 {{ rows.length }} 个学年 · 当前显示 {{ filteredRows.length }} 个</span>
      </form>
      <p v-if="currentError" class="mp-note">当前学期解析失败，本页不猜测“当前学年”；学年汇总仍可正常查看。{{ currentError }}</p>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!filteredRows.length"
        title="还没有学年数据"
        description="点击右上角「新建学期」创建第一个学年学期"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="filteredRows"
        row-key="yearCode"
      >
        <template #cell-yearCode="{ row }">
          <div class="mp-cell-main">{{ row.yearCode }} 学年</div>
          <div class="mp-cell-sub" v-if="row.startDate && row.endDate">{{ row.startDate.slice(0, 10) }} ~ {{ row.endDate.slice(0, 10) }}</div>
        </template>
        <template v-for="no in [1, 2]" :key="no" #[`cell-term${no}`]="{ row }">
          <template v-for="term in (row.terms || []).filter(t => Number(t.termNo) === no)" :key="term.termId">
            <button class="mp-link" @click="goTerm(term)">{{ term.termName || `${row.yearCode} 第${no}学期` }}</button>
            <div class="mp-cell-sub">{{ termStatusLabel(term.status) }} · {{ term.termId }}</div>
          </template>
          <span v-if="!(row.terms || []).some(t => Number(t.termNo) === no)" class="mp-cell-sub">尚未建立</span>
        </template>
        <template #cell-plans="{ row }">
          <strong>{{ row.programCount ?? 0 }}</strong>
          <span class="mp-cell-sub">当届生效方案</span>
        </template>
        <template #cell-current="{ row }">
          <AppStatusTag v-if="isResolvedCurrentYear(row)" type="success" dot>当前学年</AppStatusTag>
          <span v-else-if="currentError" class="mp-cell-sub">待核对</span>
          <span v-else class="mp-cell-sub">—</span>
        </template>
        <template #cell-yearStatus="{ row }">
          <AppStatusTag :type="yearStatusType(row.yearStatus)" dot>{{ yearStatusLabel(row.yearStatus) }}</AppStatusTag>
        </template>
        <template #cell-terms="{ row }">
          <div class="aa-year-terms">
            <button v-for="t in row.terms" :key="t.termId" type="button" class="aa-year-term-chip" @click="goTerm(t)">
              第{{ t.termNo }}学期
              <AppStatusTag :type="termStatusType(t.status)" dot>{{ termStatusLabel(t.status) }}</AppStatusTag>
            </button>
          </div>
        </template>
      </DataTable>
      </AppSectionCard>

      <p class="mp-note">
        学年由所属学期自动汇总。点击学期可查看详情；学年和学期序号创建后不可修改。
        <button class="mp-link" @click="$router.push('/admin/academic-affairs/terms')">前往学期管理</button>
      </p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学年管理（/admin/academic-affairs/terms/years）：学年聚合可独立读取；“当前学年”必须由 A-C1 resolved term 的 yearCode 决定。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppTextInput, AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'

const YEAR_STATUS_LABEL = { ACTIVE: '含已发布学期', ARCHIVED: '已归档', PLANNING: '筹备中', MIXED: '状态不一致' }
const YEAR_STATUS_TYPE = { ACTIVE: 'success', ARCHIVED: 'info', PLANNING: 'default', MIXED: 'warning' }
const TERM_STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' }
const TERM_STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }

export default {
  name: 'AaAcademicYearView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppTextInput, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  computed: {
    filteredRows() { return this.rows.filter(row => !this.query || String(row.yearCode).includes(this.query)) },
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') }
  },
  data() {
    return {
      loading: true,
      loadVersion: 0, disposed: false, search: '', query: '',
      error: '',
      currentContext: null,
      currentError: '',
      rows: [],
      columns: [
        { key: 'yearCode', title: '学年' },
        { key: 'term1', title: '第一学期' },
        { key: 'term2', title: '第二学期' },
        { key: 'plans', title: '关联方案' },
        { key: 'current', title: '当前学年' },
        { key: 'yearStatus', title: '学年状态' }
      ]
    }
  },
  created() {
    this.search = this.query = typeof this.$route.query.year === 'string' ? this.$route.query.year : ''
    this.load()
  },
  watch: { ctx: { deep: true, handler() { this.load() } }, '$route.query.year'(value) { this.search = this.query = typeof value === 'string' ? value : '' } },
  beforeUnmount() { this.disposed = true; this.loadVersion++ },
  methods: {
    applyFilter() { this.query = this.search.trim(); this.$router.replace({ query: { ...this.$route.query, year: this.query || undefined } }) },
    goTerm(term) { this.$router.push({ name: 'aa-term-detail', params: { termId: term.termId }, query: { returnToken: this.academicFlow?.captureReturn() } }) },
    yearStatusLabel(s) { return YEAR_STATUS_LABEL[s] || (s ? '学年状态待确认' : '') },
    yearStatusType(s) { return YEAR_STATUS_TYPE[s] || 'default' },
    termStatusLabel(s) { return TERM_STATUS_LABEL[s] || (s ? '学期状态待确认' : '') },
    termStatusType(s) { return TERM_STATUS_TYPE[s] || 'default' },
    isResolvedCurrentYear(row) {
      return Boolean(this.currentContext?.yearCode) && String(row.yearCode) === String(this.currentContext.yearCode)
    },
    goCreate() {
      if (!this.canManage) return
      this.$router.push({ path: '/admin/academic-affairs/terms/new', query: { returnToken: this.academicFlow?.captureReturn() } })
    },
    async loadCurrentContext() {
      const version = this.loadVersion, scope = JSON.stringify(this.ctx)
      this.currentError = ''
      this.currentContext = null
      const res = await academicAffairsApi.getCurrentTerm()
      if (version !== this.loadVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败'
      }
    },
    async load() {
      const version = ++this.loadVersion, scope = JSON.stringify(this.ctx)
      this.loading = true
      this.rows = []
      this.error = ''
      const [res] = await Promise.all([
        academicAffairsApi.getAcademicYears(),
        this.loadCurrentContext()
      ])
      if (version !== this.loadVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
      if (res.code === 0) {
        this.rows = res.data || []
      } else {
        this.error = res.message
      }
      this.loading = false
      this.academicFlow?.restorePosition()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-year-filter { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.aa-year-filter > :first-child { max-width: 260px; }
.aa-year-terms {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.aa-year-term-chip {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-700, #4e5969);
  padding: 2px 8px;
  border: 1px solid var(--border-100, #f0f1f2);
  border-radius: 6px;
  background: var(--bg-subtle, #f7f8fa);
}
</style>
