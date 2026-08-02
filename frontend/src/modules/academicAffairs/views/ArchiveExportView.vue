<template>
  <ModulePageShell
    title="教务归档 · 归档导出"
    subtitle="已归档批次水印物料下载 · 下载记录留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aaex-layout">
      <div class="aaex-list">
        <div class="aaex-list-title">已归档批次</div>
        <LoadingState v-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无已归档批次" description="批次确认归档后可在此下载物料" />
        <ul v-else class="aaex-items">
          <li v-for="b in rows" :key="b.batchId" :class="['aaex-item', { 'is-active': current && current.batchId === b.batchId }]" @click="select(b)">
            <span>{{ b.batchName }}</span>
            <span class="aaex-item-date">{{ fmt(b.archivedAt) }}</span>
          </li>
        </ul>
      </div>

      <div class="aaex-detail">
        <EmptyState v-if="!current" title="选择批次" description="从左侧选择已归档批次查看可下载物料" />
        <template v-else>
          <div class="aaex-head">
            <div class="aaex-title">{{ current.batchName }}</div>
            <AppButton size="small" variant="primary" :loading="packing" @click="openExport(null)">打包下载全部</AppButton>
          </div>

          <div class="aaex-section-title">物料清单（{{ items.length }} 域，仅列出有数据域）</div>
          <DataTable :columns="itemColumns" :rows="downloadableItems" row-key="domain">
            <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
            <template #cell-action="{ row }">
              <AppButton size="small" variant="ghost" @click="openExport(row.domain)">下载</AppButton>
            </template>
          </DataTable>

          <div class="aaex-section-title">下载记录</div>
          <LoadingState v-if="logLoading" />
          <EmptyState v-else-if="!downloadLog.length" title="暂无下载记录" description="尚未有人下载过本批次物料" />
          <DataTable v-else :columns="logColumns" :rows="downloadLog" row-key="downloadAt">
            <template #cell-downloadAt="{ row }">{{ fmt(row.downloadAt) }}</template>
          </DataTable>
        </template>
      </div>
    </div>

    <AppDrawer :visible="exportVisible" title="下载归档物料" mode="modal" size="small" @close="exportVisible = false">
      <div class="aaex-form">
        <AppFormItem label="下载用途" required>
          <AppTextInput v-model="exportPurpose" placeholder="如 上级检查留档核对（≥5字，写审计）" :disabled="exporting" />
        </AppFormItem>
        <AppInlineAlert type="warning" description="导出文件含学生姓名/学号等敏感字段，首行水印 + 审计留痕，请勿随意外发。" />
        <AppInlineAlert v-if="exportError" type="danger" :description="exportError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="exporting" @click="exportVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="exporting" @click="doExport">确认下载</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 教务归档 · 归档导出（12 卡，/admin/academic-affairs/archive/export）：
 * 已归档批次的水印 xlsx 单域下载 + zip 打包全量下载 + 下载记录查询。批次未 ARCHIVED 不出现在列表。 */
import { ModulePageShell, DataTable, LoadingState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppFormItem, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

function _download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default {
  name: 'ArchiveExportView',
  components: { ModulePageShell, DataTable, LoadingState, EmptyState, AppButton, AppDrawer, AppTextInput, AppFormItem, AppInlineAlert },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, rows: [], current: null, items: [],
      itemColumns: [{ key: 'domain', title: '数据域' }, { key: 'domainLabel', title: '名称' }, { key: 'recordCount', title: '记录数' }, { key: 'action', title: '操作' }],
      logLoading: false, downloadLog: [],
      logColumns: [{ key: 'operator', title: '下载人' }, { key: 'action', title: '类型' }, { key: 'detail', title: '说明' }, { key: 'downloadAt', title: '时间' }],
      exportVisible: false, exportPurpose: '', exportError: '', exporting: false, packing: false, pendingCategory: null
    }
  },
  computed: {
    downloadableItems() { return this.items.filter(i => i.present && i.recordCount > 0) }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
    async load() {
      this.loading = true
      const res = await api.listBatches({ status: 'ARCHIVED', pageSize: 100 })
      this.rows = res.code === 0 ? res.data.list : []
      this.loading = false
    },
    async select(b) {
      const res = await api.getBatch(b.batchId)
      if (res.code === 0) { this.current = res.data; this.items = res.data.items || [] }
      this.loadLog()
    },
    async loadLog() {
      if (!this.current) return
      this.logLoading = true
      const res = await api.downloadLog(this.current.batchId)
      this.downloadLog = res.code === 0 ? res.data : []
      this.logLoading = false
    },
    openExport(category) {
      this.pendingCategory = category
      this.exportPurpose = ''; this.exportError = ''; this.exportVisible = true
    },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) { this.exportError = '用途至少5字'; return }
      this.exporting = true
      const purpose = this.exportPurpose.trim()
      const res = this.pendingCategory
        ? await api.exportItem(this.current.batchId, this.pendingCategory, purpose)
        : await api.exportAll(this.current.batchId, purpose)
      this.exporting = false
      if (res.code === 0) {
        const filename = this.pendingCategory ? `${this.pendingCategory}_${this.current.batchName}.xlsx` : `${this.current.batchName}_归档物料.zip`
        _download(res.data, filename)
        toast.success('已下载'); this.exportVisible = false; this.loadLog()
      } else this.exportError = res.message
    }
  }
}
</script>

<style scoped>
.aaex-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.aaex-list-title { font-weight: 500; margin-bottom: 8px; }
.aaex-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaex-item { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaex-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaex-item-date { font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.aaex-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.aaex-title { font-size: 16px; font-weight: 600; }
.aaex-section-title { font-weight: 500; margin: 16px 0 8px; }
.aaex-form { display: flex; flex-direction: column; gap: 12px; }
</style>
