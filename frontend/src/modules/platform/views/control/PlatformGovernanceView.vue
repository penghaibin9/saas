<template>
  <ModulePageShell title="数据治理、集成目录与合规证据" subtitle="跨租户主数据责任 · 集成登记 · 高危操作证据完整性"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <LoadingState v-if="loading" text="正在加载数据治理与合规证据…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="ov">
      <div class="pgv__grid">
        <AppCard class="pgv__stat"><div class="pgv__stat-num">{{ ov.tenantCount }}</div><div class="pgv__stat-label">在库租户</div></AppCard>
        <AppCard class="pgv__stat" :class="{ 'pgv__stat--warn': ov.dataGovernance.domainsWithoutOwnerTotal }">
          <div class="pgv__stat-num">{{ ov.dataGovernance.domainsWithoutOwnerTotal }}</div><div class="pgv__stat-label">主数据域无责任人（全平台）</div>
        </AppCard>
        <AppCard class="pgv__stat" :class="{ 'pgv__stat--warn': ov.dataGovernance.openIssuesTotal }">
          <div class="pgv__stat-num">{{ ov.dataGovernance.openIssuesTotal }}</div><div class="pgv__stat-label">数据质量问题未关闭</div>
        </AppCard>
        <AppCard class="pgv__stat"><div class="pgv__stat-num">{{ ov.integrationCatalog.registeredCount }}</div><div class="pgv__stat-label">已登记集成连接</div></AppCard>
        <AppCard class="pgv__stat" :class="{ 'pgv__stat--warn': ov.complianceEvidence.gapCount }">
          <div class="pgv__stat-num">{{ ov.complianceEvidence.gapCount }}</div><div class="pgv__stat-label">高危操作证据缺口</div>
        </AppCard>
      </div>

      <AppCard class="pgv__panel">
        <AppSectionHeader title="数据治理缺口最多的学校" />
        <EmptyState v-if="!ov.dataGovernance.tenantsWithGaps.length" text="暂无主数据治理缺口" compact />
        <DataTable v-else :columns="gapColumns" :rows="ov.dataGovernance.tenantsWithGaps" row-key="tenantId" />
      </AppCard>

      <AppCard class="pgv__panel">
        <AppSectionHeader title="合规证据缺口（高危操作 actor/tenant/object/reason/version/traceId 不全）" />
        <EmptyState v-if="!ov.complianceEvidence.gaps || !ov.complianceEvidence.gaps.length" text="近期高危操作证据完整" compact />
        <ul v-else class="pgv__list">
          <li v-for="g in ov.complianceEvidence.gaps" :key="g.auditId">
            <span class="pgv__list-name">{{ g.auditId }} · 缺 {{ (g.missing || []).join('、') }}</span>
          </li>
        </ul>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
/** PLAT-14 数据治理、集成目录与合规证据：跨租户只读聚合，纯只读页面。 */
import { AppCard, AppSectionHeader, DataTable } from '@/components/ui'
import { EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'

export default {
  name: 'PlatformGovernanceView',
  components: { AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar },
  data() {
    return {
      loading: true,
      error: '',
      ov: null,
      gapColumns: [
        { key: 'tenantName', title: '学校' },
        { key: 'domainsWithoutOwner', title: '无责任人域' },
        { key: 'openIssues', title: '未关闭问题' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformControlApi.getPlatformGovernanceOverview()
      this.loading = false
      if (res.code === 0) this.ov = res.data
      else this.error = res.message
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pgv__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}
.pgv__stat {
  padding: var(--space-4);
}
.pgv__stat--warn {
  border-color: var(--color-warning, #d97706);
}
.pgv__stat-num {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.pgv__stat-label {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pgv__panel {
  margin-top: var(--space-3);
  padding: var(--space-4);
}
.pgv__list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.pgv__list li {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pgv__list-name {
  color: var(--t2);
}
</style>
