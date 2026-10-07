<template>
  <ModulePageShell title="资源统计" subtitle="教室 / 实训室 / 设备数量与状态分布 · 预约审批率 · 维修工单（只读聚合）">
    <template #actions>
      <AppButton variant="ghost" @click="load">刷新</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="data" class="aars-wrap">
      <div class="aars-scope">
        <div><span>统计范围</span><strong>{{ ctx.dataScope?.scopeName || '当前授权范围' }}</strong></div>
        <div><span>统计口径</span><strong>当前资源目录与正式预约、维修工单聚合</strong></div>
        <div><span>下一步</span><strong>下钻到占用与维修台账核对对象</strong></div>
      </div>
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
          <div class="aars-detail-title"><span>教室</span><button class="mp-link" type="button" @click="drill('/admin/academic-affairs/classrooms')">查看目录</button></div>
          <AppDescriptionList :items="classroomDescItems" :columns="1" size="compact" />
        </div>
        <div class="aars-detail-block">
          <div class="aars-detail-title"><span>实训室</span><button class="mp-link" type="button" @click="drill('/admin/academic-affairs/resources/labs')">查看目录</button></div>
          <AppDescriptionList :items="labDescItems" :columns="1" size="compact" />
        </div>
        <div class="aars-detail-block">
          <div class="aars-detail-title"><span>设备</span><button class="mp-link" type="button" @click="drill('/admin/academic-affairs/resources/equipment')">查看目录</button></div>
          <AppDescriptionList :items="equipmentDescItems" :columns="1" size="compact" />
        </div>
      </div>
      <div class="aars-actions">
        <AppButton variant="primary" @click="drill('/admin/academic-affairs/resources/occupancy')">下钻资源占用</AppButton>
        <AppButton variant="ghost" @click="drill('/admin/academic-affairs/resources/repairs')">核对未结维修</AppButton>
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

export default {
  name: 'AaResourceStatsView',
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppMetricCard, AppDescriptionList },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', data: null, revision: 0, disposed: false }
  },
  computed: {
    classroomDescItems() {
      return Object.entries(this.data?.classroom?.byStatus || {}).map(([s, n]) => ({ label: this.statusLabel(s), value: n }))
    },
    labDescItems() {
      return Object.entries(this.data?.lab?.byStatus || {}).map(([s, n]) => ({ label: this.statusLabel(s), value: n }))
    },
    equipmentDescItems() {
      return Object.entries(this.data?.equipment?.byStatus || {}).map(([s, n]) => ({ label: this.equipStatusLabel(s), value: n }))
    }
  },
  created() { this.load() },
  watch: { ctx() { this.load() } },
  beforeUnmount() { this.disposed = true; this.revision++ },
  methods: {
    statusLabel(s) { return _STATUS_LABEL[s] || '状态待确认' },
    equipStatusLabel(s) { return _EQUIP_STATUS_LABEL[s] || '设备状态待确认' },
    pct(v) { return v == null ? '—' : `${v}%` },
    drill(path) { this.$router.push(path) },
    async load() {
      const revision = ++this.revision, context = this.ctx
      const current = () => !this.disposed && revision === this.revision && context === this.ctx
      this.loading = true; this.error = ''; this.data = null
      try {
        const res = await academicAffairsResourceApi.stats(); if (!current()) return
        if (res.code !== 0) throw res
        if (!['classroom', 'lab', 'equipment', 'classroomBooking', 'labBooking', 'repair'].every(key => Number.isFinite(res.data?.[key]?.total))) throw new Error('资源统计口径未完整返回，请重新读取。')
        this.data = res.data
      } catch (e) { if (current()) this.error = e?.message || '统计读取失败，请重试。' }
      finally { if (current()) this.loading = false }
    }
  }
}
</script>

<style scoped>
.aars-wrap { display: grid; gap: 16px; }
.aars-scope { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aars-scope > div { padding: 12px 14px; border: 1px solid var(--border-base, #e2e8f0); border-radius: 10px; background: var(--surface-card, #fff); }
.aars-scope span, .aars-scope strong { display: block; }
.aars-scope span { color: var(--text-tertiary, #94a3b8); font-size: 12px; }
.aars-scope strong { margin-top: 4px; color: var(--text-primary, #0f172a); font-size: 14px; }
.aars-section-title { font-weight: 500; margin: 8px 0 12px; }
.aars-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.aars-card { padding: 16px; background: var(--fill-light, #f8fafc); border-radius: 10px; }
.aars-value { font-size: 26px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aars-label { margin-top: 4px; font-size: 13px; color: var(--text-secondary, #64748b); }
.aars-sub { margin-top: 2px; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.aars-detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.aars-detail-block { padding: 12px 16px; border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; }
.aars-detail-title { display: flex; justify-content: space-between; gap: 8px; font-weight: 500; margin-bottom: 8px; }
.aars-detail-row { display: flex; justify-content: space-between; font-size: 13px; color: var(--text-secondary, #64748b); padding: 2px 0; }
.aars-actions { display: flex; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
@media (max-width: 760px) { .aars-scope { grid-template-columns: 1fr; } }
</style>
