<template>
  <ModulePageShell
    title="免修材料归档"
    subtitle="按学期/归档状态查看免修申请材料，标记已归档留存"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="reload" @reset="resetFilters" />

      <ErrorState v-if="error" :description="error" @retry="reload" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <EmptyState v-if="!rows.length" title="暂无免修申请材料" description="学生免修申请审批后在此归档" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="exemptionId">
          <template #cell-student="{ row }">{{ row.studentName }}（{{ row.courseName }}）</template>
          <template #cell-status="{ row }"><StatusTag :type="exType(row.status)" :label="row.status" dot /></template>
          <template #cell-archiveStatus="{ row }">
            <StatusTag :type="row.archiveStatus === 'ARCHIVED' ? 'success' : 'default'"
                      :label="row.archiveStatus === 'ARCHIVED' ? '已归档' : '未归档'" dot />
          </template>
          <template #cell-materials="{ row }">
            <button v-if="(row.materialFiles || []).length" class="mp-link" @click="openMaterials(row)">
              查看材料（{{ row.materialFiles.length }}）
            </button>
            <span v-else class="aamk-muted">无材料</span>
          </template>
          <template #cell-ops="{ row }">
            <button v-if="canArchive(row)" class="mp-link" @click="markArchived(row)">标记已归档</button>
          </template>
        </DataTable>
      </template>
    </div>

    <AppDrawer :visible="materialsVisible" title="免修材料" mode="modal" size="medium" @close="materialsVisible = false">
      <AppFileList :files="materialFiles" :previewable="false" :downloadable="false" :removable="false" />
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 免修材料归档（三级施工卡 11-材料归档）：/admin/academic-affairs/exemption/archive。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import { AppFileList } from '@/components/common'
import { academicAffairsApi, academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _TERMINAL = ['APPROVED', 'REJECTED', 'CANCELLED']

export default {
  name: 'AaExemptionArchiveView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AdvancedFilter, AppDrawer, AppFileList },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [],
      filters: { term: '', status: '' },
      columns: [
        { key: 'student', title: '学生/课程' }, { key: 'status', title: '审批状态' },
        { key: 'archiveStatus', title: '归档状态' }, { key: 'materials', title: '材料' }, { key: 'ops', title: '操作' }
      ],
      materialsVisible: false, materialFiles: []
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'term', label: '学期', type: 'text', placeholder: '如 2024-2，可空=全部' },
        { key: 'status', label: '归档状态', type: 'select', options: [
          { value: 'NOT_ARCHIVED', label: '未归档' },
          { value: 'ARCHIVED', label: '已归档' }
        ] }
      ]
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.reload()
  },
  methods: {
    resetFilters() { this.filters.term = ''; this.filters.status = ''; this.reload() },
    exType(s) { return s === 'APPROVED' ? 'success' : s === 'REJECTED' ? 'danger' : 'primary' },
    canArchive(row) { return _TERMINAL.includes(row.status) && row.archiveStatus !== 'ARCHIVED' },
    async reload() {
      this.loading = true; this.error = ''
      const res = await api.archiveList({
        term: this.filters.term || undefined,
        status: this.filters.status || undefined,
        pageSize: 100
      })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    openMaterials(row) {
      this.materialFiles = (row.materialFiles || []).map((f) => ({ id: f.fileId, name: f.fileName }))
      this.materialsVisible = true
    },
    async markArchived(row) {
      const res = await api.archiveExemption(row.exemptionId)
      if (res.code === 0) { toast.success('已标记归档'); this.reload() } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
.aamk-filter { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.aamk-filter__item { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary, #64748b); }
.aamk-muted { color: var(--text-tertiary, #94a3b8); font-size: 12px; }
</style>
