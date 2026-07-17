<template>
  <ModulePageShell title="资源统计" subtitle="教室 / 实训室 / 设备数量与状态分布 · 预约审批率 · 维修工单（只读聚合）">
    <template #actions>
      <AppButton variant="ghost" @click="load">刷新</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="aars-wrap">
      <div class="aars-section-title">资源数量与可用率</div>
      <div class="aars-grid">
        <AppMetricCard title="教室总数" :value="data.classroom.total" :trend-label="`可用率 ${pct(data.classroom.availableRate)}`" />
        <AppMetricCard title="实训室总数" :value="data.lab.total" :trend-label="`可用率 ${pct(data.lab.availableRate)}`" />
        <AppMetricCard title="设备总数" :value="data.equipment.total" :trend-label="`在用率 ${pct(data.equipment.inUseRate)}`" />
      </div>

      <div class="aars-section-title">预约审批</div>
      <div class="aars-grid">
        <AppMetricCard title="教室预约总数" :value="data.classroomBooking.total" :trend-label="`通过率 ${pct(data.classroomBooking.approvalRate)}`" />
        <AppMetricCard title="实训室预约总数" :value="data.labBooking.total" :trend-label="`通过率 ${pct(data.labBooking.approvalRate)}`" />
        <AppMetricCard title="维修工单未结数" :value="data.repair.openCount" accent="warning" :trend-label="`累计 ${data.repair.total} 单`" />
      </div>

      <div class="aars-section-title">状态分布明细</div>
      <div class="aars-detail-grid">
        <div class="aars-detail-block">
          <div class="aars-detail-title">教室</div>
          <AppDescriptionList :items="classroomDescItems" :columns="1" size="compact" />
        </div>
        <div class="aars-detail-block">
          <div class="aars-detail-title">实训室</div>
          <AppDescriptionList :items="labDescItems" :columns="1" size="compact" />
        </div>
        <div class="aars-detail-block">
          <div class="aars-detail-title">设备</div>
          <AppDescriptionList :items="equipmentDescItems" :columns="1" size="compact" />
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 资源统计（/admin/academic-affairs/resources/stats）：数量/状态分布/预约审批率/维修工单只读聚合。 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppDescriptionList } from '@/components/common'
import { academicAffairsResourceApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const _STATUS_LABEL = { AVAILABLE: '可用', DISABLED: '停用', MAINTENANCE: '维修中',
                        PENDING: '待审', APPROVED: '已通过', REJECTED: '已驳回', CANCELLED: '已取消' }
const _EQUIP_STATUS_LABEL = { IN_USE: '在用', IDLE: '闲置', MAINTENANCE: '维修中', SCRAPPED: '已报废' }

const EMPTY = () => ({
  classroom: { total: 0, byStatus: {}, availableRate: null },
  lab: { total: 0, byStatus: {}, availableRate: null },
  equipment: { total: 0, byStatus: {}, inUseRate: null },
  classroomBooking: { total: 0, byStatus: {}, approvalRate: null },
  labBooking: { total: 0, byStatus: {}, approvalRate: null },
  repair: { total: 0, byStatus: {}, openCount: 0 }
})

export default {
  name: 'AaResourceStatsView',
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppMetricCard, AppDescriptionList },
  data() {
    return { loading: true, error: '', data: EMPTY() }
  },
  computed: {
    classroomDescItems() {
      return Object.entries(this.data.classroom.byStatus || {}).map(([s, n]) => ({ label: this.statusLabel(s), value: n }))
    },
    labDescItems() {
      return Object.entries(this.data.lab.byStatus || {}).map(([s, n]) => ({ label: this.statusLabel(s), value: n }))
    },
    equipmentDescItems() {
      return Object.entries(this.data.equipment.byStatus || {}).map(([s, n]) => ({ label: this.equipStatusLabel(s), value: n }))
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return _STATUS_LABEL[s] || s },
    equipStatusLabel(s) { return _EQUIP_STATUS_LABEL[s] || s },
    pct(v) { return v == null ? '—' : `${v}%` },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsResourceApi.stats()
      if (res.code === 0) {
        this.data = res.data
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
.aars-section-title { font-weight: 500; margin: 8px 0 12px; }
.aars-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.aars-card { padding: 16px; background: var(--fill-light, #f8fafc); border-radius: 10px; }
.aars-value { font-size: 26px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aars-label { margin-top: 4px; font-size: 13px; color: var(--text-secondary, #64748b); }
.aars-sub { margin-top: 2px; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.aars-detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.aars-detail-block { padding: 12px 16px; border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; }
.aars-detail-title { font-weight: 500; margin-bottom: 8px; }
.aars-detail-row { display: flex; justify-content: space-between; font-size: 13px; color: var(--text-secondary, #64748b); padding: 2px 0; }
</style>
