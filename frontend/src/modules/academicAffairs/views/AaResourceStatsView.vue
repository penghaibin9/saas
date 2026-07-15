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
        <div class="aars-card">
          <div class="aars-value">{{ data.classroom.total }}</div>
          <div class="aars-label">教室总数</div>
          <div class="aars-sub">可用率 {{ pct(data.classroom.availableRate) }}</div>
        </div>
        <div class="aars-card">
          <div class="aars-value">{{ data.lab.total }}</div>
          <div class="aars-label">实训室总数</div>
          <div class="aars-sub">可用率 {{ pct(data.lab.availableRate) }}</div>
        </div>
        <div class="aars-card">
          <div class="aars-value">{{ data.equipment.total }}</div>
          <div class="aars-label">设备总数</div>
          <div class="aars-sub">在用率 {{ pct(data.equipment.inUseRate) }}</div>
        </div>
      </div>

      <div class="aars-section-title">预约审批</div>
      <div class="aars-grid">
        <div class="aars-card">
          <div class="aars-value">{{ data.classroomBooking.total }}</div>
          <div class="aars-label">教室预约总数</div>
          <div class="aars-sub">通过率 {{ pct(data.classroomBooking.approvalRate) }}</div>
        </div>
        <div class="aars-card">
          <div class="aars-value">{{ data.labBooking.total }}</div>
          <div class="aars-label">实训室预约总数</div>
          <div class="aars-sub">通过率 {{ pct(data.labBooking.approvalRate) }}</div>
        </div>
        <div class="aars-card">
          <div class="aars-value">{{ data.repair.openCount }}</div>
          <div class="aars-label">维修工单未结数</div>
          <div class="aars-sub">累计 {{ data.repair.total }} 单</div>
        </div>
      </div>

      <div class="aars-section-title">状态分布明细</div>
      <div class="aars-detail-grid">
        <div class="aars-detail-block">
          <div class="aars-detail-title">教室</div>
          <div v-for="(n, s) in data.classroom.byStatus" :key="s" class="aars-detail-row">
            <span>{{ statusLabel(s) }}</span><span>{{ n }}</span>
          </div>
        </div>
        <div class="aars-detail-block">
          <div class="aars-detail-title">实训室</div>
          <div v-for="(n, s) in data.lab.byStatus" :key="s" class="aars-detail-row">
            <span>{{ statusLabel(s) }}</span><span>{{ n }}</span>
          </div>
        </div>
        <div class="aars-detail-block">
          <div class="aars-detail-title">设备</div>
          <div v-for="(n, s) in data.equipment.byStatus" :key="s" class="aars-detail-row">
            <span>{{ equipStatusLabel(s) }}</span><span>{{ n }}</span>
          </div>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 资源统计（/admin/academic-affairs/resources/stats）：数量/状态分布/预约审批率/维修工单只读聚合。 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
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
  components: { ModulePageShell, LoadingState, ErrorState, AppButton },
  data() {
    return { loading: true, error: '', data: EMPTY() }
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
