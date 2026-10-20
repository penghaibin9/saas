<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="学期归档"
    subtitle="查看各学期的归档进度，衔接 13 数据域完整性检查与正式封存。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="$route.query.returnToken" @click="academicFlow?.back($route.query.returnToken, '/admin/academic-affairs/terms')">返回原位置</AppButton>
      <AppButton :disabled="loading" @click="load">刷新归档关系</AppButton>
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
          <div v-if="row.checkedAt" class="mp-cell-sub">检查于 {{ formatTime(row.checkedAt) }}</div>
          <div v-if="row.missingCount !== null && row.missingCount !== undefined" class="mp-cell-sub">缺失 {{ row.missingCount }} 域</div>
        </template>
        <template #cell-archiveBatchId="{ row }">{{ row.archiveBatchId || '未建归档批次' }}</template>
        <template #cell-sealedVersion="{ row }">
          <strong v-if="row.sealedVersion">V{{ row.sealedVersion }}</strong>
          <span v-else>{{ row.termStatus === 'ARCHIVED' ? '封存版本缺失' : '尚未封存' }}</span>
          <div v-if="row.manifestHash" class="mp-cell-sub">{{ row.manifestHash.slice(0, 12) }}…</div>
        </template>
        <template #cell-archivedAt="{ row }">{{ formatTime(row.archivedAt) }}</template>
        <template #cell-actions="{ row }"><AppButton size="small" @click="selected = row">查看归档证据</AppButton></template>
      </DataTable>
      <p class="mp-note">归档检查与封存在「教务归档」办理。归档后发现错误必须走纠错版本链，不普通解冻。</p>
    </div>
    <AppDrawer :visible="!!selected" title="学期与归档证据" mode="modal" size="large" @close="selected = null">
      <AaCalendarArchivePanel v-if="selected" :term="selected" :ctx="ctx" />
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 学期归档（/admin/academic-affairs/terms/archive-status）：GET /terms/archive-overview（只读，联动教务归档批次状态）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import AaCalendarArchivePanel from '@/modules/academicAffairs/components/AaCalendarArchivePanel.vue'

const TERM_STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' }
const TERM_STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }
const BATCH_STATUS_LABEL = { DRAFT: '草稿', CHECKING: '检查中', READY: '完整可归档', MISSING_ITEMS: '有缺失', ARCHIVED: '已归档', CANCELLED: '已取消' }
const BATCH_STATUS_TYPE = { DRAFT: 'default', CHECKING: 'processing', READY: 'processing', MISSING_ITEMS: 'danger', ARCHIVED: 'success', CANCELLED: 'default' }

export default {
  name: 'AaTermArchiveView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppStatusTag, AaCalendarArchivePanel },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  computed: {
    contextKey() { return JSON.stringify([this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns]) },
    canViewArchive() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.archive.view') }
  },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: null, loadVersion: 0, disposed: false,
      columns: [
        { key: 'term', title: '学年学期' },
        { key: 'termStatus', title: '学期状态' },
        { key: 'archiveBatchId', title: '归档批次' },
        { key: 'archiveStatus', title: '预检 / 封存结论' },
        { key: 'sealedVersion', title: '封存版本' },
        { key: 'archivedAt', title: '封存时间' },
        { key: 'actions', title: '证据入口' }
      ]
    }
  },
  created() {
    this.load()
  },
  watch: { contextKey() { this.selected = null; this.load() } },
  beforeUnmount() { this.disposed = true; this.loadVersion++ },
  methods: {
    termStatusLabel(s) { return TERM_STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    termStatusType(s) { return TERM_STATUS_TYPE[s] || 'default' },
    batchStatusLabel(s) { return BATCH_STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    batchStatusType(s) { return BATCH_STATUS_TYPE[s] || 'default' },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    async load() {
      const version = ++this.loadVersion, context = this.contextKey
      this.loading = true
      this.error = ''
      this.rows = []
      const res = await academicAffairsApi.getTermArchiveOverview()
      if (version !== this.loadVersion || context !== this.contextKey || this.disposed) return
      if (res.code === 0) {
        this.rows = res.data || []
      } else {
        this.error = res.message
      }
      this.loading = false
      this.academicFlow?.restorePosition?.()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
</style>
