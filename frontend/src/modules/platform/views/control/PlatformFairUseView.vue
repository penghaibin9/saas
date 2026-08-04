<template>
  <ModulePageShell title="租户用量、容量、成本与公平使用" subtitle="用量最高学校 · 超配额学校 · 保护共享核心服务"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <LoadingState v-if="loading" text="正在加载用量数据…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="ov">
      <div class="pfu__grid">
        <AppCard class="pfu__stat"><div class="pfu__stat-num">{{ ov.usage.tenantsWithSnapshot }}</div><div class="pfu__stat-label">已有用量快照的学校</div></AppCard>
        <AppCard class="pfu__stat" :class="{ 'pfu__stat--warn': ov.fairUse.tenantsOverLimitToday }">
          <div class="pfu__stat-num">{{ ov.fairUse.tenantsOverLimitToday }}</div><div class="pfu__stat-label">今日超公平使用配额</div>
        </AppCard>
        <AppCard class="pfu__stat" :class="{ 'pfu__stat--warn': ov.fairUse.chronicOffenders.length }">
          <div class="pfu__stat-num">{{ ov.fairUse.chronicOffenders.length }}</div><div class="pfu__stat-label">近7天连续超限</div>
        </AppCard>
      </div>

      <AppCard class="pfu__panel">
        <AppSectionHeader title="存储用量最高的学校" />
        <EmptyState v-if="!ov.usage.topByStorage.length" text="暂无用量快照，先为学校生成快照" compact />
        <ul v-else class="pfu__list">
          <li v-for="s in ov.usage.topByStorage" :key="s.id">
            租户 {{ s.tenantId }} · {{ (s.storageTotalBytes / 1024 / 1024 / 1024).toFixed(2) }} GiB
          </li>
        </ul>
      </AppCard>

      <AppCard class="pfu__panel">
        <AppSectionHeader title="连续超限学校" />
        <EmptyState v-if="!ov.fairUse.chronicOffenders.length" text="暂无连续超限学校" compact />
        <ul v-else class="pfu__list">
          <li v-for="o in ov.fairUse.chronicOffenders" :key="o.tenantId">
            租户 {{ o.tenantId }} · 近7天超限 {{ o.violationDaysLast7 }} 天
          </li>
        </ul>
      </AppCard>

      <AppCard class="pfu__panel">
        <AppSectionHeader title="单校用量快照与公平使用评估" />
        <div class="pfu__form">
          <input v-model.trim="targetTenantId" class="pfu__input" placeholder="租户ID" />
          <button class="mp-link" @click="captureSnapshot">生成今日快照</button>
          <button class="mp-link" @click="evaluateFairUse">评估公平使用</button>
        </div>
        <p v-if="evalResult" class="pfu__note">
          {{ evalResult.withinLimits ? '未超出配额' : `超出配额：${evalResult.violations.map(v => v.resourceCode).join('、')}` }}
        </p>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
/** PLAT-13 租户用量、容量、成本与公平使用：跨租户用量排行 + 单校快照/评估操作。 */
import { AppCard, AppSectionHeader } from '@/components/ui'
import { EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformFairUseView',
  components: { AppCard, AppSectionHeader, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar },
  data() {
    return { loading: true, error: '', ov: null, targetTenantId: '', evalResult: null }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformControlApi.getFairUseOverview()
      this.loading = false
      if (res.code === 0) this.ov = res.data
      else this.error = res.message
    },
    async captureSnapshot() {
      if (!this.targetTenantId) {
        toast.error('请填写租户ID')
        return
      }
      const res = await platformControlApi.captureTenantUsageSnapshot(this.targetTenantId)
      if (res.code === 0) { toast.success('快照已生成'); this.load() } else toast.error(res.message)
    },
    async evaluateFairUse() {
      if (!this.targetTenantId) {
        toast.error('请填写租户ID')
        return
      }
      const res = await platformControlApi.evaluateTenantFairUse(this.targetTenantId)
      if (res.code === 0) { this.evalResult = res.data; this.load() } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pfu__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}
.pfu__stat {
  padding: var(--space-4);
}
.pfu__stat--warn {
  border-color: var(--color-warning, #d97706);
}
.pfu__stat-num {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.pfu__stat-label {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pfu__panel {
  margin-top: var(--space-3);
  padding: var(--space-4);
}
.pfu__list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pfu__form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.pfu__input {
  padding: 6px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm, 4px);
  font-size: var(--font-size-sm);
}
.pfu__note {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--t2);
}
</style>
