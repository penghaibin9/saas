<template>
  <ModulePageShell title="公共底座运行中心" subtitle="跨租户文件底座容量/异常 · 服务目录健康 · 只读聚合"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <LoadingState v-if="loading" text="正在加载公共底座运行数据…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="overview">
      <div class="pfo__grid">
        <AppCard class="pfo__stat"><div class="pfo__stat-num">{{ overview.tenantCount }}</div><div class="pfo__stat-label">在库租户</div></AppCard>
        <AppCard class="pfo__stat"><div class="pfo__stat-num">{{ usedGiB }}</div><div class="pfo__stat-label">文件底座已用（GiB）</div></AppCard>
        <AppCard class="pfo__stat" :class="{ 'pfo__stat--warn': foundation.scanErrors }">
          <div class="pfo__stat-num">{{ foundation.scanErrors }}</div><div class="pfo__stat-label">病毒扫描失败</div>
        </AppCard>
        <AppCard class="pfo__stat" :class="{ 'pfo__stat--warn': foundation.expiredPendingCleanup }">
          <div class="pfo__stat-num">{{ foundation.expiredPendingCleanup }}</div><div class="pfo__stat-label">到期待清理</div>
        </AppCard>
        <AppCard class="pfo__stat" :class="{ 'pfo__stat--warn': overview.serviceCatalog.degradedCount }">
          <div class="pfo__stat-num">{{ overview.serviceCatalog.degradedCount || 0 }}</div><div class="pfo__stat-label">服务降级中</div>
        </AppCard>
      </div>

      <AppCard class="pfo__panel">
        <AppSectionHeader title="运行风险" />
        <EmptyState v-if="!overview.risks.length" text="当前无跨租户运行风险" compact />
        <ul v-else class="pfo__list">
          <li v-for="(r, i) in overview.risks" :key="i">
            <span class="pfo__list-name">{{ r.text }}</span>
            <StatusTag :type="r.level === 'HIGH' ? 'danger' : 'warning'" :label="r.sourceCard" />
          </li>
        </ul>
      </AppCard>

      <AppCard class="pfo__panel">
        <AppSectionHeader title="需要关注的学校（按异常分数排序）" />
        <EmptyState v-if="!overview.tenantsNeedingAttention.length" text="暂无需要关注的学校" compact />
        <DataTable v-else :columns="attentionColumns" :rows="overview.tenantsNeedingAttention" row-key="tenantId" />
      </AppCard>

      <AppCard class="pfo__panel">
        <AppSectionHeader title="文件底座明细（全平台求和）" />
        <ul class="pfo__kv">
          <li><span>隔离区滞留超1小时</span><b>{{ foundation.quarantineOverOneHour }}</b></li>
          <li><span>对象存储未完成生产校验</span><b>{{ foundation.cosUnverified }}</b></li>
          <li><span>24小时无业务引用</span><b>{{ foundation.unboundOver24Hours }}</b></li>
          <li><span>法律保留中文件</span><b>{{ foundation.legalHoldFiles }}</b></li>
          <li><span>扫描积压</span><b>{{ foundation.scanBacklog }}</b></li>
          <li><span>文件后台任务失败</span><b>{{ foundation.failedFileJobs }}</b></li>
          <li><span>配额预占（有效 / 已过期未释放）</span><b>{{ foundation.heldReservations }} / {{ foundation.expiredHeldReservations }}</b></li>
        </ul>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
/** PLAT-06 公共底座运行中心：跨租户聚合 PR#25 文件底座 + PLAT-08 服务目录，纯只读。 */
import { AppCard, AppSectionHeader, DataTable } from '@/components/ui'
import { EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'

export default {
  name: 'PlatformFoundationOpsView',
  components: { AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      overview: null,
      attentionColumns: [
        { key: 'tenantName', title: '学校' },
        { key: 'anomalyScore', title: '异常分数' }
      ]
    }
  },
  computed: {
    foundation() {
      return (this.overview && this.overview.fileFoundation) || {}
    },
    usedGiB() {
      const bytes = this.foundation.totalBytes || 0
      return (bytes / 1024 / 1024 / 1024).toFixed(2)
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformControlApi.getFoundationOverview()
      this.loading = false
      if (res.code === 0) this.overview = res.data
      else this.error = res.message
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pfo__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}
.pfo__stat {
  padding: var(--space-4);
}
.pfo__stat--warn {
  border-color: var(--color-warning, #d97706);
}
.pfo__stat-num {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.pfo__stat-label {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pfo__panel {
  margin-top: var(--space-3);
  padding: var(--space-4);
}
.pfo__list, .pfo__kv {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.pfo__list li, .pfo__kv li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pfo__kv b {
  color: var(--t1);
}
.pfo__list-name {
  color: var(--t2);
}
</style>
