<template>
  <ModulePageShell class="platform-workspace ptd" :title="tenant ? tenant.tenantName : '学校详情'" :subtitle="tenant ? tenant.tenantCode + ' · ' + pkgLabel : ''" :role-name="roleName" data-scope-name="当前学校对象">
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回学校清单</AppButton>
    </template>
    <LoadingState v-if="loading" text="正在加载学校详情…" />
    <template v-else-if="tenant">
      <section class="ptd__object" aria-label="当前学校与办理入口">
        <div class="ptd__object-avatar" aria-hidden="true">{{ (tenant.tenantName || '校').slice(0, 1) }}</div>
        <div class="ptd__object-copy"><span class="pw-eyebrow">学校服务工作区</span><h2>{{ schoolNextStep }}</h2><p><StatusTag :type="statusType" :label="statusLabel" /><span>{{ environmentLabel(tenant.environment) }}</span><span>{{ tenant.tenantCode }}</span></p></div>
        <RouterLink v-if="can('platform.order.view')" class="pw-button" :to="{ path: '/admin/platform/orders', query: { tenantId: tid } }">查看该校合同订单 <span aria-hidden="true">→</span></RouterLink>
      </section>
      <nav class="ptd__tabs" aria-label="学校工作区">
        <button v-for="t in tabs" :key="t.key" type="button" class="ptd__tab" :class="{ 'is-active': tab === t.key }" :aria-pressed="tab === t.key" @click="switchTab(t.key)">{{ t.label }}</button>
      </nav>
      <div v-if="pendingRulesNavigation" class="ptd__leave-rules" role="alert">
        <strong>{{ tab === 'rules' ? '规则草稿或本次提交记录尚未处理' : '学校变更尚未办理完毕' }}</strong>
        <p>{{ workspaceBusy ? '正在请求服务器，暂不能离开；请勿重复提交。' : '离开会清除本页草稿和核验记录。已经发送的请求不会因此撤销；结果未确认时，请先核对配置和审计。' }}</p>
        <div class="ptd__ops"><AppButton variant="primary" @click="pendingRulesNavigation = null">继续办理</AppButton><AppButton variant="ghost" :disabled="workspaceBusy || rulesLeaveApproved" @click="leaveRules">清除本页记录并离开</AppButton></div>
      </div>
      <LoadingState v-if="tabLoading" text="正在读取当前工作区…" />
      <ErrorState v-else-if="tabError" :description="tabError" @retry="loadTab(tab)" @back="backToList" />
      <template v-else>
        <div v-if="tab === 'info'" class="ptd__cols">
          <AppCard class="ptd__panel">
            <AppSectionHeader title="学校运营档案" />
            <ul class="ptd__kv">
              <li><span>生命周期</span><StatusTag :type="statusType" :label="statusLabel" /></li>
              <li><span>当前套餐</span><b>{{ tenant.packageName || '未取得' }}</b></li>
              <li><span>服务期限</span><b>{{ fmt(tenant.expireAt) || '未取得' }}</b></li>
              <li><span>环境</span><b>{{ environmentLabel(tenant.environment) }}</b></li>
              <li><span>联系人</span><b>{{ (tenant.contactName || '—') + ' ' + (tenant.contactPhone || '') }}</b></li>
              <li><span>地区</span><b>{{ (tenant.province || '—') + ' ' + (tenant.city || '') }}</b></li>
            </ul>
          </AppCard>
          <AppCard class="ptd__panel">
            <AppSectionHeader title="容量与用量" />
            <ul class="ptd__kv">
              <li><span>学生数</span><b>{{ countLabel(tenant.studentCount) }} / {{ countLabel(tenant.maxStudents) }}</b></li>
              <li><span>账号数</span><b>{{ countLabel(tenant.userCount) }} / {{ countLabel(tenant.maxUsers) }}</b></li>
              <li><span>商业存储上限</span><b>{{ formatBytes(tenant360.storage?.commercialStorageLimitBytes) }}</b></li>
              <li><span>学校治理配额</span><b>{{ formatBytes(tenant360.storage?.schoolGovernanceQuotaBytes) }}</b></li>
              <li><span>真实占用（文件+预留）</span><b>{{ formatBytes(tenant360.storage?.actualOccupancyBytes) }}</b></li>
              <li v-if="tenant360.effectiveState?.mismatch"><span>状态一致性</span><b class="ptd__danger">租户主状态与租户元数据不一致</b></li>
            </ul>
            <p class="ptd__authority-note">商业套餐与商业额度由已支付订单或受控特批决定；本页不再提供普通直改入口。</p>
          </AppCard>
          <TenantLifecycleWorkspace ref="lifecycleWorkspace" :key="tid" class="ptd__full" :tenant="tenant" :tenant360="tenant360" @activity="lifecycleActivity = $event" @changed="load" />
        </div>

        <AppCard v-else-if="tab === 'features'" class="ptd__panel">
          <AppSectionHeader title="商业授权（只读对账）" />
          <p class="ptd__authority-note">{{ featuresAuthorityHint }}</p>
          <div class="ptd__switches">
            <label v-for="k in featureKeys" :key="k" class="ptd__switch"><input :checked="Boolean(features[k])" type="checkbox" disabled /><span>{{ featureLabels[k] || '待命名功能' }}</span></label>
          </div>
          <EmptyState v-if="!featureKeys.length" title="接口未返回可展示的授权项" description="请先核对当前学校的合同订单与套餐证据，不在此处直接授予商业权限。"><template #actions><button type="button" class="pw-button" @click="switchTab('info')">返回学校概况</button></template></EmptyState>
        </AppCard>

        <AppCard v-else-if="tab === 'studentPortal'" class="ptd__panel">
          <AppSectionHeader title="学生电脑门户配置（保存后写审计；关闭的模块或功能，学生端菜单隐藏且后端拒绝访问）" />
          <StudentPortalConfigPanel :tenant-id="tid" />
        </AppCard>

        <TenantRulesWorkspace v-else-if="tab === 'rules'" ref="rulesWorkspace" :key="tid" :tenant="tenant" :projection="rulesProjection" @activity="rulesActivity = $event" />

        <AppCard v-else-if="tab === 'workflows'" class="ptd__panel">
          <AppSectionHeader title="审批流运行定义（只读）" />
          <p class="ptd__authority-note">WorkflowDefinition 是唯一运行真值；历史 WORKFLOWS JSON 仅用于漂移对账，请在学校系统管理的流程治理工作区修改正式定义。</p>
          <DataTable :columns="wfColumns" :rows="workflowRows" row-key="workflowCode">
            <template #cell-enabled="{ row }"><input :checked="Boolean(row.enabled)" type="checkbox" disabled /></template>
            <template #cell-needApproval="{ row }"><input :checked="Boolean(row.needApproval)" type="checkbox" disabled /></template>
            <template #cell-approverRoleCodes="{ row }"><span class="ptd__roles">{{ roleLabels(row.approverRoleCodes) }}</span></template>
            <template #cell-timeoutHours="{ row }"><span>{{ row.timeoutHours || '—' }}</span></template>
          </DataTable>
          <EmptyState v-if="!workflowRows.length" title="当前学校暂无运行流程定义" description="正式流程由学校系统管理的流程治理工作区维护。"><template #actions><button type="button" class="pw-button" @click="switchTab('info')">返回学校概况</button></template></EmptyState>
        </AppCard>

        <AppCard v-else-if="tab === 'brand'" class="ptd__panel">
          <AppSectionHeader title="学校品牌（只读）" />
          <p class="ptd__authority-note">品牌由学校系统管理维护，此处读取同一份学校品牌配置，不再提供第二套保存入口。</p>
          <dl class="ptd__brand"><div v-for="f in brandFields" :key="f.key"><dt>{{ f.label }}</dt><dd>{{ brand[f.key] || '未配置' }}</dd></div></dl>
          <p class="ptd__brand-source">学校品牌版本 {{ brandVersion }}</p>
          <p v-if="brandMeta.legacyOverrideReadOnly" class="ptd__authority-note">存在历史平台品牌记录，仅用于对账，不参与当前品牌展示。</p>
        </AppCard>

        <AppCard v-else-if="tab === 'users'" class="ptd__panel">
          <AppSectionHeader title="学校账号（创建管理员 / 停用 / 重置密码）" />
          <div class="ptd__user-create"><input v-model.trim="newUser.loginName" class="ptd__input" placeholder="登录名" :disabled="saving" /><input v-model.trim="newUser.realName" class="ptd__input" placeholder="姓名" :disabled="saving" /><AppButton variant="primary" :loading="saving" @click="createUser">创建学校管理员</AppButton></div>
          <div v-if="oneTimeSecret" class="ptd__secret"><span>{{ oneTimeSecret }}（仅本次显示，请立即转交；刷新或切换学校后不可再查看）</span><AppButton variant="ghost" @click="oneTimeSecret = ''">我已记录</AppButton></div>
          <DataTable :columns="userColumns" :rows="users" row-key="userId">
            <template #cell-status="{ row }"><StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.status === 'ACTIVE' ? '启用' : '停用'" /></template>
            <template #cell-userType="{ row }">{{ platformRoleLabel(row.userType) }}</template>
            <template #cell-lastLoginAt="{ row }">{{ fmt(row.lastLoginAt) || '从未登录' }}</template>
            <template #cell-actions="{ row }"><div class="ptd__ops ptd__ops--row"><AppButton v-if="row.status !== 'ACTIVE'" variant="ghost" :disabled="saving" @click="userAct(row, 'enable')">启用</AppButton><AppButton v-else variant="danger" :disabled="saving" @click="userAct(row, 'disable')">停用</AppButton><AppButton variant="warning" :disabled="saving" @click="userAct(row, 'reset-password')">重置密码</AppButton></div></template>
          </DataTable>
          <EmptyState v-if="!users.length" title="该学校暂无账号" description="当前接口已返回空清单；已有账号不受本页面筛选影响。"><template #actions><button type="button" class="pw-button" @click="switchTab('info')">返回学校概况</button></template></EmptyState>
        </AppCard>
        <TenantOffboardingPanel v-else-if="tab === 'offboarding'" :tenant-id="tid" :tenant="tenant" :tenant360="tenant360" @changed="load" />
      </template>
    </template>
    <ErrorState v-else :description="error || '学校详情未取得'" @retry="load" @back="backToList" />
  </ModulePageShell>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import StudentPortalConfigPanel from '@/modules/platform/components/StudentPortalConfigPanel.vue'
