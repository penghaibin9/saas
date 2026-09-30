<template>
  <ModulePageShell class="platform-workspace pct" title="学校清单" subtitle="找到学校，核对状态，进入下一步办理" :role-name="roleName" data-scope-name="已授权的平台学校范围">
    <template #actions>
      <AppButton v-if="can('platform.provision.run.view')" variant="primary" @click="goProvisioning">开通新学校</AppButton>
    </template>
    <PlatformMetricStrip :items="schoolMetrics" />
    <section class="pct__workspace" aria-label="学校管理工作区">
      <div class="pct__list-head"><div><h2>学校工作区</h2><p>按服务状态找到学校，进入详情继续办理</p></div><div class="pct__density" aria-label="表格显示密度"><button type="button" :aria-pressed="density === 'comfortable'" @click="density = 'comfortable'">舒适</button><button type="button" :aria-pressed="density === 'compact'" @click="density = 'compact'">紧凑</button></div></div>
      <div v-if="pickerHint" class="pct__hint">{{ pickerHint }}</div>
      <div class="pct__status-tabs" aria-label="按生命周期筛选">
        <button v-for="item in statusOptions" :key="item.value" type="button" :class="{ 'is-active': applied.status === item.value }" :aria-pressed="applied.status === item.value" @click="selectStatus(item.value)">{{ item.label }}</button>
      </div>
      <form class="pct__toolbar" role="search" @submit.prevent="search">
        <label class="pct__search"><span class="pct__sr-only">学校名称或编码</span><input v-model="keyword" maxlength="100" class="pct__input" placeholder="搜索学校名称 / 编码" /></label>
        <button type="submit" class="pct__query">查询</button>
        <AppButton v-if="applied.keyword || applied.status" variant="ghost" @click="clearFilters">清除筛选</AppButton>
        <button type="button" class="pct__refresh" :disabled="loading" @click="load">{{ loading ? '读取中…' : '刷新' }}</button>
      </form>
      <div class="pct__result-bar" role="status" aria-live="polite">
        <span v-if="loading">正在读取学校清单</span>
        <span v-else-if="error">本次读取失败，未展示旧结果</span>
        <span v-else><strong>{{ rows.length }}</strong> 所{{ applied.keyword || applied.status ? '符合条件的' : '' }}学校<span v-if="applied.keyword"> · 搜索“{{ applied.keyword }}”</span></span>
        <span v-if="loadedAt && !loading && !error" class="pct__read-time">本次读取 {{ loadedAt }}</span>
      </div>
      <LoadingState v-if="loading" text="正在加载学校清单…" />
      <ErrorState v-else-if="error" :description="error" @retry="load" @back="$router.push('/admin/platform/overview')" />
      <div v-else-if="!rows.length" class="pct__empty">
        <EmptyState title="没有符合条件的学校" :description="applied.keyword || applied.status ? '可以调整学校名称、编码或生命周期筛选，已有学校不会因筛选被删除。' : '当前已授权范围尚无学校记录。开通完成后，学校会出现在这里。'">
          <template #actions>
            <button v-if="applied.keyword || applied.status" type="button" class="pw-button pw-button--primary" @click="clearFilters">清除筛选，查看学校清单</button>
            <button v-else-if="can('platform.provision.run.view')" type="button" class="pw-button pw-button--primary" @click="goProvisioning">开通学校</button>
            <span v-else class="pw-empty-note">学校开通由具备交付权限的人员办理。</span>
          </template>
        </EmptyState>
      </div>
      <template v-else>
        <p id="pct-table-help" class="pw-scroll-hint">左右滚动可查看容量、授权与办理入口；键盘可聚焦表格后按方向键浏览。</p>
        <div aria-describedby="pct-table-help" class="pct__table-region" :class="{ 'pct__table-region--compact': density === 'compact' }" tabindex="0" role="region" aria-label="学校清单，可横向滚动">
          <DataTable :columns="columns" :rows="visibleRows" row-key="tenantId" :row-class="rowTone">
            <template #cell-tenantName="{ row }">
              <div class="pct__identity"><span class="pct__avatar" :data-status="row.status" aria-hidden="true">{{ (row.tenantName || '校').slice(0, 1) }}</span><div class="pct__identity-text"><RouterLink class="pct__name" :to="detailLocation(row)">{{ row.tenantName || '学校名称未取得' }}</RouterLink><div class="pct__code">{{ row.tenantCode || '编码未取得' }}</div></div></div>
            </template>
            <template #cell-status="{ row }"><StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" /><div class="pct__code">{{ environmentLabel(row.environment) }}</div></template>
            <template #cell-packageName="{ row }"><strong class="pct__package">{{ row.packageName || '套餐未取得' }}</strong><div class="pct__code">服务至 {{ dateLabel(row.expireAt) }}</div></template>
            <template #cell-usage="{ row }">
              <div class="pct__usage"><span>学生</span><b>{{ countLabel(row.studentCount) }} / {{ countLabel(row.maxStudents) }}</b></div>
              <progress v-if="usagePercent(row.studentCount, row.maxStudents) !== null" class="pct__meter" :class="{ 'pct__meter--high': usagePercent(row.studentCount, row.maxStudents) >= 90 }" :value="usagePercent(row.studentCount, row.maxStudents)" max="100" aria-label="学生容量占用" />
              <div class="pct__usage"><span>账号</span><b>{{ countLabel(row.userCount) }} / {{ countLabel(row.maxUsers) }}</b></div>
            </template>
            <template #cell-next="{ row }"><span class="pct__authority" :class="{ 'pct__authority--review': row.commercialAuthorityVerified === false }">{{ authorityLabel(row) }}</span><div class="pct__code">{{ nextLabel(row) }}</div></template>
            <template #cell-actions="{ row }"><div class="pct__ops"><RouterLink class="pct__detail-link" :to="detailLocation(row)">进入学校详情 <span aria-hidden="true">→</span></RouterLink><RouterLink v-if="can('platform.order.view') && ['trial', 'expired'].includes(row.status)" class="pct__secondary-link" :to="{ path: '/admin/platform/orders', query: { tenantId: row.tenantId } }">查看合同订单</RouterLink></div></template>
          </DataTable>
        </div>
        <nav class="pct__pagination" aria-label="学校清单分页">
          <span>第 {{ rangeStart }}–{{ rangeEnd }} 所，共 {{ rows.length }} 所</span>
          <label>每页 <select :value="pageSize" aria-label="每页学校数" @change="setPageSize($event.target.value)"><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select> 所</label>
          <div class="pct__page-buttons"><button type="button" :disabled="page <= 1" @click="setPage(page - 1)">上一页</button><span aria-live="polite">{{ page }} / {{ pageCount }}</span><button type="button" :disabled="page >= pageCount" @click="setPage(page + 1)">下一页</button></div>
        </nav>
      </template>
    </section>
    <p class="pct__safety-note">启停、延期与环境维护在学校详情中核对影响后办理。列表不会执行这些变更。</p>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import PlatformMetricStrip from '@/modules/platform/components/PlatformMetricStrip.vue'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { canEnterRoute, getPermissionPatterns, getRbacLoadFailed } from '@/security/permissionGate'
