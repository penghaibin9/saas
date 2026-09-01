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

      <section class="presence-provider" :class="{ 'is-disabled': !provider.configured }">
        <div><span>门禁 Provider</span><strong>{{ provider.providerLabel || '未配置' }}</strong></div>
        <div><span>最后同步</span><strong>{{ provider.lastSyncAt ? provider.lastSyncAt.slice(0, 16).replace('T', ' ') : '—' }}</strong></div>
        <div><span>健康状态</span><strong>{{ provider.healthStatus || 'DISABLED' }}</strong></div>
        <p>{{ provider.notice || '未接入归寝数据' }}。UNKNOWN 表示缺少可靠事实，不等同于未归。</p>
      </section>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="今日归寝状态">
        <p class="dorm-exception-hint">仅依据批准请假和已标准化的 Provider 事件研判；无数据时保持“未知”，不会生成“未归”结论。</p>
        <DataTable v-if="presenceItems.length" :columns="presenceColumns" :rows="presenceItems" row-key="studentId">
          <template #cell-student="{ row }"><strong>{{ row.studentName }}</strong><br><span class="sa-muted">{{ row.studentNo }}</span></template>
          <template #cell-room="{ row }">{{ row.buildingName }} · {{ row.roomNo }}室 · {{ row.bedNo }}床</template>
          <template #cell-presenceStatus="{ row }"><AppStatusTag :type="presenceTone(row.status)" :label="row.statusLabel" /></template>
          <template #cell-lastEventAt="{ row }">{{ row.lastEventAt ? row.lastEventAt.slice(0, 16).replace('T', ' ') : '—' }}</template>
        </DataTable>
        <p v-else class="sa-empty">当前范围暂无在住学生。</p>
      </AppSectionCard>
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
          <template #cell-relatedRisk="{ row }">
            <button v-if="row.relatedRisk?.riskId" type="button" class="dorm-risk-link" @click="goRisk(row)">{{ row.relatedRisk.riskLevel }} · {{ row.relatedRisk.statusLabel || row.relatedRisk.status }}<span v-if="row.relatedRisk.ownerName"> · {{ row.relatedRisk.ownerName }}</span> →</button>
            <span v-else class="sa-muted">未生成风险</span>
          </template>
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
  { key: 'relatedRisk', title: '关联风险', width: '220px' },
  { key: 'status', title: '状态' },
  { key: 'createdAt', title: '时间' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'PENDING_HANDLE', label: '待处置' },
  { value: 'HANDLED', label: '已处置' }
]
const PRESENCE_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'room', title: '床位' },
  { key: 'presenceStatus', title: '归寝状态' },
  { key: 'lastEventAt', title: '最近可靠事件' }
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
      presenceColumns: PRESENCE_COLUMNS,
      STATUS_OPTIONS,
      loading: true, actioning: false, errorMessage: '', items: [], statusCounts: null, filterStatus: '',
      provider: { providerLabel: '未配置', healthStatus: 'DISABLED', configured: false },
      presenceItems: [], presenceCounts: {},
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
        { key: 'p', label: '归寝未知', value: this.presenceCounts.UNKNOWN ?? '—', accent: 'warning' },
        { key: 'n', label: '确认未归', value: this.presenceCounts.NOT_RETURNED ?? '—', accent: 'warning' },
        { key: 't', label: '异常待处置', value: this.statusCounts === null ? '—' : (this.statusCounts.PENDING_HANDLE || 0), accent: 'risk' }
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
        const [res, providerRes, presenceRes] = await Promise.all([
          studentAffairsApi.listDormExceptions({ status, page: this.pagination.page, pageSize: this.pagination.pageSize }),
          studentAffairsApi.getDormPresenceProvider(),
          studentAffairsApi.listDormPresence({ page: 1, pageSize: 50 })
        ])
        this.items = res.data.items || []
        this.pagination.total = res.data.total != null ? res.data.total : this.items.length
        this.statusCounts = res.data.statusCounts || null
        this.provider = providerRes.data || this.provider
        this.presenceItems = presenceRes.data.items || []
        this.presenceCounts = presenceRes.data.statusCounts || {}
      }
      catch (e) { this.errorMessage = e.message || '异常加载失败' } finally { this.loading = false }
    },
    presenceTone(status) { return ({ IN_DORM: 'success', ON_LEAVE: 'info', LATE_RETURN: 'warning', NOT_RETURNED: 'danger', OUT: 'default', UNKNOWN: 'default' })[status] || 'default' },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    goRisk(row) {
      const riskId = row.relatedRisk?.riskId
      if (!riskId) return
      this.$router.push({ name: 'student-affairs-risk-detail', params: { riskId: String(riskId) }, query: { studentId: String(row.studentId || ''), from: 'dorm-exception', exceptionId: String(row.exceptionId || '') } })
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
.dorm-risk-link { border: 0; background: transparent; padding: 0; color: var(--primary-600); font: inherit; font-size: var(--font-size-xs); cursor: pointer; text-align: left; }
.dorm-risk-link:hover { text-decoration: underline; }
.dorm-exception-detail { color: var(--text-secondary); }
.dorm-exception-time { color: var(--text-tertiary); font-size: var(--font-size-xs); white-space: nowrap; }
.sa-muted { color: var(--text-tertiary); }
.presence-provider { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-3);margin-bottom:var(--space-4);padding:var(--space-4);border:1px solid var(--primary-200,#bfdbfe);border-radius:var(--radius-lg);background:var(--primary-50,#eff6ff) }
.presence-provider.is-disabled { border-color:var(--border-color);background:var(--surface-subtle,#f8fafc) }
.presence-provider div span { display:block;color:var(--text-tertiary);font-size:var(--font-size-xs);margin-bottom:4px }.presence-provider div strong { color:var(--text-primary) }.presence-provider p { grid-column:1/-1;margin:0;color:var(--text-secondary);font-size:var(--font-size-sm) }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
