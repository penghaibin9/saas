<template>
  <AppPageShell
    title="困难认定公示待办"
    subtitle="学校终审通过、进入公示期的认定申请。公示期满可扫描批量转通过，或逐条人工确认。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="困难认定公示确认"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载公示名单..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.aid.approve" :loading="scanning" @click="scan">
          公示期满扫描
        </AppPermissionButton>
      </div>

      <AppSectionCard title="公示中的认定申请">
        <p class="ap-note">公示信息仅展示允许字段（姓名 / 学号 / 拟认定等级）；家庭经济明细在公示页不呈现。</p>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>学号</th><th>拟认定等级</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="it in items" :key="it.applyId">
              <td><strong>{{ it.realName || ('学生#' + it.studentId) }}</strong></td>
              <td>{{ it.studentNo || '—' }}</td>
              <td><StatusTag type="processing" :label="levelLabel(it.finalLevel || it.applyLevel)" dot /></td>
              <td>
                <AppPermissionButton code="studentAffairs.aid.approve" size="sm" variant="secondary"
                                     :loading="actingId === it.applyId" @click="confirm(it)">
                  确认公示期满 → 通过
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="4" class="sa-empty">当前无公示中的认定申请</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const LEVELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }

export default {
  name: 'AidPublicityView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag },
  data() { return { loading: true, scanning: false, actingId: '', errorMessage: '', items: [] } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const byLevel = this.items.reduce((m, x) => { const k = x.finalLevel || x.applyLevel; m[k] = (m[k] || 0) + 1; return m }, {})
      return [
        { key: 'all', label: '公示中', value: this.items.length, accent: 'primary' },
        { key: 'sp', label: '特别困难', value: byLevel.SPECIAL || 0, accent: 'risk' },
        { key: 'df', label: '困难', value: byLevel.DIFFICULT || 0, accent: 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getAidApplications({ status: 'PUBLICITY', pageSize: 200 })
        this.items = (res.data && res.data.items) || []
      } catch (e) {
        this.errorMessage = e.message || '公示名单加载失败'
      } finally {
        this.loading = false
      }
    },
    async scan() {
      this.scanning = true
      try {
        const res = await studentAffairsApi.scanAidPublicity()
        const n = (res.data && res.data.count) || 0
        toast.success(n ? `公示期满 ${n} 条已转通过` : '暂无到期公示')
        await this.load()
      } catch (e) {
        toast.error(e.message || '扫描失败')
      } finally {
        this.scanning = false
      }
    },
    async confirm(it) {
      this.actingId = it.applyId
      try {
        await studentAffairsApi.confirmAidPublicity(it.applyId)
        toast.success('已确认通过，进入困难库')
        await this.load()
      } catch (e) {
        toast.error(e.message || '确认失败')
      } finally {
        this.actingId = ''
      }
    },
    levelLabel(l) { return LEVELS[l] || l || '—' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.ap-note { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
