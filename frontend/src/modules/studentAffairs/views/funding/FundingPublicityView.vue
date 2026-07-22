<template>
  <AppPageShell
    title="资助公示待办"
    subtitle="终审通过、进入公示期的资助申请。公示期满可扫描批量转「获资助」，或逐条人工确认。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="资助公示确认"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载公示名单..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.funding.publicity.manage" :loading="scanning" @click="scan">
          公示期满扫描
        </AppPermissionButton>
      </div>

      <AppSectionCard title="公示中的资助申请">
        <p class="fp-note">金额按当前角色脱敏由后端裁定；公示仅展示允许字段。</p>
        <DataTable v-if="items.length" :columns="publicityColumns" :rows="items" row-key="applicationId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-studentNo="{ row }">{{ row.studentNo || '—' }}</template>
          <template #cell-projectType="{ row }">{{ typeLabel(row.projectType) }}</template>
          <template #cell-amount="{ row }">{{ amountText(row.amount) }}</template>
          <template #cell-actions="{ row }">
            <AppPermissionButton code="studentAffairs.funding.publicity.manage" size="sm" variant="secondary"
                                 :loading="actingId === row.applicationId" @click="confirm(row)">
              确认公示期满 → 获资助
            </AppPermissionButton>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前无公示中的资助申请</p>
        <!-- 本页仅展示 status=PUBLICITY 的待办队列，属于随时清空的工作队列而非历史台账，
             规模受限于当前同时在公示期内的申请数，暂不引入 AppPagination。 -->
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const PUBLICITY_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'studentNo', title: '学号' },
  { key: 'projectType', title: '项目类型' },
  { key: 'amount', title: '金额' },
  { key: 'actions', title: '操作', align: 'right', width: '220px' }
]

export default {
  name: 'FundingPublicityView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, DataTable },
  data() { return { publicityColumns: PUBLICITY_COLUMNS, loading: true, scanning: false, actingId: '', errorMessage: '', items: [] } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const grant = this.items.filter((x) => x.projectType === 'GRANT').length
      const sch = this.items.filter((x) => x.projectType === 'SCHOLARSHIP').length
      return [
        { key: 'all', label: '公示中', value: this.items.length, accent: 'primary' },
        { key: 'sc', label: '奖学金', value: sch, accent: 'warning' },
        { key: 'gr', label: '助学金', value: grant, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getFundingApplications({ status: 'PUBLICITY', pageSize: 200 })
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
      } else {
        this.errorMessage = res.message || '公示名单加载失败'
      }
      this.loading = false
    },
    async scan() {
      this.scanning = true
      const res = await studentAffairsApi.scanFundingPublicity()
      if (res.code === 0) {
        const n = (res.data && res.data.count) || 0
        toast.success(n ? `公示期满 ${n} 条已转获资助` : '暂无到期公示')
        await this.load()
      } else {
        toast.error(res.message || '扫描失败')
      }
      this.scanning = false
    },
    async confirm(it) {
      this.actingId = it.applicationId
      const res = await studentAffairsApi.confirmFundingPublicity(it.applicationId)
      if (res.code === 0) {
        toast.success('已确认获资助')
        await this.load()
      } else {
        toast.error(res.message || '确认失败')
      }
      this.actingId = ''
    },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || t || '' },
    amountText(a) { return (a == null || a === '') ? '—' : (typeof a === 'number' ? ('¥' + a) : a) }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.fp-note { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@import '@/styles/module-page.css';
</style>
