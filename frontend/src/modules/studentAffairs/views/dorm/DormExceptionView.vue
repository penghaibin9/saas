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
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="异常列表">
        <div class="sa-toolbar">
          <AppSelect v-model="filterStatus" class="sa-filter" :options="STATUS_OPTIONS" placeholder="" @change="load" />
        </div>
        <table class="sa-table">
          <thead><tr><th>类型</th><th>说明</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="x in items" :key="x.exceptionId">
              <td>{{ typeLabel(x.excType) }}</td>
              <td>{{ x.detail || '—' }}</td>
              <td><AppStatusTag :type="x.status === 'HANDLED' ? 'success' : 'warning'" :label="x.status === 'HANDLED' ? '已处置' : '待处置'" /></td>
              <td>{{ (x.createdAt || '').slice(0, 16) }}</td>
              <td class="sa-actions">
                <AppPermissionButton v-if="x.status !== 'HANDLED'" code="studentAffairs.dorm.exception.handle" size="sm" :loading="actioning" @click="handle(x)">处置</AppPermissionButton>
                <span v-else class="sa-muted">已闭环</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="5" class="sa-empty">当前范围内暂无宿舍异常</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 处置说明：原生 prompt 无法多行、无快捷用语；分组按本条异常类型置顶对应话术 -->
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
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'PENDING_HANDLE', label: '待处置' },
  { value: 'HANDLED', label: '已处置' }
]

export default {
  name: 'DormExceptionView',
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
    AppSelect, AppStatusTag
  },
  data() {
    return {
      STATUS_OPTIONS,
      loading: true, actioning: false, errorMessage: '', items: [], filterStatus: '',
      dlg: { visible: false, exceptionId: '', excType: '', detail: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = this.items.filter((x) => x.status !== 'HANDLED').length
      const night = this.items.filter((x) => (x.excType || '').includes('NIGHT')).length
      return [
        { key: 'p', label: '待处置', value: pending, accent: pending ? 'risk' : 'success' },
        { key: 'n', label: '夜不归宿', value: night, accent: night ? 'warning' : 'info' },
        { key: 't', label: '异常合计', value: this.items.length, accent: 'info' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try { this.items = (await studentAffairsApi.listDormExceptions({ status: this.filterStatus, pageSize: 100 })).data.items || [] }
      catch (e) { this.errorMessage = e.message || '异常加载失败' } finally { this.loading = false }
    },
    handle(x) {
      this.dlg = { visible: true, exceptionId: x.exceptionId, excType: x.excType || '', detail: x.detail || '' }
    },
    async submitHandle({ reason }) {
      this.actioning = true; this.errorMessage = ''
      try {
        await studentAffairsApi.handleDormException(this.dlg.exceptionId, reason.trim())
        await this.load()
        this.dlg.visible = false
      } catch (e) { this.errorMessage = e.message || '处置失败' } finally { this.actioning = false }
    },
    typeLabel(t) { return ({ HYGIENE: '卫生', SAFETY: '安全', CONTRABAND: '违禁品', NIGHT_ABSENCE: '夜不归宿', DORM_CHECK: '检查异常' })[t] || (t || '异常') }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-toolbar { margin-bottom: var(--space-4); }
.sa-toolbar select { min-width: 160px; border: 1px solid var(--border-base); border-radius: var(--radius-base); background: var(--bg-surface); padding: var(--space-2) var(--space-3); }
.sa-filter { width: 160px; }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-actions { display: flex; gap: var(--space-2); }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
