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
        <DataTable v-if="items.length" :columns="publicityColumns" :rows="items" row-key="applyId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-studentNo="{ row }">{{ row.studentNo || '—' }}</template>
          <template #cell-level="{ row }"><StatusTag type="processing" :label="levelLabel(row.finalLevel || row.applyLevel)" dot /></template>
          <template #cell-objection="{ row }">
            <StatusTag v-if="row.hasPendingObjection" type="warning" label="异议待复核" dot />
            <span v-else>—</span>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton v-if="!row.hasPendingObjection" code="studentAffairs.aid.approve" size="sm" variant="secondary"
                                 :loading="actingId === row.applyId" @click="confirm(row)">
              确认公示期满 → 通过
            </AppPermissionButton>
            <span v-else class="ap-blocked">请先完成异议复核</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前无公示中的认定申请</p>
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                       :total="pagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const LEVELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const PUBLICITY_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'studentNo', title: '学号' },
  { key: 'level', title: '拟认定等级' },
  { key: 'objection', title: '异议' },
  { key: 'actions', title: '操作', align: 'right', width: '200px' }
]

export default {
  name: 'AidPublicityView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  data() {
    return {
      publicityColumns: PUBLICITY_COLUMNS,
      loading: true, scanning: false, actingId: '', errorMessage: '', items: [], statsItems: [],
      pagination: { page: 1, pageSize: 20, total: 0 }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const byLevel = this.statsItems.reduce((m, x) => { const k = x.finalLevel || x.applyLevel; m[k] = (m[k] || 0) + 1; return m }, {})
      return [
        { key: 'all', label: '公示中', value: this.pagination.total, accent: 'primary' },
        { key: 'sp', label: '特别困难', value: byLevel.SPECIAL || 0, accent: 'risk' },
        { key: 'df', label: '困难', value: byLevel.DIFFICULT || 0, accent: 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [pageRes, statsRes] = await Promise.all([
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', page: this.pagination.page, pageSize: this.pagination.pageSize }),
        // 独立于当前分页的全量口径（上限 200），仅用于按等级统计卡
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', pageSize: 200 })
      ])
      if (pageRes.code === 0 && pageRes.data) {
        this.items = pageRes.data.items || []
        this.pagination.total = pageRes.data.total != null ? pageRes.data.total : this.items.length
      } else {
        this.errorMessage = pageRes.message || '公示名单加载失败'
      }
      this.statsItems = (statsRes.code === 0 && statsRes.data) ? (statsRes.data.items || []) : []
      this.loading = false
    },
    async scan() {
      this.scanning = true
      const res = await studentAffairsApi.scanAidPublicity()
      if (res.code === 0) {
        const n = (res.data && res.data.count) || 0
        toast.success(n ? `公示期满 ${n} 条已转通过` : '暂无到期公示')
        this.pagination.page = 1
        await this.load()
      } else {
        toast.error(res.message || '扫描失败')
      }
      this.scanning = false
    },
    async confirm(it) {
      this.actingId = it.applyId
      const res = await studentAffairsApi.confirmAidPublicity(it.applyId)
      if (res.code === 0) {
        toast.success('已确认通过，进入困难库')
        this.pagination.page = 1
        await this.load()
      } else {
        toast.error(res.message || '确认失败')
      }
      this.actingId = ''
    },
    levelLabel(l) { return LEVELS[l] || l || '—' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.ap-note { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }
.ap-blocked { color: var(--color-warning, #b45309); font-size: var(--font-size-sm); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@import '@/styles/module-page.css';
</style>