import { platformRoleLabel } from '@/modules/platform/constants/platform-display.constants'
import { toPlatformUiContext } from '@/security/platformAccessGate'
import { countLabel, statusLabel, statusTone, environmentLabel, dateLabel, usagePercent, parseListQuery, listQuery, tenantLocation, authorityLabel, validateTenantList } from '@/modules/platform/utils/tenantWorkspace.mjs'

export default {
  name: 'PlatformControlTenants',
  components: { PlatformMetricStrip, AppButton, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  props: { targetTab: { type: String, default: '' } },
  data() {
    return {
      density: 'comfortable', loading: true, error: '', rows: [], keyword: '', page: 1, pageSize: 20,
      applied: { keyword: '', status: '' }, filterKey: null, requestEpoch: 0, loadedAt: '',
      statusOptions: [{ value: '', label: '全部学校' }, { value: 'trial', label: '试用中' }, { value: 'active', label: '正式' }, { value: 'expired', label: '已到期' }, { value: 'disabled', label: '已停用' }],
      columns: [
        { key: 'tenantName', title: '学校', width: '240px' }, { key: 'status', title: '生命周期', width: '120px' },
        { key: 'packageName', title: '套餐 / 服务期限', width: '180px' }, { key: 'usage', title: '容量与用量', width: '200px' },
        { key: 'next', title: '授权核验 / 下一步', width: '170px' }, { key: 'actions', title: '办理入口', width: '150px' }
      ]
    }
  },
  computed: {
    schoolMetrics() {
      const ready = !this.loading && !this.error
      const count = states => ready ? this.rows.filter(row => states.includes(row.status)).length : '未取得'
      return [
        { label: '当前学校', value: ready ? this.rows.length : '未取得', unit: '所', caption: '按当前筛选条件统计', icon: 'enrollment' },
        { label: '正式服务', value: count(['active']), unit: '所', caption: '已进入正式服务阶段', tone: 'success', icon: 'workbench' },
        { label: '试用中', value: count(['trial']), unit: '所', caption: '跟进使用情况与转正安排', icon: 'students' },
        { label: '服务待跟进', value: count(['expired', 'disabled']), unit: '所', caption: '已到期或已停用的学校', tone: 'warning', icon: 'risk' }
      ]
    },
    roleName() { return platformRoleLabel(toPlatformUiContext()?.currentRole?.roleCode || 'PLATFORM') },
    pickerHint() { return ({ features: '选择学校，查看商业授权事实。此处不直接修改授权。', rules: '选择学校，进入该校规则工作区。', workflows: '选择学校，查看实际运行的审批流程。', brand: '选择学校，查看学校品牌配置。', brands: '选择学校，查看学校品牌配置。', users: '选择学校，进入该校账号工作区。' })[this.targetTab] || '' },
    pageCount() { return Math.max(1, Math.ceil(this.rows.length / this.pageSize)) },
    visibleRows() { return this.rows.slice((this.page - 1) * this.pageSize, this.page * this.pageSize) },
    rangeStart() { return this.rows.length ? (this.page - 1) * this.pageSize + 1 : 0 },
    rangeEnd() { return Math.min(this.page * this.pageSize, this.rows.length) }
  },
  watch: { '$route.fullPath'() { this.syncRoute() } },
  created() { this.syncRoute() },
  beforeUnmount() { this.requestEpoch += 1 },
  methods: {
    rowTone(row) { return ['expired', 'disabled'].includes(row.status) ? 'pct__service-attention' : '' },
    countLabel, statusLabel, statusTone, environmentLabel, dateLabel, usagePercent, authorityLabel,
    can(key) { return Array.isArray(getPermissionPatterns()) && !getRbacLoadFailed() && canEnterRoute({ moduleCode: 'PLATFORM', permissionKey: key }) },
    syncRoute() {
      const f = parseListQuery(this.$route.query)
      const key = JSON.stringify([f.keyword, f.status])
      const reload = key !== this.filterKey
      this.keyword = f.keyword; this.applied = { keyword: f.keyword, status: f.status }
      this.page = f.page; this.pageSize = f.pageSize; this.filterKey = key
      if (reload) return this.load()
      if (!this.loading && !this.error && this.page > this.pageCount) return this.setPage(this.pageCount)
    },
    navigate(filters) {
      const query = listQuery(filters)
      if (JSON.stringify(listQuery(this.$route.query)) === JSON.stringify(query)) return this.load()
      return this.$router.replace({ path: this.$route.path, query })
    },
    search() { return this.navigate({ ...this.applied, keyword: this.keyword, page: 1, pageSize: this.pageSize }) },
    selectStatus(status) { return this.navigate({ keyword: this.keyword, status, page: 1, pageSize: this.pageSize }) },
    clearFilters() { this.keyword = ''; return this.navigate({ pageSize: this.pageSize }) },
    setPage(page) { return this.navigate({ ...this.applied, page: Math.max(1, Math.min(page, this.pageCount)), pageSize: this.pageSize }) },
    setPageSize(pageSize) { return this.navigate({ ...this.applied, page: 1, pageSize: String(pageSize) }) },
    async load() {
      const epoch = ++this.requestEpoch
      const filters = { ...this.applied }
      this.loading = true; this.error = ''; this.rows = []; this.loadedAt = ''
      try {
        const res = await platformControlApi.listTenants(filters)
        if (epoch !== this.requestEpoch) return
        if (res?.code !== 0) throw new Error(res?.message || '学校清单读取失败，请重试')
        this.rows = validateTenantList(res.data)
        this.loadedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false })
        if (this.page > this.pageCount) {
          this.page = this.pageCount
          this.$router.replace({ path: this.$route.path, query: listQuery({ ...filters, page: this.page, pageSize: this.pageSize }) })
        }
      } catch (error) {
        if (epoch === this.requestEpoch) { this.rows = []; this.error = error?.message || '学校清单读取失败，请重试'; this.loadedAt = '' }
      } finally { if (epoch === this.requestEpoch) this.loading = false }
    },
    detailLocation(row) { return tenantLocation(row.tenantId, this.targetTab === 'brands' ? 'brand' : this.targetTab || 'info', this.$route) },
    nextLabel(row) {
      if (row.commercialAuthorityVerified === false) return '进入详情核对授权证据'
      return ({ trial: '核对试用与转正安排', expired: '核对续费与激活状态', disabled: '核对停用原因与恢复条件', active: '查看学校状态与配置' })[row.status] || '先核实生命周期状态'
    },
    goProvisioning() { if (this.can('platform.provision.run.view')) this.$router.push('/admin/platform/provisioning?create=1') }
  }
}
</script>

