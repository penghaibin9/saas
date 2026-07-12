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
          <select v-model="filterStatus" @change="load">
            <option value="">全部状态</option>
            <option value="PENDING_HANDLE">待处置</option>
            <option value="HANDLED">已处置</option>
          </select>
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
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'DormExceptionView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag },
  data() { return { loading: true, actioning: false, errorMessage: '', items: [], filterStatus: '' } },
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
    async handle(x) {
      const reason = window.prompt('处置说明（不少于 5 字）', '')
      if (!reason || reason.trim().length < 5) { if (reason !== null) window.alert('说明不少于 5 字'); return }
      this.actioning = true
      try { await studentAffairsApi.handleDormException(x.exceptionId, reason.trim()); await this.load() }
      catch (e) { this.errorMessage = e.message || '处置失败' } finally { this.actioning = false }
    },
    typeLabel(t) { return ({ HYGIENE: '卫生', SAFETY: '安全', CONTRABAND: '违禁品', NIGHT_ABSENCE: '夜不归宿', DORM_CHECK: '检查异常' })[t] || (t || '异常') }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-toolbar { margin-bottom: var(--space-4); }
.sa-toolbar select { min-width: 160px; border: 1px solid var(--border-base); border-radius: var(--radius-base); background: var(--bg-surface); padding: var(--space-2) var(--space-3); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-actions { display: flex; gap: var(--space-2); }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
