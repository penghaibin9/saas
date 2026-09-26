<template>
  <ModulePageShell
    title="迎新统计"
    subtitle="当前迎新批次办理进度，按您的职责范围统计"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="迎新统计"
  >
    <template #actions>
      <AppButton v-if="canExport" variant="secondary" :disabled="loading || !!error || !data.batchId" :loading="exporting" @click="openExport">导出迎新台账</AppButton>
    </template>
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <template v-else>
        <div class="ost-head">
          <span class="ost-head__name">{{ data.batchName }}</span>
          <span class="ost-head__period">{{ data.batchPeriod }}</span>
          <span class="ost-head__time">更新于 {{ formatDateTime(data.updateTime) }}</span>
        </div>

        <!-- KPI 卡片 -->
        <div class="ost-kpis">
          <div v-for="k in data.kpis" :key="k.key" class="ost-kpi" :class="'ost-kpi--' + (k.trendQuality || 'neutral')">
            <div class="ost-kpi__label">{{ k.label }}</div>
            <div class="ost-kpi__value">{{ k.value }}</div>
            <div v-if="k.trend" class="ost-kpi__trend">{{ k.trend }}</div>
          </div>
        </div>

        <!-- 环节漏斗 -->
        <section class="ost-card">
          <div class="ost-card__title">报到环节完成漏斗</div>
          <div v-if="!data.stepFunnel.length" class="ost-empty">暂无环节数据</div>
          <div v-for="s in data.stepFunnel" v-else :key="s.key" class="ost-funnel">
            <span class="ost-funnel__label">{{ s.label }}</span>
            <div class="ost-funnel__bar">
              <div class="ost-funnel__fill" :style="{ width: barWidth(s.done) + '%' }" />
            </div>
            <span class="ost-funnel__num">{{ s.done }}</span>
          </div>
        </section>

        <!-- 待办 -->
        <section class="ost-card">
          <div class="ost-card__title">待办概览</div>
          <div class="ost-todos">
            <button v-for="t in data.todos" :key="t.id" type="button" class="ost-todo" @click="go(t.link)">
              <span class="ost-todo__label">{{ t.label }}</span>
              <span class="ost-todo__value">{{ t.value }}</span>
            </button>
          </div>
        </section>
      </template>
    </template>

    <AppDrawer :visible="exportVisible" title="导出当前批次台账" mode="modal" size="medium" @close="closeExport">
      <div class="ost-export-form">
        <p>只导出当前迎新批次与当前角色学生范围，文件带操作人、用途、时间水印并写入审计。</p>
        <AppSelect v-if="!exportResult" v-model="reportListKey" :options="REPORT_TYPES" :disabled="exporting" />
        <AppTextInput v-if="!exportResult" v-model="exportPurpose" :disabled="exporting" placeholder="导出用途（不少于5字）" />
        <p v-if="exportError" role="alert">{{ exportError }}</p>
        <p v-if="exportResult">已生成 {{ exportResult.fileName }}，共 {{ exportResult.rowCount }} 行。若下载中断，可重新下载同一文件。</p>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="exporting" @click="closeExport">{{ exportResult ? '完成' : '取消' }}</AppButton>
        <AppButton v-if="exportResult" variant="primary" @click="downloadExport">重新下载此文件</AppButton>
        <AppButton v-else variant="primary" :disabled="exportPurpose.trim().length < 5 || !canExport || !data.batchId" :loading="exporting" @click="exportReport">生成并下载</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/statistics 迎新统计（KPI + 环节漏斗 + 待办；真实走 /orientation/dashboard）。 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppSelect, AppTextInput } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { orientationDestination } from '@/modules/orientation/routeContext'
import { formatDateTime } from '@/utils/dateUtils'

const REPORT_TYPES = [
  { value: 'studentList', label: '迎新新生台账.xlsx' },
  { value: 'progressList', label: '报到进度.xlsx' },
  { value: 'materialList', label: '材料审核.xlsx' },
  { value: 'paymentList', label: '缴费状态.xlsx' },
  { value: 'greenChannelList', label: '绿色通道.xlsx' },
  { value: 'dormList', label: '住宿安排.xlsx' },
  { value: 'checkinList', label: '现场报到.xlsx' },
  { value: 'noShowList', label: '未报到.xlsx' },
  { value: 'exceptionList', label: '迎新异常.xlsx' }
]