import TenantOffboardingPanel from '@/modules/platform/components/TenantOffboardingPanel.vue'
import TenantLifecycleWorkspace from '@/modules/platform/components/TenantLifecycleWorkspace.vue'
import TenantRulesWorkspace from '@/modules/platform/components/TenantRulesWorkspace.vue'
import { rulesSnapshot } from '@/modules/platform/utils/tenantRuleDraft.mjs'
import { countLabel, environmentLabel, wholeNumber, returnLocation } from '@/modules/platform/utils/tenantWorkspace.mjs'
import { toPlatformUiContext } from '@/security/platformAccessGate'
import { canEnterRoute, getPermissionPatterns, getRbacLoadFailed } from '@/security/permissionGate'
import {
  PLATFORM_FEATURE_LABELS,
  platformRoleLabel
} from '@/modules/platform/constants/platform-display.constants'
import { toast } from '@/utils/toast'

const STATUS = { trial: ['warning', '试用中'], active: ['success', '正式'], expired: ['danger', '已到期'], disabled: ['default', '已停用'] }

export default {
  name: 'PlatformControlTenantDetail',
  components: { AppButton, AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag, StudentPortalConfigPanel, TenantOffboardingPanel, TenantLifecycleWorkspace, TenantRulesWorkspace },
  data() {
    return {
      loading: true, saving: false, error: '', tabLoading: false, tabError: '',
      tenant: null, tenant360: {}, requestEpoch: 0, tabRequestEpoch: 0, mutationEpoch: 0, tab: 'info',
      tabs: [
        { key: 'info', label: '学校概况与办理' }, { key: 'features', label: '商业授权' },
        { key: 'rules', label: '规则中心' }, { key: 'workflows', label: '审批流' },
        { key: 'brand', label: '品牌（只读）' }, { key: 'users', label: '账号' },
        { key: 'studentPortal', label: '学生电脑门户' }, { key: 'offboarding', label: '退租与数据销毁' }
      ],
      quota: { maxStudents: 0, maxUsers: 0, storageLimitMb: 0 },
      features: {}, featureKeys: [], featureLabels: PLATFORM_FEATURE_LABELS, featuresMeta: {},
      lifecycleActivity: { protected: false, busy: false, phase: 'edit' },
      rulesProjection: null, rulesActivity: { protected: false, busy: false, phase: 'edit' }, pendingRulesNavigation: null, rulesLeaveApproved: false,
      workflowRows: [], workflowMeta: {},
      wfColumns: [
        { key: 'workflowName', title: '审批流', width: '180px' }, { key: 'enabled', title: '启用', width: '60px', align: 'center' },
        { key: 'needApproval', title: '需审批', width: '70px', align: 'center' }, { key: 'approverRoleCodes', title: '审批角色', width: '200px' },
        { key: 'timeoutHours', title: '时限(小时)', width: '110px' }
      ],
      brand: {}, brandVersion: 0, brandMeta: {},
      brandFields: [
        { key: 'schoolName', label: '学校名称' }, { key: 'schoolShortName', label: '学校简称' },
        { key: 'platformDisplayName', label: '平台展示名称' }, { key: 'brandColor', label: '品牌主色' },
        { key: 'loginSlogan', label: '登录标语' }, { key: 'watermarkText', label: '页面水印' },
        { key: 'watermarkDensity', label: '水印密度' }, { key: 'footerText', label: '页脚文案' }
      ],
      users: [],
      userColumns: [
        { key: 'loginName', title: '登录名', width: '140px' }, { key: 'realName', title: '姓名', width: '110px' },
        { key: 'userType', title: '类型', width: '130px' }, { key: 'status', title: '状态', width: '80px' },
        { key: 'lastLoginAt', title: '最近登录', width: '150px' }, { key: 'actions', title: '操作', width: '220px' }
      ],
      newUser: { loginName: '', realName: '' }, oneTimeSecret: ''
    }
  },
  computed: {
    schoolNextStep() { return ({ trial: '核对试用安排，再推进正式开通', expired: '核对续费与授权激活', disabled: '先核对停用原因，再办理恢复', active: '查看学校服务，按事项进入办理' })[this.tenant?.status] || '先核实当前学校状态' },
    workspaceBusy() { return this.saving || (this.tab === 'rules' ? this.rulesActivity.busy : this.tab === 'info' && this.lifecycleActivity.busy) },
    tid() { return this.$route.params.tenantId || this.$route.params.id },
    roleName() { return platformRoleLabel(toPlatformUiContext()?.currentRole?.roleCode || 'PLATFORM') },
    pkgLabel() { return this.tenant ? (this.tenant.packageName || '套餐未取得') + ' · 服务至 ' + (this.fmt(this.tenant.expireAt) || '未取得') : '' },
    statusType() { return (STATUS[this.tenant?.status] || ['default'])[0] },
    statusLabel() { return (STATUS[this.tenant?.status] || ['default', '状态待确认'])[1] },
    featuresAuthorityHint() {
      if (this.featuresMeta.legacyOverrideReadOnly) return '检测到历史授权覆盖：当前仅允许只读对账，不能继续从此页面直接改商业授权。'
      if (this.featuresMeta.authoritySource === 'PAID_ORDER') return '商业授权来自已支付订单；学校启停由学校系统管理单独控制。'
      return '商业授权来自套餐/订单权威；此处只展示，不作为学校功能开关写入口。'
    }
  },
  watch: {
    tid(newTenantId, oldTenantId) {
      if (String(newTenantId || '') === String(oldTenantId || '')) return
      this.resetTenantState()
      const requestedTab = this.$route.query.tab
      this.tab = requestedTab && this.tabs.some((item) => item.key === requestedTab) ? requestedTab : 'info'
      this.load()
    },
    '$route.query.tab'(value) {
      if (this.loading || !this.tenant || String(this.tenant.tenantId) !== String(this.tid)) return
      const key = this.tabs.some(item => item.key === value) ? value : 'info'
      if (key !== this.tab) { this.tab = key; this.oneTimeSecret = ''; this.loadTab(key) }
    }
  },
  created() {
    const requestedTab = this.$route.query.tab
    if (requestedTab && this.tabs.some((item) => item.key === requestedTab)) this.tab = requestedTab
    this.load()
  },
  beforeRouteLeave(to) { return !this.blockRulesNavigation(to.fullPath) },
  beforeRouteUpdate(to, from) { return to.fullPath === from.fullPath || !this.blockRulesNavigation(to.fullPath) },
  beforeUnmount() { this.requestEpoch += 1; this.tabRequestEpoch += 1; this.mutationEpoch += 1; this.oneTimeSecret = '' },
  methods: {
    countLabel, environmentLabel,
    can(key) { return Array.isArray(getPermissionPatterns()) && !getRbacLoadFailed() && canEnterRoute({ moduleCode: 'PLATFORM', permissionKey: key }) },
    protectedWorkspace() { return this.tab === 'rules' ? this.$refs?.rulesWorkspace : this.tab === 'info' ? this.$refs?.lifecycleWorkspace : null },
    blockRulesNavigation(destination) {
      if (this.rulesLeaveApproved || !this.protectedWorkspace()?.protectNavigation) return false
      this.pendingRulesNavigation = destination
      return true
    },
    async leaveRules() {
      if (this.rulesLeaveApproved || !this.pendingRulesNavigation || this.protectedWorkspace()?.busy) return
      const destination = this.pendingRulesNavigation
      this.rulesLeaveApproved = true
      try {
        const failure = await this.$router.push(destination)
        if (!failure) this.pendingRulesNavigation = null
      } catch (error) { toast.error(error?.message || '暂未离开，规则草稿仍保留在本页') }
      finally { this.rulesLeaveApproved = false }
    },
    backToList() { this.$router.push(returnLocation(this.$route.query)) },
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' },
    formatBytes(value) { const bytes = wholeNumber(value); return bytes === null ? '未取得' : `${(bytes / 1024 ** 3).toFixed(2)} GiB` },
    platformRoleLabel,
    roleLabels(values) { return (Array.isArray(values) ? values : []).map((value) => platformRoleLabel(value)).join(' / ') || '—' },
    clearTenantPayload() {
      this.error = ''; this.tabError = ''; this.tabLoading = false
      this.tenant = null; this.tenant360 = {}; this.saving = false
      this.quota = { maxStudents: 0, maxUsers: 0, storageLimitMb: 0 }
      this.features = {}; this.featureKeys = []; this.featuresMeta = {}
      this.lifecycleActivity = { protected: false, busy: false, phase: 'edit' }
      this.rulesProjection = null; this.pendingRulesNavigation = null; this.rulesActivity = { protected: false, busy: false, phase: 'edit' }
      this.workflowRows = []; this.workflowMeta = {}
      this.brand = {}; this.brandVersion = 0; this.brandMeta = {}
      this.users = []; this.newUser = { loginName: '', realName: '' }; this.oneTimeSecret = ''
    },
    resetTenantState() {
      this.requestEpoch += 1; this.tabRequestEpoch += 1; this.mutationEpoch += 1
      this.clearTenantPayload(); this.loading = true
    },
    async load() {
      const tenantId = String(this.tid || ''), epoch = ++this.requestEpoch
      this.tabRequestEpoch += 1; this.mutationEpoch += 1
      this.clearTenantPayload(); this.loading = true
      try {
        const res = await platformControlApi.getTenant(tenantId)
        if (epoch !== this.requestEpoch || tenantId !== String(this.tid || '')) return
        if (res?.code !== 0) throw new Error(res?.message || '学校详情读取失败')
        if (!res.data || String(res.data.tenantId) !== tenantId || (res.data.tenant360?.tenantId != null && String(res.data.tenant360.tenantId) !== tenantId)) throw new Error('学校身份与请求不一致，已停止展示')
        this.tenant = res.data; this.tenant360 = res.data.tenant360 || {}
        this.quota = { maxStudents: res.data.maxStudents, maxUsers: res.data.maxUsers, storageLimitMb: res.data.storageLimitMb }
        await this.loadTab(this.tab)
      } catch (error) {
        if (epoch === this.requestEpoch && tenantId === String(this.tid || '')) { this.tenant = null; this.tenant360 = {}; this.error = error?.message || '学校详情读取失败' }
      } finally { if (epoch === this.requestEpoch && tenantId === String(this.tid || '')) this.loading = false }
    },
    switchTab(key) {
      if (!this.tabs.some(item => item.key === key) || this.saving) return
      if (key !== this.tab && this.blockRulesNavigation({ path: this.$route.path, query: { ...this.$route.query, tab: key } })) return
      if (key === this.tab && this.protectedWorkspace()?.protectNavigation) return
      this.tab = key; this.oneTimeSecret = ''
      this.$router.replace({ query: { ...this.$route.query, tab: key } })
      this.loadTab(key)
    },
    async loadTab(key) {
      const tenantId = String(this.tid || ''), epoch = ++this.tabRequestEpoch
      const stillCurrent = () => epoch === this.tabRequestEpoch && tenantId === String(this.tid || '') && key === this.tab
      this.tabError = ''; this.tabLoading = false
      const method = { features: 'getFeatures', rules: 'getRules', workflows: 'getWorkflows', brand: 'getBrand', users: 'listUsers' }[key]
      if (!method) return
      if (key === 'features') { this.features = {}; this.featureKeys = []; this.featuresMeta = {} }
      if (key === 'rules') this.rulesProjection = null
      if (key === 'workflows') { this.workflowRows = []; this.workflowMeta = {} }
      if (key === 'brand') { this.brand = {}; this.brandVersion = 0; this.brandMeta = {} }
      if (key === 'users') this.users = []
      this.tabLoading = true
      try {
        const res = await platformControlApi[method](tenantId)
        if (!stillCurrent()) return
        if (res?.code !== 0) throw new Error(res?.message || '当前工作区读取失败')
        const data = res.data
        if (!data || typeof data !== 'object' || Array.isArray(data) || (data.tenantId != null && String(data.tenantId) !== tenantId)) throw new Error('当前学校工作区数据异常')
        if (key === 'features') { if (!data.features || typeof data.features !== 'object' || Array.isArray(data.features)) throw new Error('商业授权数据未取得'); this.features = data.features; this.featureKeys = Object.keys(data.features); this.featuresMeta = data }
        else if (key === 'rules') this.rulesProjection = rulesSnapshot(data, tenantId)
        else if (key === 'workflows') { if (!data.workflows || typeof data.workflows !== 'object') throw new Error('流程定义数据未取得'); this.workflowRows = Object.values(data.workflows); this.workflowMeta = data }
        else if (key === 'brand') { if (data.authority !== 'TENANT_BRAND_CONFIG' || !data.brand || typeof data.brand !== 'object' || Array.isArray(data.brand) || wholeNumber(data.version) === null) throw new Error('学校品牌权威或版本未取得'); this.brand = data.brand; this.brandVersion = wholeNumber(data.version); this.brandMeta = data }
        else { if (!Array.isArray(data.list)) throw new Error('学校账号清单未取得'); this.users = data.list }
      } catch (error) { if (stillCurrent()) this.tabError = error?.message || '当前工作区读取失败，请重试' }
      finally { if (stillCurrent()) this.tabLoading = false }
    },
    async createUser() {
      if (this.saving || this.tab !== 'users') return
      if (!this.newUser.loginName || !this.newUser.realName) return toast.error('登录名与姓名必填')
      const tenantId = String(this.tid), epoch = ++this.mutationEpoch
      this.saving = true
      try {
        const res = await platformControlApi.createUser(tenantId, { ...this.newUser })
        if (epoch !== this.mutationEpoch || tenantId !== String(this.tid) || this.tab !== 'users') return
        if (res.code === 0) { this.oneTimeSecret = res.data.initialPassword ? '账号 ' + res.data.loginName + ' 初始密码：' + res.data.initialPassword : ''; this.newUser = { loginName: '', realName: '' }; await this.loadTab('users') }
        else toast.error(res.message)
      } catch (error) { if (epoch === this.mutationEpoch && tenantId === String(this.tid)) toast.error(error?.message || '账号创建结果未取得，请先核对账号清单') }
      finally { if (epoch === this.mutationEpoch && tenantId === String(this.tid)) this.saving = false }
    },
    async userAct(row, action) {
      if (this.saving || this.tab !== 'users' || !this.users.some(item => item.userId === row.userId)) return
      const tenantId = String(this.tid), epoch = ++this.mutationEpoch
      this.saving = true; this.oneTimeSecret = ''
      try {
        const res = await platformControlApi.userAction(row.userId, action)
        if (epoch !== this.mutationEpoch || tenantId !== String(this.tid) || this.tab !== 'users') return
        if (res.code === 0) { if (action === 'reset-password' && res.data.newPassword) this.oneTimeSecret = '账号 ' + row.loginName + ' 新密码：' + res.data.newPassword; else toast.success('操作成功'); await this.loadTab('users') }
        else toast.error(res.message)
      } catch (error) { if (epoch === this.mutationEpoch && tenantId === String(this.tid)) toast.error(error?.message || '账号变更结果未取得，请先核对状态') }
      finally { if (epoch === this.mutationEpoch && tenantId === String(this.tid)) this.saving = false }
    }
  }
}
</script>

