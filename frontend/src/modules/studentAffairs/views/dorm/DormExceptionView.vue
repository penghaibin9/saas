<template>
  <AppPageShell
    title="宿舍异常"
    subtitle="汇总检查/夜不归宿等宿舍异常，宿管逐条处置并留痕；涉事学生异常已联动风险处置。"
    role-name="宿管 / 辅导员 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍异常处置"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载宿舍异常..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <section class="sa-summary-strip dorm-exception-summary">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">异常处置重点</span>
          <h2 class="sa-summary-strip__title">优先处理待处置和夜不归宿等高风险异常，完成事实核查、处置说明和闭环留痕</h2>
          <p class="sa-summary-strip__text">当前范围异常合计 {{ statusCounts === null ? '—' : (statusCounts.ALL || 0) }} 条。异常记录来自宿舍检查等业务，处置时应说明核查结果、处理措施和后续安排。</p>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="宿舍异常处置流程">
        <div class="sa-workflow-step" data-step="1"><strong>识别异常</strong><br>查看类型、发生时间和原始说明</div>
        <div class="sa-workflow-step" data-step="2"><strong>核查事实</strong><br>联系学生、宿舍成员或值班人员</div>
        <div class="sa-workflow-step" data-step="3"><strong>记录处置</strong><br>填写处理措施和后续要求</div>
        <div class="sa-workflow-step" data-step="4"><strong>完成闭环</strong><br>异常转为已处置并保留审计</div>
      </div>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="异常列表与处置">
        <p class="dorm-exception-hint">默认按当前数据范围展示。切换到“待处置”集中处理未闭环记录；长异常说明会自动换行，不再挤压操作列。</p>
        <div v-if="statusFilterLabel" class="sa-student-filter">
          <span>{{ statusFilterLabel }}</span>
          <button type="button" class="mp-link" @click="clearStatusFilter">清除状态筛选</button>
        </div>
        <div class="sa-toolbar sa-filter-bar">
          <AppSelect v-model="filterStatus" class="sa-filter" :options="STATUS_OPTIONS" placeholder="" @change="onStatusChange" />
        </div>
        <DataTable v-if="items.length || pagination.total > 0" :columns="exceptionColumns" :rows="items" row-key="exceptionId"
                   :pagination="pagination" @page-change="onPageChange">
          <template #cell-type="{ row }"><strong>{{ typeLabel(row.excType) }}</strong></template>
          <template #cell-detail="{ row }"><span class="dorm-exception-detail sa-cell-wrap">{{ row.detail || '—' }}</span></template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'HANDLED' ? 'success' : 'warning'" :label="row.status === 'HANDLED' ? '已处置' : '待处置'" /></template>
          <template #cell-createdAt="{ row }"><span class="dorm-exception-time">{{ (row.createdAt || '').slice(0, 16) || '—' }}</span></template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.exception.handle')" v-if="row.status !== 'HANDLED'" code="studentAffairs.dorm.exception.handle" size="sm" :loading="actioning" @click="handle(row)">处置</AppPermissionButton>
            <span v-else class="sa-muted">已闭环</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前范围内暂无宿舍异常。可调整状态筛选，或返回宿舍检查页查看检查记录。</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="dlg.visible" :title="`处置宿舍异常 · ${typeLabel(dlg.excType)}`" type="primary"
      confirm-text="确认处置" require-reason :reason-min-length="5" reason-label="处置说明（≥5 字）"
      phrase-scene-key="sa.dorm.exception" :phrase-group="dlg.excType"
      :description="dlg.detail ? `原始异常：${dlg.detail}` : ''"
      :submitting="actioning" @confirm="submitHandle"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
  AppSelect, AppStatusTag
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { resolveTodoStatus } from '@/modules/studentAffairs/utils/todoFilterSemantics'

const EXCEPTION_COLUMNS = [
  { key: 'type', title: '类型' },
  { key: 'detail', title: '说明' },
  { key: 'status', title: '状态' },
  { key: 'createdAt', title: '时间' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'PENDING_HANDLE', label: '待处置' },
  { value: 'HANDLED', label: '已处置' }
]