export default {
  name: 'OrientationStatsView',
  components: { AppButton, AppDrawer, AppSelect, AppTextInput, ModulePageShell, LoadingState, ErrorState, NoPermissionState },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      data: { batchId: '', batchName: '', batchPeriod: '', updateTime: '', kpis: [], stepFunnel: [], todos: [] },
      REPORT_TYPES, exportVisible: false, exporting: false,
      reportListKey: 'studentList', exportPurpose: '', exportError: '', exportResult: null, loadSerial: 0, actionSerial: 0
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    canExport() { return !!this.perms['orientation.student.export']?.allowed },
    maxDone() { return Math.max(1, ...this.data.stepFunnel.map((s) => s.done || 0)) }
  },
  async created() {
    const ctx = await api.getOrientationContext()
    if (ctx.code === 0) this.ctx = ctx.data
    await this.load()
  },
  beforeUnmount() { this.loadSerial++; this.actionSerial++ },
  methods: {
    formatDateTime,
    async load() {
      const serial = ++this.loadSerial
      this.loading = true; this.error = ''
      this.data = { batchId: '', batchName: '', batchPeriod: '', updateTime: '', kpis: [], stepFunnel: [], todos: [] }
      try {
        const res = await api.getOrientationDashboard({ batchId: this.$route.query.batchId || undefined })
        if (serial !== this.loadSerial) return
        if (res.code === 0) {
          this.data = {
            batchId: res.data.batchId || '',
            batchName: res.data.batchName || '',
            batchPeriod: res.data.batchPeriod || '',
            updateTime: res.data.updateTime || '',
            kpis: res.data.kpis || [],
            stepFunnel: res.data.stepFunnel || [],
            todos: res.data.todos || []
          }
        } else this.error = res.message || '统计读取失败，请重试'
      } catch (e) { if (serial === this.loadSerial) this.error = e.message || '加载失败' }
      finally { if (serial === this.loadSerial) this.loading = false }
    },
    openExport() {
      if (!this.canExport || this.loading || this.error || !this.data.batchId || this.exporting) return
      this.exportResult = null; this.exportError = ''; this.exportPurpose = ''; this.exportVisible = true
    },
    closeExport() { if (!this.exporting) this.exportVisible = false },
    downloadExport() { if (this.exportResult) downloadXlsxFromApi(this.exportResult) },
    async exportReport() {
      if (this.exporting || this.exportResult || !this.canExport || !this.data.batchId || this.loading || this.error || this.exportPurpose.trim().length < 5) return
      const serial = this.actionSerial
      this.exporting = true; this.exportError = ''
      try {
        const res = await api.createExport(this.reportListKey, {
          auditConfirmed: true, purpose: this.exportPurpose.trim(), batchId: this.data.batchId
        })
        if (serial !== this.actionSerial) return
        if (res.code === 0) {
          this.exportResult = res.data
          downloadXlsxFromApi(res.data)
        } else this.exportError = res.message || '导出失败，请重试'
      } catch (error) { if (serial === this.actionSerial) this.exportError = error.message || '导出失败，请重试' }
      finally { if (serial === this.actionSerial) this.exporting = false }
    },
    barWidth(done) { return Math.round(((done || 0) / this.maxDone) * 100) },
    go(link) { if (link) this.$router.push(orientationDestination(link, { path: this.$route.path, query: { ...this.$route.query, batchId: this.data.batchId } })) }
  }
}
</script>

<style scoped>
.ost-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.ost-head__name {
  font-size: 16px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.ost-head__period {
  font-size: 13px;
  color: var(--t2);
}
.ost-head__time {
  font-size: 12px;
  color: var(--t3);
  margin-left: auto;
}
.ost-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.ost-kpi {
  padding: 14px 16px;
  border: 1px solid var(--card-b);
  border-radius: 12px;
  background: var(--card);
}
.ost-kpi__label {
  font-size: 12.5px;
  color: var(--t3);
}
.ost-kpi__value {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
  margin: 4px 0;
  font-variant-numeric: tabular-nums;
}
.ost-kpi__trend {
  font-size: 11.5px;
  color: var(--t2);
}
.ost-kpi--good .ost-kpi__value {
  color: #16a34a;
}
.ost-kpi--bad .ost-kpi__value {
  color: #dc2626;
}
.ost-card {
  border: 1px solid var(--card-b);
  border-radius: 12px;
  background: var(--card);
  padding: 16px;
  margin-bottom: 16px;
}
.ost-card__title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--t1);
  margin-bottom: 12px;
}
.ost-funnel {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 9px;
}
.ost-funnel__label {
  width: 92px;
  flex-shrink: 0;
  font-size: 12.5px;
  color: var(--t2);
}
.ost-funnel__bar {
  flex: 1;
  height: 14px;
  border-radius: 7px;
  background: var(--pri-bg);
  overflow: hidden;
}
.ost-funnel__fill {
  height: 100%;
  border-radius: 7px;
  background: var(--btn-p-bg);
  transition: width 0.3s ease;
}
.ost-funnel__num {
  width: 44px;
  text-align: right;
  font-size: 12.5px;
  color: var(--t1);
  font-variant-numeric: tabular-nums;
}
.ost-todos {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.ost-todo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid var(--card-b);
  border-radius: 10px;
  background: var(--bg-card);
  cursor: pointer;
  font-family: inherit;
}
.ost-todo:hover {
  border-color: var(--glow);
}
.ost-todo__label {
  font-size: 13px;
  color: var(--t2);
}
.ost-todo__value {
  font-size: 15px;
  font-weight: var(--font-weight-bold);
  color: var(--pri);
}
.ost-empty {
  font-size: 12.5px;
  color: var(--t3);
}
.ost-export-form { display: grid; gap: 12px; }
.ost-export-form p { margin: 0; color: var(--t2); font-size: 13px; line-height: 1.6; }
</style>
