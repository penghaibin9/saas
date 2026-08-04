<template>
  <ModulePageShell title="客户健康、工单、培训与续费" subtitle="健康分实时判定 · 工单 · 培训 · 续费跟进"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <LoadingState v-if="loading" text="正在加载客户成功数据…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="ov">
      <div class="pcs__grid">
        <AppCard class="pcs__stat"><div class="pcs__stat-num">{{ ov.tenantCount }}</div><div class="pcs__stat-label">在库租户</div></AppCard>
        <AppCard class="pcs__stat" :class="{ 'pcs__stat--warn': ov.healthDistribution.CRITICAL }">
          <div class="pcs__stat-num">{{ ov.healthDistribution.CRITICAL }}</div><div class="pcs__stat-label">健康分 CRITICAL</div>
        </AppCard>
        <AppCard class="pcs__stat" :class="{ 'pcs__stat--warn': ov.healthDistribution.AT_RISK }">
          <div class="pcs__stat-num">{{ ov.healthDistribution.AT_RISK }}</div><div class="pcs__stat-label">健康分 AT_RISK</div>
        </AppCard>
        <AppCard class="pcs__stat"><div class="pcs__stat-num">{{ ov.openTicketsTotal }}</div><div class="pcs__stat-label">未关闭工单</div></AppCard>
        <AppCard class="pcs__stat"><div class="pcs__stat-num">{{ ov.upcomingRenewals }}</div><div class="pcs__stat-label">待跟进续费</div></AppCard>
      </div>

      <AppCard class="pcs__panel">
        <AppSectionHeader title="健康分 CRITICAL 的学校" />
        <EmptyState v-if="!ov.criticalTenants.length" text="当前无 CRITICAL 学校" compact />
        <ul v-else class="pcs__list">
          <li v-for="t in ov.criticalTenants" :key="t.tenantId">
            <span class="pcs__list-name">{{ t.tenantName }}</span>
            <span class="pcs__list-sub">{{ (t.reasons || []).join('；') }}</span>
          </li>
        </ul>
      </AppCard>

      <AppCard class="pcs__panel">
        <AppSectionHeader title="创建工单" />
        <div class="pcs__form">
          <input v-model.trim="ticketForm.tenantId" class="pcs__input" placeholder="租户ID" />
          <input v-model.trim="ticketForm.title" class="pcs__input" placeholder="工单标题" />
          <select v-model="ticketForm.severity" class="pcs__input">
            <option value="P0">P0</option><option value="P1">P1</option>
            <option value="P2">P2</option><option value="P3">P3</option>
          </select>
          <input v-model.trim="ticketForm.reporterName" class="pcs__input" placeholder="反馈人" />
          <button class="mp-link" @click="createTicket">创建工单</button>
        </div>
      </AppCard>

      <AppCard class="pcs__panel">
        <AppSectionHeader title="工单列表" />
        <DataTable :columns="ticketColumns" :rows="tickets" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'OPEN' ? 'danger' : (row.status === 'IN_PROGRESS' ? 'warning' : 'success')" :label="row.status" />
          </template>
          <template #cell-ops="{ row }">
            <button v-if="row.status !== 'CLOSED'" class="mp-link" @click="transitionTicket(row, 'IN_PROGRESS')">处理中</button>
            <button v-if="row.status !== 'CLOSED'" class="mp-link" @click="transitionTicket(row, 'RESOLVED')">已解决</button>
            <button v-if="row.status === 'RESOLVED'" class="mp-link" @click="transitionTicket(row, 'CLOSED')">关闭</button>
          </template>
        </DataTable>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
/** PLAT-05 客户健康、工单、培训与续费：健康分只读展示 + 工单闭环操作。 */
import { AppCard, AppSectionHeader, DataTable } from '@/components/ui'
import { EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformCustomerSuccessView',
  components: { AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      ov: null,
      tickets: [],
      ticketForm: { tenantId: '', title: '', severity: 'P2', reporterName: '' },
      ticketColumns: [
        { key: 'title', title: '标题' },
        { key: 'severity', title: '优先级' },
        { key: 'status', title: '状态' },
        { key: 'reporterName', title: '反馈人' },
        { key: 'ops', title: '操作' }
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
      const [ovRes, ticketsRes] = await Promise.all([
        platformControlApi.getCustomerSuccessOverview(),
        platformControlApi.listSupportTickets()
      ])
      this.loading = false
      if (ovRes.code === 0) this.ov = ovRes.data
      else this.error = ovRes.message
      if (ticketsRes.code === 0) this.tickets = ticketsRes.data.items || []
    },
    async createTicket() {
      if (!this.ticketForm.tenantId || !this.ticketForm.title) {
        toast.error('请填写租户ID和标题')
        return
      }
      const res = await platformControlApi.createSupportTicket({
        tenantId: this.ticketForm.tenantId,
        title: this.ticketForm.title,
        severity: this.ticketForm.severity,
        reporterName: this.ticketForm.reporterName
      })
      if (res.code === 0) {
        toast.success('工单已创建')
        this.ticketForm = { tenantId: '', title: '', severity: 'P2', reporterName: '' }
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async transitionTicket(row, status) {
      const res = await platformControlApi.transitionSupportTicket(row.id, {
        status, expectedVersion: row.version
      })
      if (res.code === 0) {
        toast.success('工单状态已更新')
        this.load()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pcs__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}
.pcs__stat {
  padding: var(--space-4);
}
.pcs__stat--warn {
  border-color: var(--color-warning, #d97706);
}
.pcs__stat-num {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.pcs__stat-label {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pcs__panel {
  margin-top: var(--space-3);
  padding: var(--space-4);
}
.pcs__list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.pcs__list li {
  display: flex;
  flex-direction: column;
  font-size: var(--font-size-sm);
}
.pcs__list-name {
  color: var(--t1);
  font-weight: var(--font-weight-bold);
}
.pcs__list-sub {
  color: var(--text-secondary);
  font-size: 12px;
}
.pcs__form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.pcs__input {
  padding: 6px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm, 4px);
  font-size: var(--font-size-sm);
}
</style>
