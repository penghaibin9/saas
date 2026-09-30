<template>
  <ModulePageShell
    title="选课归档"
    subtitle="已锁定名单不能普通退课，归档批次只读并保留正式凭证"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/academic-affairs/selection')">查看锁定名单</AppButton>
    </template>

    <section v-if="current" class="aasar-context">
      <div><strong>{{ current.batchName }}</strong><p>选课归档批次 · {{ current.batchId }} · {{ current.termName || '正式学期以原批次为准' }}</p></div>
      <dl><div><dt>当前责任</dt><dd>选课管理岗</dd></div><div><dt>下一责任</dt><dd>归档查阅人</dd></div></dl>
    </section>

    <div class="aasar-notice"><strong>已封存事实只读；UNKNOWN 域会阻断新的封存</strong><span>原始名单不可修改；受控纠错必须建立新版本并保留操作凭证。</span></div>

    <div class="aasar-layout">
      <div class="aasar-list">
        <header class="aasar-list-head"><div><strong>选课归档批次 · 原记录与正式凭证</strong></div><div class="aasar-toolbar"><AppTermEntityPicker v-model="termId" placeholder="全部学期" /><AppButton size="small" variant="ghost" @click="applyFilter">查询</AppButton></div></header>
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无已归档批次" description="批次进入 LOCKED 状态后，在选课管理控制台点「归档」即可在此查询" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="batchId">
          <template #cell-batchName="{ row }">
            <button class="mp-link" @click="select(row)">{{ row.batchName }}</button>
          </template>
          <template #cell-term="{ row }">{{ row.termName || row.termId || '—' }}</template>
          <template #cell-lockedAt="{ row }">{{ row.lockedAt || '—' }}</template>
          <template #cell-count="{ row }">{{ row.studentCount ?? row.selectedCount ?? '—' }}</template>
          <template #cell-status><span class="aasar-status">已归档</span></template>
          <template #cell-ops="{ row }"><button class="mp-link" @click="select(row)">查看封存凭证</button></template>
        </DataTable>
        <AppPagination v-if="pagination.total" :total="pagination.total" :page="pagination.page" :page-size="pagination.pageSize" :show-size-changer="false" @change="onPage" />
      </div>

      <div v-if="current || detailLoading || detailError" class="aasar-detail">
        <ErrorState v-if="detailError" :description="detailError" @retry="reloadCurrent" />
        <LoadingState v-else-if="detailLoading" />
        <EmptyState v-else-if="!current" title="选择一个归档批次" description="查看容量/选课统计摘要并导出台账" />
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
import { AppPagination, AppTermEntityPicker, AppTextInput } from '@/components/common'
import { academicAffairsApi, academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { isDeniedResult } from '../components/parallel-a/resultState'
import { toast } from '@/utils/toast'

export default {
  name: 'AaSelectionArchiveView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppPagination, AppTermEntityPicker, AppTextInput },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      disposed: false, listSeq: 0, detailSeq: 0,
      loading: true, error: '', rows: [], termId: '', pagination: { page: 1, pageSize: 20, total: 0 },
      current: null, selectedBatchId: '', detailLoading: false, detailError: '', exportPurpose: '', exporting: false,
      columns: [
        { key: 'batchName', title: '批次' }, { key: 'term', title: '学期' },
        { key: 'lockedAt', title: '锁定日期' }, { key: 'count', title: '人数' },
        { key: 'status', title: '归档状态' }, { key: 'ops', title: '办理入口' }
      ]
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  beforeUnmount() { this.disposed = true; this.listSeq += 1; this.detailSeq += 1 },
  methods: {
    clearSensitive(message) {
      this.listSeq += 1; this.detailSeq += 1
      this.rows = []; this.pagination.total = 0; this.current = null; this.selectedBatchId = ''
      this.exportPurpose = ''; this.exporting = false; this.loading = false; this.detailLoading = false; this.detailError = ''
      this.error = message || '无权读取选课归档，已清除先前显示内容'
    },
    async load() {
      const seq = ++this.listSeq
      this.loading = true; this.error = ''
      const res = await api.listArchivedBatches({ termId: this.termId || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (this.disposed || seq !== this.listSeq) return
      if (res.code === 0) {
        this.rows = res.data.list; this.pagination.total = res.data.total
        if (this.selectedBatchId && !this.rows.some(row => String(row.batchId) === String(this.selectedBatchId))) {
          this.current = null; this.selectedBatchId = ''; this.exportPurpose = ''
        }
        if (!this.current && this.rows.length) this.select(this.rows[0])
      } else if (isDeniedResult(res)) return this.clearSensitive(res.message)
      else { this.rows = []; this.pagination.total = 0; this.error = res.message || '选课归档读取失败，请重试' }
      this.loading = false
    },
    applyFilter() { this.pagination.page = 1; this.current = null; this.selectedBatchId = ''; this.exportPurpose = ''; this.load() },
    onPage({ page }) { this.pagination.page = page; this.load() },
    async select(row) {
      const seq = ++this.detailSeq, batchId = row.batchId
      this.current = null; this.selectedBatchId = batchId; this.exportPurpose = ''; this.detailError = ''; this.detailLoading = true
      const res = await api.archiveDetail(row.batchId)
      if (this.disposed || seq !== this.detailSeq || String(batchId) !== String(this.selectedBatchId)) return
      this.detailLoading = false
      if (res.code === 0) this.current = res.data
      else if (isDeniedResult(res)) this.clearSensitive(res.message)
      else this.detailError = res.message || '归档详情读取失败，请重试'
    },
    reloadCurrent() {
      const row = this.rows.find(item => String(item.batchId) === String(this.selectedBatchId))
      if (row) this.select(row)
    },
    async exportArchive() {
      if (!this.current) return
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字'); return
      }
      this.exporting = true
      const res = await api.exportArchive(this.current.batchId, this.exportPurpose.trim())
      this.exporting = false
      if (isDeniedResult(res)) { this.clearSensitive(res.message); return }
      if (res.code !== 0) { this.detailError = res.message || '导出失败，请重试'; return }
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
.aasar-context { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:14px; padding:15px 16px; border:1px solid #dce6f3; border-left:3px solid #2f6fd2; border-radius:12px; background:#fff; }
.aasar-context strong { color:#173153; font-size:15px; }.aasar-context p { margin:4px 0 0; color:#6f7d90; font-size:12px; }
.aasar-context dl { display:flex; gap:28px; margin:0; }.aasar-context dl div { display:grid; gap:3px; }.aasar-context dt { color:#8692a3; font-size:11px; }.aasar-context dd { margin:0; color:#1f2937; font-size:12px; font-weight:700; }
.aasar-notice { display:grid; gap:3px; margin-bottom:14px; padding:13px 16px; border-radius:10px; background:#eaf2ff; color:#285b9b; font-size:12px; }.aasar-notice strong { font-size:12px; }
.aasar-toolbar { display: flex; gap: 8px; align-items: center; width:420px; max-width:100%; }
.aasar-layout { display: grid; gap: 14px; }
.aasar-list,.aasar-detail { overflow:hidden; border:1px solid #dfe7f1; border-radius:12px; background:#fff; }
.aasar-list-head { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:13px 16px; border-bottom:1px solid #e6edf5; color:#1e3556; font-size:13px; }
.aasar-list :deep(.data-table) { margin:0; }
.aasar-detail { padding:16px; }
.aasar-detail-title { font-size: 16px; font-weight: 600; margin-bottom: 10px; }
.aasar-stats { display: flex; flex-wrap:wrap; gap: 18px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aasar-export { display: grid; grid-template-columns:minmax(0,1fr) auto; gap: 8px; }
.aasar-status { display:inline-flex; padding:3px 7px; border-radius:5px; background:#f1f5f9; color:#64748b; font-size:11px; }
@media(max-width:760px){.aasar-context,.aasar-list-head{align-items:flex-start;flex-direction:column}.aasar-export{grid-template-columns:1fr}.aasar-context dl{gap:14px}}
</style>