<style src="../../styles/workspace.css"></style>
<style scoped>
.ptd__object { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-4); padding: var(--space-5); background: linear-gradient(120deg, var(--pri-bg), var(--bg-card)); border: 1px solid var(--card-b); border-radius: var(--r); }
.ptd__object-avatar { display: grid; place-items: center; flex: none; width: 56px; height: 56px; border-radius: 16px; background: var(--bg-card); color: var(--pri); border: 1px solid var(--card-b); font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold); }
.ptd__object-copy { flex: 1; min-width: 180px; }
.ptd__object h2 { margin: var(--space-2) 0; font-size: var(--font-size-lg); color: var(--t1); line-height: 1.6; }
.ptd__object p { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-3); margin: 0; color: var(--t2); font-size: var(--font-size-xs); overflow-wrap: anywhere; }
.ptd__object > .pw-button { flex: none; }
.ptd__tabs { padding: var(--space-2); border: 1px solid var(--card-b); border-radius: var(--r); background: var(--bg-card); }
@media(max-width:600px) { .ptd__object { padding: var(--space-4); }.ptd__object-copy { min-width: 0; flex-basis: calc(100% - 80px); }.ptd__object > .pw-button { width: 100%; }.ptd__kv li { align-items: flex-start; } }

.ptd__leave-rules{padding:14px 16px;border:1px solid var(--warning-700,#96530b);border-radius:9px;background:var(--warn-l,#fff5e5);color:var(--t1,#1c2844);font-size:13px;line-height:1.65}.ptd__leave-rules p{margin:6px 0 0}.ptd__leave-rules .ptd__ops{margin-top:10px}
.ptd__tabs{display:flex;gap:6px;overflow-x:auto;padding:4px 0 10px}.ptd__tab{flex:none;height:38px;padding:0 14px;border:1px solid var(--card-b,#e5eaf2);border-radius:8px;background:var(--bg-card,#fff);color:var(--t2,#526176);font-size:13px;font-family:inherit;cursor:pointer}.ptd__tab.is-active{background:var(--pri-bg,#edf1ff);border-color:var(--pri,#3c5cdb);color:var(--pri,#3c5cdb);font-weight:650}.ptd__tab:focus-visible{outline:2px solid var(--pri,#3c5cdb);outline-offset:2px}.ptd__cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:var(--space-3,16px)}.ptd__full{grid-column:1/-1}.ptd__panel{padding:var(--space-4,20px);min-width:0}.ptd__kv{list-style:none;margin:var(--space-2,8px) 0 0;padding:0;display:flex;flex-direction:column;gap:12px}.ptd__kv li{display:flex;align-items:baseline;justify-content:space-between;gap:16px;font-size:var(--font-size-sm,13px);color:var(--text-secondary,#728098)}.ptd__kv li span{flex:none}.ptd__kv b{color:var(--t1,#1c2844);font-weight:550;overflow-wrap:anywhere;text-align:right}.ptd__danger{color:var(--danger-600,#b42318)!important}.ptd__ops{display:flex;gap:var(--space-2,8px);flex-wrap:wrap;margin-top:var(--space-3,16px)}.ptd__ops--row{margin-top:0}.ptd__input{height:36px;padding:0 10px;border:1px solid var(--card-b,#e5eaf2);border-radius:8px;background:var(--bg-input,#fff);color:var(--t1,#1c2844);font-size:13px;font-family:inherit;min-width:0}.ptd__input:focus-visible{outline:2px solid var(--pri,#3c5cdb);outline-offset:2px}.ptd__switches{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:var(--space-2,8px);margin-top:var(--space-3,16px)}.ptd__switch{display:flex;align-items:center;gap:var(--space-2,8px);font-size:var(--font-size-sm,13px);color:var(--t2,#526176)}.ptd__roles{font-size:12px;color:var(--text-secondary,#728098)}.ptd__brand{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(240px,100%),1fr));gap:20px;margin-top:20px}.ptd__brand dt,.ptd__brand-source{font-size:12px;color:var(--text-secondary,#728098)}.ptd__brand dd{margin:6px 0 0;font-size:14px;color:var(--t1,#1c2844);overflow-wrap:anywhere}.ptd__user-create{display:flex;gap:var(--space-2,8px);flex-wrap:wrap;margin:var(--space-3,16px) 0}.ptd__secret{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2,8px);padding:var(--space-2,8px) var(--space-3,16px);border-radius:9px;background:var(--warn-l,#fff5e5);color:var(--warning-700,#96530b);font-size:var(--font-size-sm,13px);margin-bottom:var(--space-3,16px);overflow-wrap:anywhere}.ptd__authority-note{margin:var(--space-3,16px) 0 0;padding:var(--space-2,8px) var(--space-3,16px);border-radius:9px;background:var(--pri-bg,#edf1ff);color:var(--text-secondary,#728098);font-size:var(--font-size-sm,13px);line-height:1.6}
.ptd__tabs { padding: var(--space-2); gap: var(--space-1); }.ptd__tab { border-color: transparent; min-height: 40px; }.ptd__tab.is-active { border-color: transparent; }
</style>
