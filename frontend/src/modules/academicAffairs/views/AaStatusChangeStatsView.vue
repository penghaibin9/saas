<template>
  <ModulePageShell
    title="异动统计"
    subtitle="学籍异动按类型 / 状态 / 在途审批节点聚合（按当前身份数据范围过滤，与台账/审批口径一致）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="load">刷新</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <div class="aa-metric-grid">
        <AppMetricCard title="累计异动" :value="data.total" accent="primary" />
        <AppMetricCard title="在途待审" :value="data.pending" accent="warning" />
        <AppMetricCard title="已生效" :value="data.effective" accent="success" />
        <AppMetricCard title="已驳回" :value="data.rejected" accent="risk" />
      </div>

      <AppSectionCard title="按异动类型">
        <EmptyState v-if="!data.byType.length" title="暂无数据" />
        <template v-else>
          <AppG2Chart :spec="byTypeSpec" :height="260" />
          <table class="aa-table">
            <thead><tr><th>类型</th><th>数量</th></tr></thead>
            <tbody>
              <tr v-for="g in data.byType" :key="g.key">
                <td>{{ g.label }}</td>
                <td>{{ g.count }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </AppSectionCard>

      <AppSectionCard title="按当前状态">
        <EmptyState v-if="!data.byStatus.length" title="暂无数据" />
        <template v-else>
          <AppG2Chart :spec="byStatusSpec" :height="260" />
          <table class="aa-table">
            <thead><tr><th>状态</th><th>数量</th></tr></thead>
            <tbody>
              <tr v-for="g in data.byStatus" :key="g.key">
                <td><StatusTag :type="statusColor(g.key)" :label="statusLabel(g.key)" dot /></td>
                <td>{{ g.count }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </AppSectionCard>

      <AppSectionCard title="在途审批节点分布（待处理积压）">
        <EmptyState v-if="!data.pendingByNode.length" title="当前无在途异动" />
        <template v-else>
          <AppG2Chart :spec="pendingByNodeSpec" :height="260" />
          <table class="aa-table">
            <thead><tr><th>审批节点</th><th>待处理数</th></tr></thead>
            <tbody>
              <tr v-for="g in data.pendingByNode" :key="g.key">
                <td>{{ nodeLabel(g.key) }}</td>
                <td>{{ g.count }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学籍异动统计（Tier1「异动统计」，/admin/academic-affairs/status-changes/stats）。
 * 后端 GET /academic-affairs/status-changes/stats（academic_affairs_change_service.stats()），
 * 范围收敛与列表/审批同一套 _scope_conds（教务处全校 / 学院教务限本院 / 辅导员限本班）。
 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppMetricCard, AppG2Chart } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { STATUS_LABEL, NODE_LABEL, statusColor } from '@/modules/academicAffairs/constants/status-change'

export default {
  name: 'AaStatusChangeStatsView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppMetricCard, AppG2Chart },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '',
      data: { total: 0, pending: 0, effective: 0, rejected: 0, byType: [], byStatus: [], pendingByNode: [] }
    }
  },
  computed: {
    byTypeSpec() {
      return {
        type: 'interval',
        data: this.data.byType.map(g => ({ name: g.label, value: g.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    byStatusSpec() {
      return {
        type: 'interval',
        data: this.data.byStatus.map(g => ({ name: this.statusLabel(g.key), value: g.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    pendingByNodeSpec() {
      return {
        type: 'interval',
        data: this.data.pendingByNode.map(g => ({ name: this.nodeLabel(g.key), value: g.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusColor,
    nodeLabel(n) { return NODE_LABEL[n] || n || '未知节点' },
    async load() {
      this.loading = true; this.error = ''
      const res = await academicAffairsApi.getStatusChangeStats()
      if (res.code === 0) this.data = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.aa-stats { display: flex; gap: var(--space-3, 12px); flex-wrap: wrap; }
.aa-stat { display: flex; flex-direction: column; align-items: center; min-width: 96px; padding: 12px 18px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; }
.aa-stat b { font-size: 22px; color: var(--primary-600, #2563eb); }
.aa-stat span { font-size: 12px; color: var(--text-500, #646a73); margin-top: 4px; }
.aa-stat--success b { color: var(--success-600, #16a34a); }
.aa-stat--danger b { color: var(--danger-600, #dc2626); }
.aa-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.aa-table th, .aa-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); }
.aa-table th { color: var(--text-500, #646a73); font-weight: 500; }
</style>
