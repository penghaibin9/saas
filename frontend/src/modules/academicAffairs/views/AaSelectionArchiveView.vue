<template>
  <ModulePageShell
    title="选课归档"
    subtitle="已归档（ARCHIVED）选课批次历史查询 · 按学期筛选 · 导出台账"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/academic-affairs/selection')">返回选课管理</AppButton>
    </template>

    <div class="aasar-toolbar">
      <AppTextInput v-model="termId" placeholder="按学期 ID 筛选（选填）" />
      <AppButton size="small" variant="ghost" @click="load">查询</AppButton>
    </div>

    <div class="aasar-layout">
      <div class="aasar-list">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无已归档批次" description="批次进入 LOCKED 状态后，在选课管理控制台点「归档」即可在此查询" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="batchId">
          <template #cell-batchName="{ row }">
            <button class="mp-link" @click="select(row)">{{ row.batchName }}</button>
          </template>
          <template #cell-lockedAt="{ row }">{{ row.lockedAt || '—' }}</template>
        </DataTable>
      </div>

      <div class="aasar-detail">
        <EmptyState v-if="!current" title="选择一个归档批次" description="查看容量/选课统计摘要并导出台账" />
        <template v-else>
          <div class="aasar-detail-title">{{ current.batchName }}</div>
          <div v-if="current.stats" class="aasar-stats">
            <span>课程 {{ current.stats.courseCount }}</span>
            <span>容量 {{ current.stats.totalCapacity }}</span>
            <span>已选 {{ current.stats.totalSelected }}</span>
            <span>填充率 {{ (current.stats.fillRate * 100).toFixed(0) }}%</span>
            <span>选课记录 {{ current.stats.recordCount }}</span>
          </div>
          <div class="aasar-export">
            <AppTextInput v-model="exportPurpose" placeholder="导出用途（≥5字，导出前必填）" />
            <AppButton size="small" variant="primary" :loading="exporting" @click="exportArchive">导出台账 Excel</AppButton>
          </div>
        </template>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 选课归档（/admin/academic-affairs/selection/archive）：ARCHIVED 批次历史查询 + 导出（12号卡）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTextInput } from '@/components/common'
import { academicAffairsApi, academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaSelectionArchiveView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppTextInput },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], termId: '',
      current: null, exportPurpose: '', exporting: false,
      columns: [
        { key: 'batchName', title: '批次名称' }, { key: 'termId', title: '学期ID' },
        { key: 'lockedAt', title: '锁定时间' }
      ]
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listArchivedBatches({ termId: this.termId || undefined, page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    async select(row) {
      this.current = null; this.exportPurpose = ''
      const res = await api.archiveDetail(row.batchId)
      if (res.code === 0) this.current = res.data
      else toast.error(res.message || '加载归档详情失败')
    },
    async exportArchive() {
      if (!this.current) return
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字'); return
      }
      this.exporting = true
      const res = await api.exportArchive(this.current.batchId, this.exportPurpose.trim())
      this.exporting = false
      if (res.code !== 0) { toast.error(res.message || '导出失败'); return }
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href; a.download = `选课归档-${this.current.batchName}-${Date.now()}.xlsx`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(href)
    }
  }
}
</script>

<style scoped>
.aasar-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; max-width: 420px; }
.aasar-layout { display: grid; grid-template-columns: 1fr 320px; gap: 16px; }
.aasar-detail-title { font-size: 16px; font-weight: 600; margin-bottom: 10px; }
.aasar-stats { display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aasar-export { display: flex; flex-direction: column; gap: 8px; }
</style>
