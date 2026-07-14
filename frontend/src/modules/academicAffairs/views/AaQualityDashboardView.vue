<template>
  <ModulePageShell
    title="教学质量 · 运行质量看板"
    subtitle="实时聚合既有教务数据的质量指标 · 教务运行质量报告导出"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openExport">导出质量报告</AppButton>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else>
      <div class="aaql-grid">
        <div v-for="i in indicators" :key="i.key" class="aaql-card">
          <div class="aaql-value">{{ i.value }}<span class="aaql-unit">{{ i.unit }}</span></div>
          <div class="aaql-label">{{ i.label }}</div>
          <div v-if="i.numerator != null" class="aaql-sub">{{ i.numerator }} / {{ i.denominator }}</div>
        </div>
      </div>

      <div class="aaql-section-title">质量报告导出历史</div>
      <EmptyState v-if="!reports.length" title="暂无导出记录" description="点击右上角「导出质量报告」生成" />
      <DataTable v-else :columns="reportColumns" :rows="reports" row-key="exportId">
        <template #cell-occurredAt="{ row }">{{ fmt(row.occurredAt) }}</template>
      </DataTable>
    </template>

    <AppDrawer :visible="exportVisible" title="导出教务运行质量报告" @close="exportVisible = false">
      <div class="aaql-form">
        <AppFormItem label="导出用途" required>
          <AppTextInput v-model="exportPurpose" placeholder="如 期末教学质量分析（≥5字，写审计）" :disabled="exporting" />
        </AppFormItem>
        <AppInlineAlert type="info" description="报告含挂科率/预警/发布率/毕业通过率等质量指标，导出带水印+审计。" />
        <AppInlineAlert v-if="exportError" type="danger" :description="exportError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="exporting" @click="exportVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="exporting" @click="doExport">导出 xlsx</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 教学质量 · 运行质量看板（/admin/academic-affairs/quality）：质量指标聚合 + 报告导出。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppFormItem, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsQualityApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaQualityDashboardView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppTextInput, AppFormItem, AppInlineAlert },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', indicators: [], reports: [],
      reportColumns: [{ key: 'operator', title: '导出人' }, { key: 'roleName', title: '角色' }, { key: 'detail', title: '用途' }, { key: 'occurredAt', title: '时间' }],
      exportVisible: false, exportPurpose: '', exportError: '', exporting: false
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
    async load() {
      this.loading = true; this.error = ''
      const [d, r] = await Promise.all([api.dashboard(), api.reports({ pageSize: 50 })])
      if (d.code === 0) this.indicators = d.data.indicators
      else this.error = d.message
      this.reports = r.code === 0 ? r.data.list : []
      this.loading = false
    },
    openExport() { this.exportPurpose = ''; this.exportError = ''; this.exportVisible = true },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) { this.exportError = '用途至少5字'; return }
      this.exporting = true
      const res = await api.exportReport({ purpose: this.exportPurpose.trim() })
      this.exporting = false
      if (res.code === 0) {
        const url = URL.createObjectURL(res.data)
        const a = document.createElement('a'); a.href = url; a.download = 'academic_quality_report.xlsx'; a.click()
        URL.revokeObjectURL(url)
        toast.success('已导出'); this.exportVisible = false; this.load()
      } else this.exportError = res.message
    }
  }
}
</script>

<style scoped>
.aaql-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.aaql-card { padding: 16px; background: var(--fill-light, #f8fafc); border-radius: 10px; }
.aaql-value { font-size: 26px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aaql-unit { font-size: 14px; margin-left: 2px; color: var(--text-secondary, #64748b); }
.aaql-label { margin-top: 4px; font-size: 13px; color: var(--text-secondary, #64748b); }
.aaql-sub { margin-top: 2px; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.aaql-section-title { font-weight: 500; margin: 8px 0 12px; }
.aaql-form { display: flex; flex-direction: column; gap: 12px; }
</style>