<style src="../../styles/workspace.css"></style>
<style scoped>
.pct__query{height:40px;padding:0 18px;border:0;border-radius:8px;background:var(--pri,#3c5cdb);color:#fff;font:inherit;cursor:pointer}.pct__hint{padding:12px 20px;background:var(--pri-bg,#edf1ff);color:var(--t2,#526176);font-size:13px;line-height:1.6}
.pct__workspace{background:var(--surface-card,var(--bg-card,#fff));border:1px solid var(--card-b,#e5eaf2);border-radius:14px;min-width:0;overflow:hidden}.pct__status-tabs{display:flex;gap:6px;padding:16px 20px 0;flex-wrap:wrap}.pct__status-tabs button{border:0;background:transparent;color:var(--t2,#526176);border-radius:8px;padding:9px 14px;font:inherit;cursor:pointer}.pct__status-tabs .is-active{background:var(--pri-bg,#edf1ff);color:var(--pri,#3c5cdb);font-weight:650}.pct__toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:16px 20px}.pct__search{flex:1;max-width:430px;min-width:180px}.pct__input{box-sizing:border-box;width:100%;height:40px;padding:0 13px;border:1px solid var(--card-b,#dde4ee);border-radius:8px;background:var(--bg-input,#fff);color:var(--t1,#1c2844);font:inherit}.pct__refresh{margin-left:auto;border:1px solid var(--card-b,#dde4ee);padding:8px 14px;border-radius:8px;background:transparent;color:var(--t2,#526176);font:inherit;cursor:pointer}.pct__result-bar{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:0 20px 14px;font-size:13px;color:var(--t2,#526176)}.pct__result-bar strong{color:var(--t1,#1c2844);font-size:16px}.pct__read-time{font-size:12px}.pct__table-region{overflow-x:auto}.pct__identity{display:flex;align-items:center;gap:12px}.pct__avatar{display:grid;place-items:center;flex:none;width:38px;height:38px;border-radius:11px;background:var(--pri-bg,#edf1ff);color:var(--pri,#3c5cdb);font-weight:700}.pct__identity-text{min-width:0}.pct__name{font-weight:650;color:var(--t1,#1c2844);text-decoration:none;overflow-wrap:anywhere}.pct__name:hover,.pct__detail-link:hover,.pct__secondary-link:hover{text-decoration:underline}.pct__code{margin-top:5px;font-size:12px;color:var(--text-secondary,#728098);line-height:1.5;overflow-wrap:anywhere}.pct__package{font-weight:550;color:var(--t1,#1c2844)}.pct__usage{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:var(--t2,#526176);line-height:1.7}.pct__usage b{font-weight:500}.pct__meter{display:block;width:100%;height:4px;margin:4px 0 6px;accent-color:var(--pri,#3c5cdb)}.pct__authority{font-size:13px;color:var(--t2,#526176)}.pct__authority--review{color:var(--warning-700,#96530b)}.pct__ops{display:flex;flex-direction:column;align-items:flex-start;gap:10px}.pct__detail-link{font-size:13px;font-weight:600;color:var(--pri,#3c5cdb);text-decoration:none}.pct__secondary-link{font-size:12px;color:var(--t2,#526176);text-decoration:none}.pct__pagination{display:flex;align-items:center;gap:18px;flex-wrap:wrap;border-top:1px solid var(--card-b,#e5eaf2);padding:14px 20px;font-size:12px;color:var(--t2,#526176)}.pct__pagination select{padding:5px 8px;background:var(--bg-input,#fff);color:inherit;border:1px solid var(--card-b,#dde4ee);border-radius:6px;font:inherit}.pct__page-buttons{display:flex;gap:12px;align-items:center;margin-left:auto}.pct__page-buttons button{border:1px solid var(--card-b,#dde4ee);border-radius:7px;background:transparent;color:inherit;padding:7px 10px;font:inherit;cursor:pointer}.pct__workspace button:disabled{opacity:.5;cursor:not-allowed}.pct__workspace :is(button,input,select,a):focus-visible{outline:2px solid var(--pri,#3c5cdb);outline-offset:3px}.pct__safety-note{font-size:12px;line-height:1.6;color:var(--text-secondary,#728098);margin:0}.pct__sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}@media(max-width:700px){.pct__toolbar,.pct__pagination{padding:12px}.pct__status-tabs{padding:12px 12px 0}.pct__result-bar{padding:0 12px 12px}.pct__status-tabs button{padding:8px 10px}.pct__read-time{display:block}.pct__page-buttons{margin-left:0}}

.pct__workspace { box-shadow: var(--s1); }
.pct__list-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3); padding: var(--space-5) var(--space-5) var(--space-2); }.pct__list-head h2 { margin: 0; font-size: var(--font-size-base); }.pct__list-head p { margin: var(--space-1) 0 0; font-size: var(--font-size-xs); color: var(--t2); line-height: 1.7; }
.pct__density { display: flex; padding: 3px; gap: 2px; border-radius: var(--rs); background: var(--bg-section); border: 1px solid var(--card-b); }.pct__density button { min-height: 32px; padding: var(--space-1) var(--space-3); border: 0; background: transparent; border-radius: var(--rs); color: var(--t2); font: inherit; font-size: var(--font-size-xs); cursor: pointer; }.pct__density button[aria-pressed="true"] { color: var(--pri); background: var(--bg-card); box-shadow: var(--s1); font-weight: var(--font-weight-semibold); }
.pct__status-tabs { border-bottom: 1px solid var(--card-b); gap: var(--space-4); padding-top: var(--space-2); }.pct__status-tabs button { min-height: 46px; padding: var(--space-2); border-radius: 0; border-bottom: 2px solid transparent; font-size: var(--font-size-sm); }.pct__status-tabs .is-active { border-bottom-color: var(--pri); background: transparent; }
.pct__toolbar { padding-block: var(--space-4); }.pct__search { max-width: 460px; }.pct__refresh { min-height: 40px; }.pct__table-region :deep(.dt__table) { min-width: 1030px; }.pct__table-region :deep(.pct__service-attention .dt__td:first-child) { box-shadow: inset 3px 0 0 var(--warn); }.pct__table-region--compact :deep(.dt__td) { padding-block: var(--space-2); }.pct__table-region--compact .pct__code { margin-top: 2px; }.pct__avatar { width: 42px; height: 42px; border-radius: var(--rs); }.pct__avatar[data-status="active"] { background: var(--ok-l); color: var(--success-700); }.pct__avatar[data-status="expired"] { background: var(--warn-l); color: var(--warning-700); }.pct__avatar[data-status="disabled"] { background: var(--bg-section); color: var(--t2); }.pct__code,.pct__safety-note { color: var(--t2); }.pct__usage,.pct__pagination { font-variant-numeric: tabular-nums; }.pct__meter { height: 5px; border: 0; border-radius: var(--rs); overflow: hidden; }.pct__meter--high { accent-color: var(--warn); }
.pct__detail-link { display: inline-flex; align-items: center; gap: var(--space-1); min-height: 36px; padding: var(--space-1) var(--space-2); border-radius: var(--rs); background: var(--pri-bg); font-weight: var(--font-weight-medium); }.pct__secondary-link { display: inline-flex; align-items: center; min-height: 30px; padding-inline: var(--space-2); }.pct__ops { gap: var(--space-1); }.pct__pagination select,.pct__page-buttons button { min-height: 34px; }.pct__empty { display: flex; flex-direction: column; align-items: center; padding-bottom: var(--space-5); }.pct__safety-note { padding: var(--space-3) var(--space-4); border-left: 2px solid var(--card-b); background: var(--bg-card); border-radius: var(--rs); }
@media (max-width: 700px) { .pct__list-head { padding: var(--space-4) var(--space-3) var(--space-2); }.pct__status-tabs { gap: var(--space-2); }.pct__search { min-width: 100%; max-width: none; }.pct__refresh { margin-left: 0; } }
/* Native progress rendering is explicit in both browser engines. */
.pct__meter { appearance: none; border: 0; border-radius: 999px; overflow: hidden; background: var(--bg-section); }
.pct__meter::-webkit-progress-bar { border-radius: 999px; background: var(--bg-section); }
.pct__meter::-webkit-progress-value { border-radius: 999px; background: var(--pri); }
.pct__meter::-moz-progress-bar { border-radius: 999px; background: var(--pri); }
.pct__meter--high::-webkit-progress-value { background: var(--warn); }
.pct__meter--high::-moz-progress-bar { background: var(--warn); }
</style>