export default {
  name: 'DormExceptionView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
    AppSelect, AppStatusTag, DataTable
  },
  data() {
    return {
      exceptionColumns: EXCEPTION_COLUMNS,
      STATUS_OPTIONS,
      loading: true, actioning: false, errorMessage: '', items: [], statusCounts: null, filterStatus: '',
      pagination: { page: 1, pageSize: 20, total: 0 },
      dlg: { visible: false, exceptionId: '', excType: '', detail: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    statusFilterLabel() {
      if (!this.filterStatus) return ''
      const hit = STATUS_OPTIONS.find((x) => x.value === this.filterStatus)
      return hit ? `当前状态筛选：${hit.label}` : `当前状态筛选：${this.filterStatus}`
    },
    metricCards() {
      return [
        { key: 'p', label: '待处置', value: '—', accent: 'risk' },
        { key: 'n', label: '夜不归宿', value: '—', accent: 'warning' },
        { key: 't', label: '异常合计', value: this.statusCounts === null ? '—' : (this.statusCounts.ALL || 0), accent: 'info' }
      ]
    }
  },
  mounted() {
    this.applyRouteFilters()
    this.load()
  },
  watch: {
    '$route.query'() { this.applyRouteFilters(); this.load() }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyRouteFilters() {
      const q = this.$route.query || {}
      if (!q.status) return
      const resolved = resolveTodoStatus('dormException', q.status)
      this.filterStatus = resolved.activeKey === 'HANDLED' ? 'HANDLED' : 'PENDING_HANDLE'
    },
    clearStatusFilter() {
      this.filterStatus = ''
      const q = { ...this.$route.query }
      delete q.status
      this.$router.replace({ query: q }).catch(() => {})
    },
    onStatusChange() {
      this.pagination.page = 1
      const q = { ...this.$route.query }
      if (!this.filterStatus) delete q.status
      else q.status = this.filterStatus
      this.$router.replace({ query: q }).catch(() => {})
      this.load()
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const status = this.filterStatus === 'PENDING_HANDLE' ? 'PENDING_HANDLE' : (this.filterStatus || undefined)
        const res = await studentAffairsApi.listDormExceptions({
          status, page: this.pagination.page, pageSize: this.pagination.pageSize
        })
        this.items = res.data.items || []
        this.pagination.total = res.data.total != null ? res.data.total : this.items.length
        this.statusCounts = res.data.statusCounts || null
      }
      catch (e) { this.errorMessage = e.message || '异常加载失败' } finally { this.loading = false }
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    handle(x) {
      this.dlg = {
        visible: true,
        exceptionId: x.exceptionId,
        version: x.version,
        excType: x.excType || '',
        detail: x.detail || ''
      }
    },
    async submitHandle({ reason }) {
      this.actioning = true; this.errorMessage = ''
      try {
        await studentAffairsApi.handleDormException(this.dlg.exceptionId, reason.trim(), this.dlg.version)
        await this.load()
        this.dlg.visible = false
      } catch (e) { this.errorMessage = e.message || '处置失败' } finally { this.actioning = false }
    },
    typeLabel(t) { return ({ HYGIENE: '卫生', SAFETY: '安全', CONTRABAND: '违禁品', NIGHT_ABSENCE: '夜不归宿', DORM_CHECK: '检查异常' })[t] || (t || '异常') }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.dorm-exception-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.sa-toolbar { margin-bottom: var(--space-3); }
.sa-filter { width: 180px; }
.sa-student-filter { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--warning-50, #fffbeb); border: 1px solid var(--warning-200, #fde68a); font-size: var(--font-size-sm); color: var(--text-primary); }
.dorm-exception-detail { color: var(--text-secondary); }
.dorm-exception-time { color: var(--text-tertiary); font-size: var(--font-size-xs); white-space: nowrap; }
.sa-muted { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
