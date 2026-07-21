<template>
  <ModulePageShell
    title="学年管理"
    subtitle="按学年汇总学期 · 查看学期齐全度（是否已建满两学期）与学年整体进度状态"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="goCreate">＋ 新建学期</AppButton>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="还没有学年数据"
        description="点击右上角「新建学期」创建第一个学年学期"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="yearCode"
      >
        <template #cell-yearCode="{ row }">
          <div class="mp-cell-main">{{ row.yearCode }} 学年</div>
          <div class="mp-cell-sub" v-if="row.startDate && row.endDate">{{ row.startDate }} ~ {{ row.endDate }}</div>
        </template>
        <template #cell-completeness="{ row }">
          <AppStatusTag :type="row.termCount >= 2 ? 'success' : 'warning'" dot>
            {{ row.termCount }} / 2 学期
          </AppStatusTag>
          <div v-if="row.termCount < 2" class="mp-cell-sub">缺 {{ 2 - row.termCount }} 个学期未建</div>
        </template>
        <template #cell-current="{ row }">
          <AppStatusTag v-if="row.isCurrentYear" type="success" dot>当前学年</AppStatusTag>
          <span v-else class="mp-cell-sub">—</span>
        </template>
        <template #cell-yearStatus="{ row }">
          <AppStatusTag :type="yearStatusType(row.yearStatus)" dot>{{ yearStatusLabel(row.yearStatus) }}</AppStatusTag>
        </template>
        <template #cell-terms="{ row }">
          <div class="aa-year-terms">
            <span v-for="t in row.terms" :key="t.termId" class="aa-year-term-chip">
              第{{ t.termNo }}学期
              <AppStatusTag :type="termStatusType(t.status)" dot>{{ termStatusLabel(t.status) }}</AppStatusTag>
            </span>
          </div>
        </template>
      </DataTable>

      <p class="mp-note">
        学年由学期的「学年编码」自动归组计算，不单独维护学年记录；如需调整某学期所属学年，请到「学期管理」编辑对应学期。
        <button class="mp-link" @click="$router.push('/admin/academic-affairs/terms')">前往学期管理</button>
      </p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学年管理（/admin/academic-affairs/terms/years）：GET /academic-affairs/terms/years（只读聚合，按学年汇总学期）。
 * 设计来源：project_rule（表单字段文档「学年名称」随学期创建表单一并录入，无独立学年实体）+
 * existing_code（聚合字段全部来自既有 t_aa_term.year_code/status/is_current）；聚合展示本身为 ai_proposal。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const YEAR_STATUS_LABEL = { ACTIVE: '进行中', ARCHIVED: '已归档', PLANNING: '筹备中', MIXED: '状态不一致' }
const YEAR_STATUS_TYPE = { ACTIVE: 'success', ARCHIVED: 'info', PLANNING: 'default', MIXED: 'warning' }
const TERM_STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中', FROZEN: '已冻结', ARCHIVED: '已归档' }
const TERM_STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }

export default {
  name: 'AaAcademicYearView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      columns: [
        { key: 'yearCode', title: '学年' },
        { key: 'completeness', title: '学期齐全度' },
        { key: 'current', title: '当前学年' },
        { key: 'yearStatus', title: '学年状态' },
        { key: 'terms', title: '学期明细' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    yearStatusLabel(s) { return YEAR_STATUS_LABEL[s] || s || '' },
    yearStatusType(s) { return YEAR_STATUS_TYPE[s] || 'default' },
    termStatusLabel(s) { return TERM_STATUS_LABEL[s] || s || '' },
    termStatusType(s) { return TERM_STATUS_TYPE[s] || 'default' },
    goCreate() {
      this.$router.push('/admin/academic-affairs/terms/new')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getAcademicYears()
      if (res.code === 0) {
        this.rows = res.data || []
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
.aa-year-terms {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.aa-year-term-chip {
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
