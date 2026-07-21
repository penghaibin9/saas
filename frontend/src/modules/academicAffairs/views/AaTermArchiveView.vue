<template>
  <ModulePageShell
    title="学期归档"
    subtitle="按学期查看归档批次状态（只读联动）· 归档批次创建/9数据域完整性检查/确认封存请到「教务归档」执行"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/archive')">前往教务归档</AppButton>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="还没有学年学期" description="请先到「学年学期」创建一个学期" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="termId">
        <template #cell-term="{ row }">
          <div class="mp-cell-main">{{ row.yearCode }} 第 {{ row.termNo }} 学期</div>
          <div class="mp-cell-sub">{{ row.termName || '未命名' }}</div>
        </template>
        <template #cell-termStatus="{ row }">
          <AppStatusTag :type="termStatusType(row.termStatus)" dot>{{ termStatusLabel(row.termStatus) }}</AppStatusTag>
        </template>
        <template #cell-archiveStatus="{ row }">
          <AppStatusTag v-if="row.archiveBatchStatus" :type="batchStatusType(row.archiveBatchStatus)" dot>
            {{ batchStatusLabel(row.archiveBatchStatus) }}
          </AppStatusTag>
          <span v-else class="mp-cell-sub">未建归档批次</span>
        </template>
        <template #cell-archivedAt="{ row }">{{ row.archivedAt ? row.archivedAt.replace('T', ' ').slice(0, 16) : '—' }}</template>
      </DataTable>
      <p class="mp-note">「学期归档」仅提供只读总览；建批次、9 数据域完整性检查、确认归档封存、特批解冻等实际动作统一在「教务归档」执行，避免双写。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学期归档（/admin/academic-affairs/terms/archive-status）：GET /terms/archive-overview（只读，联动教务归档批次状态）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const TERM_STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中', FROZEN: '已冻结', ARCHIVED: '已归档' }
const TERM_STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }
const BATCH_STATUS_LABEL = { DRAFT: '草稿', CHECKING: '检查中', READY: '完整可归档', MISSING_ITEMS: '有缺失', ARCHIVED: '已归档', CANCELLED: '已取消' }
const BATCH_STATUS_TYPE = { DRAFT: 'default', CHECKING: 'processing', READY: 'processing', MISSING_ITEMS: 'danger', ARCHIVED: 'success', CANCELLED: 'default' }

export default {
  name: 'AaTermArchiveView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      columns: [
        { key: 'term', title: '学年学期' },
        { key: 'termStatus', title: '学期状态' },
        { key: 'archiveStatus', title: '归档批次状态' },
        { key: 'archivedAt', title: '归档时间' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    termStatusLabel(s) { return TERM_STATUS_LABEL[s] || s || '' },
    termStatusType(s) { return TERM_STATUS_TYPE[s] || 'default' },
    batchStatusLabel(s) { return BATCH_STATUS_LABEL[s] || s || '' },
    batchStatusType(s) { return BATCH_STATUS_TYPE[s] || 'default' },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTermArchiveOverview()
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
</style>
