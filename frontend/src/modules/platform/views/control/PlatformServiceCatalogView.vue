<template>
  <ModulePageShell title="服务目录、依赖与租户影响地图" subtitle="P0服务 · 降级 · 无owner · 单点依赖 · SLO风险"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'bootstrap', label: '登记默认服务' }, { key: 'refresh', label: '刷新' }]"
                    @action="onToolbarAction" />
    </template>

    <LoadingState v-if="loading" text="正在加载服务目录…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else>
      <div class="psc__grid">
        <AppCard class="psc__stat"><div class="psc__stat-num">{{ overview.totalServices }}</div><div class="psc__stat-label">服务总数</div></AppCard>
        <AppCard class="psc__stat"><div class="psc__stat-num">{{ overview.p0Count }}</div><div class="psc__stat-label">P0 服务</div></AppCard>
        <AppCard class="psc__stat" :class="{ 'psc__stat--warn': overview.degradedCount }"><div class="psc__stat-num">{{ overview.degradedCount }}</div><div class="psc__stat-label">降级中</div></AppCard>
        <AppCard class="psc__stat" :class="{ 'psc__stat--warn': overview.noOwnerCount }"><div class="psc__stat-num">{{ overview.noOwnerCount }}</div><div class="psc__stat-label">无 owner</div></AppCard>
        <AppCard class="psc__stat" :class="{ 'psc__stat--warn': overview.singlePointCount }"><div class="psc__stat-num">{{ overview.singlePointCount }}</div><div class="psc__stat-label">单点依赖</div></AppCard>
      </div>

      <AppCard class="psc__panel">
        <AppSectionHeader title="近期事件" />
        <EmptyState v-if="!overview.recentIncidents || !overview.recentIncidents.length"
                   :text="overview.recentIncidentsNote || '暂无事件'" compact />
      </AppCard>

      <AppCard class="psc__panel">
        <AppSectionHeader title="服务目录" />
        <DataTable :columns="serviceColumns" :rows="services" row-key="serviceCode">
          <template #cell-scope="{ row }">
            <div class="psc__cell-main">{{ row.serviceName }}</div>
            <div class="psc__cell-sub">{{ row.serviceCode }} · {{ row.tier }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
            <StatusTag v-if="row.releaseBlocked" type="danger" label="发布阻断：缺owner/runbook" />
          </template>
          <template #cell-owner="{ row }">
            {{ row.ownerName || '（未指定）' }}
          </template>
          <template #cell-ops="{ row }">
            <button class="mp-link" @click="editService(row)">编辑</button>
            <button class="mp-link" @click="viewImpact(row)">故障影响面</button>
          </template>
        </DataTable>
      </AppCard>

      <AppCard class="psc__panel">
        <AppSectionHeader title="新增/编辑服务" />
        <div class="psc__form">
          <input v-model.trim="form.serviceCode" class="psc__input" placeholder="serviceCode，如 API_GATEWAY" :disabled="!!form._editing" />
          <input v-model.trim="form.serviceName" class="psc__input" placeholder="服务名称" />
          <select v-model="form.tier" class="psc__input">
            <option value="P0">P0</option><option value="P1">P1</option>
            <option value="P2">P2</option><option value="P3">P3</option>
          </select>
          <select v-model="form.status" class="psc__input">
            <option value="ACTIVE">ACTIVE</option><option value="DEGRADED">DEGRADED</option>
            <option value="DEPRECATED">DEPRECATED</option>
          </select>
          <input v-model.trim="form.ownerName" class="psc__input" placeholder="owner 姓名" />
          <input v-model.trim="form.runbookUrl" class="psc__input" placeholder="runbook URL" />
          <button class="mp-link" @click="saveService">保存</button>
        </div>
      </AppCard>

      <AppCard class="psc__panel">
        <AppSectionHeader title="服务依赖" />
        <div class="psc__form">
          <input v-model.trim="depForm.serviceCode" class="psc__input" placeholder="serviceCode（依赖方）" />
          <input v-model.trim="depForm.dependsOnServiceCode" class="psc__input" placeholder="dependsOnServiceCode（被依赖方）" />
          <button class="mp-link" @click="addDependency">新增依赖</button>
        </div>
        <DataTable :columns="depColumns" :rows="dependencies" row-key="id">
          <template #cell-scope="{ row }">{{ row.serviceCode }} → {{ row.dependsOnServiceCode }}（{{ row.dependencyType }}）</template>
          <template #cell-ops="{ row }"><button class="mp-link" @click="removeDependency(row)">删除</button></template>
        </DataTable>
      </AppCard>

      <AppCard v-if="impact" class="psc__panel">
        <AppSectionHeader :title="`故障影响面：${impact.serviceCode}`" />
        <ul class="psc__kv">
          <li><span>直接受影响租户</span><b>{{ impact.directTenants.join('、') || '无' }}</b></li>
          <li><span>间接受影响租户</span><b>{{ impact.indirectTenants.join('、') || '无' }}</b></li>
          <li><span>受影响服务</span><b>{{ impact.affectedServices.join('、') || '无' }}</b></li>
        </ul>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
import { AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformServiceCatalogView',
  components: { AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      services: [],
      dependencies: [],
      impact: null,
      form: { serviceCode: '', serviceName: '', tier: 'P2', status: 'ACTIVE', ownerName: '', runbookUrl: '', _editing: false, expectedVersion: null },
      depForm: { serviceCode: '', dependsOnServiceCode: '' },
      serviceColumns: [
        { key: 'scope', title: '服务' },
        { key: 'status', title: '状态' },
        { key: 'owner', title: 'Owner' },
        { key: 'ops', title: '操作' }
      ],
      depColumns: [
        { key: 'scope', title: '依赖边' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { ACTIVE: 'success', DEGRADED: 'warning', DEPRECATED: 'default' }[s] || 'default'
    },
    onToolbarAction(action) {
      if (action === 'bootstrap') return this.bootstrap()
      if (action === 'refresh') return this.load()
    },
    async bootstrap() {
      const res = await platformControlApi.bootstrapServiceCatalog()
      if (res.code === 0) { toast.success(`已登记 ${res.data.created} 个默认服务`); await this.load() }
      else toast.error(res.message)
    },
    editService(row) {
      this.form = {
        serviceCode: row.serviceCode, serviceName: row.serviceName, tier: row.tier,
        status: row.status, ownerName: row.ownerName || '', runbookUrl: row.runbookUrl || '',
        _editing: true, expectedVersion: row.version
      }
    },
    async saveService() {
      if (!this.form.serviceCode || !this.form.serviceName) return toast.error('serviceCode 与服务名称必填')
      const res = await platformControlApi.saveService({
        serviceCode: this.form.serviceCode, serviceName: this.form.serviceName, tier: this.form.tier,
        status: this.form.status, ownerName: this.form.ownerName, runbookUrl: this.form.runbookUrl,
        expectedVersion: this.form._editing ? this.form.expectedVersion : undefined
      })
      if (res.code === 0) {
        toast.success('已保存')
        this.form = { serviceCode: '', serviceName: '', tier: 'P2', status: 'ACTIVE', ownerName: '', runbookUrl: '', _editing: false, expectedVersion: null }
        await this.load()
      } else toast.error(res.message)
    },
    async addDependency() {
      if (!this.depForm.serviceCode || !this.depForm.dependsOnServiceCode) return toast.error('两个服务码都必填')
      const res = await platformControlApi.addServiceDependency({ ...this.depForm })
      if (res.code === 0) { toast.success('依赖已登记'); this.depForm = { serviceCode: '', dependsOnServiceCode: '' }; await this.load() }
      else toast.error(res.message)
    },
    async removeDependency(row) {
      const res = await platformControlApi.removeServiceDependency(row.id)
      if (res.code === 0) { toast.success('已删除'); await this.load() }
      else toast.error(res.message)
    },
    async viewImpact(row) {
      const res = await platformControlApi.getServiceImpact(row.serviceCode)
      if (res.code === 0) this.impact = res.data
      else toast.error(res.message)
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, services, deps] = await Promise.all([
        platformControlApi.getServiceCatalogOverview(),
        platformControlApi.listServices(),
        platformControlApi.listServiceDependencies()
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (services.code === 0) this.services = services.data.items || []
      else if (!this.error) this.error = services.message
      if (deps.code === 0) this.dependencies = deps.data.items || []
      this.loading = false
    }
  }
}
</script>

<style scoped>
.psc__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.psc__stat { padding: var(--space-4); }
.psc__stat--warn { border-color: var(--color-danger); }
.psc__stat-num { font-size: 26px; font-weight: var(--font-weight-bold); color: var(--t1); }
.psc__stat-label { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.psc__panel { padding: var(--space-4); margin-bottom: var(--space-3); }
.psc__cell-main { font-weight: var(--font-weight-medium); }
.psc__cell-sub { font-size: var(--font-size-xs); color: var(--text-secondary); }
.psc__form { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; margin-bottom: var(--space-3); }
.psc__input { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 160px; }
.psc__kv { list-style: none; padding: 0; margin: 0; }
.psc__kv li { display: flex; justify-content: space-between; padding: 4px 0; font-size: var(--font-size-sm); }
</style>
